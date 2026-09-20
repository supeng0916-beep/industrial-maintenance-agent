"""Writer-owned OPC UA lifecycle; API readers never initialize or migrate tables."""
from datetime import timezone
import json
import sqlite3

DEVICE_ID = 'motor-b'
METRIC = 'temperature'


class SessionSuperseded(sqlite3.OperationalError):
    """A newer collector owns this device or connection generation."""


def stamp(value):
    return value.astimezone(timezone.utc).isoformat(timespec='microseconds')


def table_exists(conn, name):
    return conn.execute("SELECT 1 FROM sqlite_master WHERE type='table' AND name=?", (name,)).fetchone() is not None


def assert_owner(conn, session, generation=None):
    row = conn.execute('SELECT session_id FROM temperature_alarm_state WHERE device_id=? AND metric=?', (DEVICE_ID,METRIC)).fetchone()
    if row is None or row[0] != session:
        raise SessionSuperseded('采集会话已失效，旧采集器不能修改新会话状态')
    if generation is not None:
        row = conn.execute('SELECT session_id,generation FROM opcua_runtime WHERE device_id=?', (DEVICE_ID,)).fetchone()
        if row is None or row[0] != session or row[1] != generation:
            raise SessionSuperseded('订阅世代已失效，旧通知不能修改新订阅状态')


def initialize_runtime(conn, session, mode, now):
    if mode not in ('read','subscribe'):
        raise ValueError('mode must be read or subscribe')
    conn.executescript('''CREATE TABLE IF NOT EXISTS opcua_runtime (
        device_id TEXT PRIMARY KEY, session_id TEXT NOT NULL, mode TEXT NOT NULL,
        state TEXT NOT NULL, generation INTEGER NOT NULL DEFAULT 0, updated_at TEXT NOT NULL,
        last_notification_at TEXT, last_publish_at TEXT, reconnect_count INTEGER NOT NULL DEFAULT 0,
        duplicate_count INTEGER NOT NULL DEFAULT 0, dropped_count INTEGER NOT NULL DEFAULT 0,
        error TEXT, revised TEXT);
        CREATE TABLE IF NOT EXISTS opcua_notification_receipts (
            identity TEXT PRIMARY KEY, session_id TEXT NOT NULL, generation INTEGER NOT NULL,
            received_at TEXT NOT NULL);
    ''')
    with conn:
        conn.execute('BEGIN IMMEDIATE')
        assert_owner(conn,session)
        conn.execute('''INSERT OR REPLACE INTO opcua_runtime
            (device_id,session_id,mode,state,updated_at) VALUES (?,?,?,?,?)''',
            (DEVICE_ID,session,mode,'reading' if mode=='read' else 'connecting',stamp(now)))
        # Receipts are relevant only inside the current collector session.
        conn.execute('DELETE FROM opcua_notification_receipts WHERE session_id<>?', (session,))


def update_in_transaction(conn, session, now, *, expected_generation=None, **fields):
    assert_owner(conn, session, expected_generation)
    allowed={'state','generation','last_notification_at','last_publish_at','reconnect_count','duplicate_count','dropped_count','error','revised'}
    if not fields.keys() <= allowed:
        raise ValueError('Unknown runtime fields')
    fields=dict(fields)
    if 'revised' in fields and fields['revised'] is not None:
        fields['revised']=json.dumps(fields['revised'],ensure_ascii=False,allow_nan=False)
    for name in ('last_notification_at','last_publish_at'):
        if name in fields and fields[name] is not None and not isinstance(fields[name],str):
            fields[name]=stamp(fields[name])
    fields['updated_at']=stamp(now)
    query=','.join(f'{name}=?' for name in fields)
    cursor=conn.execute(f'UPDATE opcua_runtime SET {query} WHERE device_id=? AND session_id=?', (*fields.values(),DEVICE_ID,session))
    if cursor.rowcount != 1:
        raise SessionSuperseded('运行状态已由另一采集会话接管')


def update_runtime(conn, session, now, *, expected_generation=None, **fields):
    with conn:
        conn.execute('BEGIN IMMEDIATE')
        update_in_transaction(conn,session,now,expected_generation=expected_generation,**fields)


def interrupt_runtime(conn, session, now, message, *, state='reconnecting', generation=None, event_type='evidence_interruption', **fields):
    from alarms import reset_pending_on_failure
    with conn:
        conn.execute('BEGIN IMMEDIATE')
        assert_owner(conn,session,generation)
        conn.execute('''INSERT INTO collection_events(device_id,metric,occurred_at,event_type,message,protocol)
            VALUES (?,?,?,?,?,'opcua')''',(DEVICE_ID,METRIC,stamp(now),event_type,message))
        reset_pending_on_failure(conn,DEVICE_ID,METRIC,session)
        update_in_transaction(conn,session,now,expected_generation=generation,state=state,error=message,**fields)


def read_runtime(conn, now):
    if not table_exists(conn,'opcua_runtime'):
        return None
    cursor=conn.execute('SELECT * FROM opcua_runtime WHERE device_id=?',(DEVICE_ID,))
    row=cursor.fetchone()
    if row is None:
        return None
    result=dict(zip((column[0] for column in cursor.description),row))
    owner=conn.execute('SELECT session_id FROM temperature_alarm_state WHERE device_id=? AND metric=?',(DEVICE_ID,METRIC)).fetchone() if table_exists(conn,'temperature_alarm_state') else None
    superseded=owner is None or owner[0]!=result['session_id']
    result.pop('device_id'); result.pop('session_id')
    result['revised']=json.loads(result['revised']) if result['revised'] else None
    from datetime import datetime
    age=(now-datetime.fromisoformat(result['updated_at'])).total_seconds()
    if superseded or (result['state'] not in ('stopped','failed') and (age<0 or age>5)):
        result['reported_state']=result['state']; result['state']='unknown'
    return result
