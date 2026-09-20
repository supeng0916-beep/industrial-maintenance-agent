"""OPC UA 写端门槛与诊断。源时间判断假设服务器/采集器 UTC 时钟同步。"""
from datetime import datetime, timezone
import json
import math
import time
from alarms import evaluate, reset_pending_on_failure
from storage import initialize
from opcua_runtime import assert_owner, table_exists, update_in_transaction

DEVICE_ID = 'motor-b'
METRIC = 'temperature'


def utc_text(value):
    return value.astimezone(timezone.utc).isoformat(timespec='microseconds') if value else None


def initialize_opcua(conn):
    initialize(conn)
    conn.executescript('''CREATE TABLE IF NOT EXISTS opcua_diagnostics (
        id INTEGER PRIMARY KEY, device_id TEXT NOT NULL, metric TEXT NOT NULL,
        value_json TEXT NOT NULL, variant_type TEXT NOT NULL, status_code INTEGER NOT NULL,
        status_name TEXT NOT NULL, quality TEXT NOT NULL, source_time TEXT, server_time TEXT,
        received_at TEXT NOT NULL, source_freshness TEXT NOT NULL, accepted INTEGER NOT NULL,
        reason TEXT NOT NULL, source_max_age REAL NOT NULL, decision_at TEXT);
        CREATE INDEX IF NOT EXISTS opcua_diagnostic_device ON opcua_diagnostics(device_id,metric,id);
    ''')
    columns={row[1] for row in conn.execute('PRAGMA table_info(opcua_diagnostics)')}
    if 'decision_at' not in columns:
        with conn:
            conn.execute('ALTER TABLE opcua_diagnostics ADD COLUMN decision_at TEXT')


def freshness(source, received, max_age, watermark=None):
    if source is None: return 'missing'
    age=(received-source).total_seconds()
    if age < 0: return 'future'
    if age > max_age: return 'stale'
    if watermark is not None:
        if source == watermark: return 'duplicate'
        if source < watermark: return 'backward'
    return 'fresh'


def event(conn, received, kind, message):
    conn.execute('INSERT INTO collection_events(device_id,metric,occurred_at,event_type,message,protocol) VALUES (?,?,?,?,?,?)',
                 (DEVICE_ID,METRIC,utc_text(received),kind,message,'opcua'))


def diagnostic_json_value(value):
    """保留原始结构；把任意层级的非有限浮点数表示为JSON字符串。"""
    if isinstance(value, float) and not math.isfinite(value):
        return str(value)
    if isinstance(value, (list, tuple)):
        return [diagnostic_json_value(item) for item in value]
    if isinstance(value, dict):
        return {str(key): diagnostic_json_value(item) for key, item in value.items()}
    return value


def save_data_value(conn, data, received_at, *, alarm_session, monotonic_now=None, source_max_age=5, generation=None, notification_identity=None, processing_deadline=None, decision_clock=None):
    if not math.isfinite(source_max_age) or source_max_age <= 0:
        raise ValueError('source_max_age 必须为正有限秒数')
    quality='good' if data.StatusCode.is_good() else 'bad' if data.StatusCode.is_bad() else 'uncertain'
    value=data.Value.Value if data.Value else None
    variant=data.Value.VariantType.name if data.Value else 'Null'
    # JSON 避免 NaN 等非标准数值；原始非有限值以字符串保存诊断。
    serial_value=diagnostic_json_value(value)
    with conn:
        conn.execute('BEGIN IMMEDIATE')
        assert_owner(conn,alarm_session,generation)
        if notification_identity is not None:
            identity=json.dumps(notification_identity,separators=(',',':'))
            inserted=conn.execute('INSERT OR IGNORE INTO opcua_notification_receipts(identity,session_id,generation,received_at) VALUES (?,?,?,?)',
                (identity,alarm_session,generation,utc_text(received_at))).rowcount
            if not inserted:
                conn.execute('UPDATE opcua_runtime SET duplicate_count=duplicate_count+1 WHERE device_id=? AND session_id=?',(DEVICE_ID,alarm_session))
                return dict(accepted=False,reason='duplicate_notification',duplicate=True)
        decision_at=decision_clock() if decision_clock is not None else received_at
        delay_exceeded=processing_deadline is not None and time.monotonic()>processing_deadline
        previous=conn.execute('SELECT source_time FROM measurements WHERE device_id=? AND metric=? AND source_time IS NOT NULL ORDER BY source_time DESC LIMIT 1',(DEVICE_ID,METRIC)).fetchone()
        source=data.SourceTimestamp
        fresh=freshness(source,received_at,source_max_age,datetime.fromisoformat(previous[0]) if previous else None)
        decision_fresh=freshness(source,decision_at,source_max_age)
        decision_rejection=fresh=='fresh' and decision_fresh!='fresh'
        if decision_rejection:
            fresh=decision_fresh
        numeric=variant=='Double' and isinstance(value,(int,float)) and not isinstance(value,bool) and math.isfinite(value)
        reason='notification_processing_delay' if delay_exceeded else quality if quality!='good' else 'invalid_double' if not numeric else fresh+'_at_decision' if decision_rejection else fresh
        accepted=not delay_exceeded and quality=='good' and numeric and fresh=='fresh'
        diagnostic=dict(value_json=json.dumps(serial_value,ensure_ascii=False,default=str,allow_nan=False),variant_type=variant,status_code=data.StatusCode.value,status_name=data.StatusCode.name,quality=quality,source_time=utc_text(source),server_time=utc_text(data.ServerTimestamp),received_at=utc_text(received_at),decision_at=utc_text(decision_at),source_freshness=fresh,accepted=accepted,reason='accepted' if accepted else reason,source_max_age=source_max_age)
        if table_exists(conn,'opcua_runtime'):
            update_in_transaction(conn,alarm_session,decision_at,expected_generation=generation,last_notification_at=received_at,error=None)
        columns=list(diagnostic)
        conn.execute(f"INSERT INTO opcua_diagnostics(device_id,metric,{','.join(columns)}) VALUES ({','.join('?' for _ in range(len(columns)+2))})",(DEVICE_ID,METRIC,*diagnostic.values()))
        if accepted:
            # Source-time continuity is independent of callback delivery speed.
            if previous:
                state=conn.execute('SELECT max_gap_seconds FROM temperature_alarm_state WHERE device_id=? AND metric=?',(DEVICE_ID,METRIC)).fetchone()
                if state and state[0] is not None and (source-datetime.fromisoformat(previous[0])).total_seconds()>state[0]:
                    event(conn,received_at,'evidence_interruption','source_timestamp_gap')
                    reset_pending_on_failure(conn,DEVICE_ID,METRIC,alarm_session)
            mid=conn.execute('''INSERT INTO measurements(device_id,metric,value,unit,collected_at,source_time,quality,protocol)
                VALUES (?,?,?,?,?,?,?,?)''',(DEVICE_ID,METRIC,value,'℃',utc_text(received_at),utc_text(source),'good','opcua')).lastrowid
            evaluate(conn,mid,value,utc_text(received_at),DEVICE_ID,METRIC,alarm_session,time.monotonic() if monotonic_now is None else monotonic_now)
        else:
            event(conn,decision_at,'data_validation_error',reason)
            reset_pending_on_failure(conn,DEVICE_ID,METRIC,alarm_session)
    return diagnostic


def save_communication_failure(conn, received_at, message, *, alarm_session, generation=None):
    with conn:
        conn.execute('BEGIN IMMEDIATE')
        assert_owner(conn,alarm_session,generation)
        event(conn,received_at,'communication_error',message)
        reset_pending_on_failure(conn,DEVICE_ID,METRIC,alarm_session)


def read_opcua_status(conn, now, api_max_age):
    result=dict(communication='unknown',quality='unknown',source_freshness='unknown',eligible=False,reason='no_diagnostic',diagnostic=None)
    if not conn.execute("SELECT 1 FROM sqlite_master WHERE type='table' AND name='opcua_diagnostics'").fetchone(): return result
    row=conn.execute('SELECT * FROM opcua_diagnostics WHERE device_id=? AND metric=? ORDER BY id DESC LIMIT 1',(DEVICE_ID,METRIC)).fetchone()
    failure=conn.execute("SELECT occurred_at FROM collection_events WHERE device_id=? AND metric=? AND event_type='communication_error' ORDER BY occurred_at DESC,id DESC LIMIT 1",(DEVICE_ID,METRIC)).fetchone()
    if row:
        d=dict(row); d['accepted']=bool(d['accepted'])
        source=datetime.fromisoformat(d['source_time']) if d['source_time'] else None
        current=freshness(source,now,min(api_max_age,d['source_max_age']))
        fresh=d['source_freshness'] if current=='fresh' else current
        result.update(communication='success',quality=d['quality'],source_freshness=fresh,eligible=d['accepted'] and fresh=='fresh',reason=d['reason'] if fresh==d['source_freshness'] else fresh,diagnostic=d)
    interruption=conn.execute("SELECT occurred_at,message FROM collection_events WHERE device_id=? AND metric=? AND event_type='evidence_interruption' ORDER BY occurred_at DESC,id DESC LIMIT 1",(DEVICE_ID,METRIC)).fetchone()
    if interruption and (not row or interruption[0]>row['received_at']):
        result.update(eligible=False,reason=interruption[1])
    if failure and (not row or failure[0]>=row['received_at']):
        result.update(communication='failure',eligible=False,reason='communication_error')
    return result
