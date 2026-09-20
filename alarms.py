"""单测点回差告警。教学阈值；写入仅由采集器调用，查询不建表。"""

import math
import sqlite3
import uuid

CONFIRM_SECONDS = 5.0

TRIGGER_ABOVE = 80.0
RECOVER_BELOW = 78.0
HISTORY_LIMIT = 20


def initialize_alarms(conn, interval=1, device_id="motor-a", metric="temperature"):
    if not math.isfinite(interval) or not 0 < interval <= 5 / 1.5:
        raise ValueError("持续告警要求 0 < interval ≤ 10/3 秒，1.5倍间隔不得超过5秒")
    session = str(uuid.uuid4())
    # 仅创建状态容器，不回放历史测量；首次新样本到来前 evaluated_id 为 NULL。
    conn.executescript("""
        CREATE TABLE IF NOT EXISTS temperature_alarm_state (
            device_id TEXT NOT NULL,
            metric TEXT NOT NULL,
            evaluated_id INTEGER,
            PRIMARY KEY(device_id, metric)
        );
        CREATE TABLE IF NOT EXISTS temperature_alarms (
            id INTEGER PRIMARY KEY,
            device_id TEXT NOT NULL,
            metric TEXT NOT NULL,
            started_at TEXT NOT NULL,
            trigger_measurement_id INTEGER NOT NULL,
            trigger_value REAL NOT NULL,
            trigger_above REAL NOT NULL,
            recover_below REAL NOT NULL,
            recovered_at TEXT,
            recovery_measurement_id INTEGER,
            recovery_value REAL,
            CHECK ((recovered_at IS NULL AND recovery_measurement_id IS NULL AND recovery_value IS NULL)
                OR (recovered_at IS NOT NULL AND recovery_measurement_id IS NOT NULL AND recovery_value IS NOT NULL))
        );
        CREATE UNIQUE INDEX IF NOT EXISTS one_active_temperature_alarm
            ON temperature_alarms(device_id, metric) WHERE recovered_at IS NULL;
        CREATE INDEX IF NOT EXISTS temperature_alarm_history
            ON temperature_alarms(device_id, metric, id);
    """)

    # 迁移只在写端进行，旧记录默认0秒，保留即时触发原意。
    with conn:
        conn.execute('BEGIN IMMEDIATE')
        additions = {
            'temperature_alarm_state': {
                'session_id': 'TEXT', 'confirm_seconds': 'REAL NOT NULL DEFAULT 0',
                'max_gap_seconds': 'REAL', 'pending_at': 'TEXT', 'pending_id': 'INTEGER',
                'pending_value': 'REAL', 'pending_mono': 'REAL', 'last_mono': 'REAL',
                'elapsed_seconds': 'REAL NOT NULL DEFAULT 0'},
            'temperature_alarms': {
                'confirm_seconds': 'REAL NOT NULL DEFAULT 0', 'observed_seconds': 'REAL',
                'max_gap_seconds': 'REAL', 'first_exceeded_at': 'TEXT',
                'first_exceeded_measurement_id': 'INTEGER', 'first_exceeded_value': 'REAL'}
        }
        for table, columns in additions.items():
            existing = {r[1] for r in conn.execute(f'PRAGMA table_info({table})')}
            for name, definition in columns.items():
                if name not in existing:
                    conn.execute(f'ALTER TABLE {table} ADD COLUMN {name} {definition}')
        conn.execute("INSERT OR IGNORE INTO temperature_alarm_state(device_id, metric) VALUES (?, ?)", (device_id, metric))
        conn.execute("""UPDATE temperature_alarm_state SET session_id=?, confirm_seconds=?, max_gap_seconds=?,
            evaluated_id=NULL, pending_at=NULL, pending_id=NULL, pending_value=NULL,
            pending_mono=NULL, last_mono=NULL, elapsed_seconds=0
            WHERE device_id=? AND metric=?""", (session, CONFIRM_SECONDS, interval * 1.5, device_id, metric))
    return session


def evaluate(conn, measurement_id, value, collected_at, device_id, metric, session, monotonic_now):
    """写测量已取得写锁。状态只存在事务内的DB中，回滚不会留下内存计时副作用。"""
    if not math.isfinite(monotonic_now):
        raise ValueError('单调时间必须有限')
    cursor = conn.execute('SELECT * FROM temperature_alarm_state WHERE device_id=? AND metric=?', (device_id, metric))
    row = cursor.fetchone()
    state = dict(zip([col[0] for col in cursor.description], row)) if row else None
    if state is None or not session or state.get('session_id') != session:
        raise sqlite3.OperationalError('采集会话已失效，请停止旧采集器；同库仅运行一个持续告警采集器')
    active = conn.execute("""SELECT id, recover_below FROM temperature_alarms
        WHERE device_id=? AND metric=? AND recovered_at IS NULL""", (device_id, metric)).fetchone()
    pending_at = pending_id = pending_value = pending_mono = last_mono = None
    elapsed = 0.0
    if active is not None:
        if value < active[1]:
            conn.execute("""UPDATE temperature_alarms SET recovered_at=?, recovery_measurement_id=?, recovery_value=?
                WHERE id=?""", (collected_at, measurement_id, value, active[0]))
    elif value > TRIGGER_ABOVE:
        gap = monotonic_now - state['last_mono'] if state['last_mono'] is not None else None
        continuous = state['pending_mono'] is not None and gap is not None and 0 <= gap <= state['max_gap_seconds']
        pending_at = state['pending_at'] if continuous else collected_at
        pending_id = state['pending_id'] if continuous else measurement_id
        pending_value = state['pending_value'] if continuous else value
        pending_mono = state['pending_mono'] if continuous else monotonic_now
        last_mono = monotonic_now
        elapsed = monotonic_now - pending_mono
        if elapsed >= state['confirm_seconds']:
            conn.execute("""INSERT INTO temperature_alarms
                (device_id, metric, started_at, trigger_measurement_id, trigger_value, trigger_above, recover_below,
                 confirm_seconds, first_exceeded_at, first_exceeded_measurement_id, first_exceeded_value,
                 observed_seconds, max_gap_seconds)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                (device_id, metric, collected_at, measurement_id, value, TRIGGER_ABOVE, RECOVER_BELOW,
                 state['confirm_seconds'], pending_at, pending_id, pending_value, elapsed, state['max_gap_seconds']))
            pending_at = pending_id = pending_value = pending_mono = last_mono = None
            elapsed = 0.0
    conn.execute("""UPDATE temperature_alarm_state SET evaluated_id=?, pending_at=?, pending_id=?, pending_value=?,
        pending_mono=?, last_mono=?, elapsed_seconds=? WHERE device_id=? AND metric=?""",
        (measurement_id, pending_at, pending_id, pending_value, pending_mono, last_mono, elapsed, device_id, metric))


def reset_pending_on_failure(conn, device_id, metric, session=None):
    # 历史数据库和即时告警库仍可记录失败，不要求先迁移。
    columns = {r[1] for r in conn.execute('PRAGMA table_info(temperature_alarm_state)')}
    if 'pending_mono' in columns:
        if session is not None:
            state = conn.execute('SELECT session_id FROM temperature_alarm_state WHERE device_id=? AND metric=?', (device_id, metric)).fetchone()
            if state is None or state[0] != session:
                raise sqlite3.OperationalError('采集会话已失效，旧采集器不能修改新会话状态')
        conn.execute("""UPDATE temperature_alarm_state SET evaluated_id=NULL, pending_at=NULL, pending_id=NULL,
            pending_value=NULL, pending_mono=NULL, last_mono=NULL, elapsed_seconds=0
            WHERE device_id=? AND metric=?""", (device_id, metric))


def read_alarms(conn, device_id, metric, sample, status):
    """使用调用方的同一个只读快照；当前未知与持久化未解除告警是两个维度。"""
    tables = {r[0] for r in conn.execute("SELECT name FROM sqlite_master WHERE type='table'")}
    result = {'enabled': False, 'current': 'not_enabled', 'active': None,
              'history': [], 'total': 0, 'limit': HISTORY_LIMIT,
              'evaluated_measurement_id': None, 'pending': None,
              'rule': {'trigger_above': TRIGGER_ABOVE, 'recover_below': RECOVER_BELOW, 'unit': '℃', 'teaching_only': True}}
    if not {'temperature_alarm_state', 'temperature_alarms'} <= tables:
        return result
    state = conn.execute('SELECT * FROM temperature_alarm_state WHERE device_id=? AND metric=?',
                         (device_id, metric)).fetchone()
    if state is None:
        return result
    state = dict(state)
    result['enabled'] = True
    result['evaluated_measurement_id'] = state['evaluated_id']
    result['rule'].update(confirm_seconds=state.get('confirm_seconds', 0), max_gap_seconds=state.get('max_gap_seconds'))
    if state.get('pending_at') is not None:
        result['pending'] = {'first_exceeded_at': state['pending_at'], 'first_exceeded_measurement_id': state['pending_id'],
                             'first_exceeded_value': state['pending_value'], 'elapsed_seconds': state['elapsed_seconds']}
    rows = conn.execute('SELECT * FROM temperature_alarms WHERE device_id=? AND metric=? ORDER BY id DESC LIMIT ?',
                        (device_id, metric, HISTORY_LIMIT)).fetchall()
    result['history'] = [dict(row) for row in rows]
    active = conn.execute('SELECT * FROM temperature_alarms WHERE device_id=? AND metric=? AND recovered_at IS NULL',
                          (device_id, metric)).fetchone()
    result['active'] = dict(active) if active else None
    result['total'] = conn.execute('SELECT count(*) FROM temperature_alarms WHERE device_id=? AND metric=?',
                                   (device_id, metric)).fetchone()[0]
    known = (sample is not None and sample['id'] == state['evaluated_id'] and sample['quality'] == 'good'
             and status['last_attempt_status'] == 'success' and status['is_stale'] is False
             and status['data_age_seconds'] >= 0)
    if result['pending'] and status['data_age_seconds'] is not None and status['data_age_seconds'] > state['max_gap_seconds']:
        known = False
    result['current'] = ('active' if active else 'pending' if result['pending'] else 'clear') if known else 'unknown'
    return result
