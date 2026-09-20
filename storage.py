"""SQLite 数据契约与短事务；连接由调用者关闭。"""

from pathlib import Path
import sqlite3
import math
import time

from points import POINTS
from alarms import evaluate, reset_pending_on_failure

DEFAULT_DB = "data/measurements.sqlite3"
DEVICE_ID = "motor-a"
METRIC = "temperature"
PROTOCOL = "modbus_tcp"


def open_database(path):
    Path(path).parent.mkdir(parents=True, exist_ok=True)
    return sqlite3.connect(path, timeout=2)


def initialize(conn):
    conn.executescript("""
        CREATE TABLE IF NOT EXISTS measurements (
            id INTEGER PRIMARY KEY,
            device_id TEXT NOT NULL,
            metric TEXT NOT NULL,
            value REAL NOT NULL,
            unit TEXT NOT NULL,
            collected_at TEXT NOT NULL,
            source_time TEXT,
            quality TEXT NOT NULL,
            protocol TEXT NOT NULL
        );
        CREATE INDEX IF NOT EXISTS measurements_device_metric_time
            ON measurements(device_id, metric, collected_at);
        CREATE TABLE IF NOT EXISTS collection_events (
            id INTEGER PRIMARY KEY,
            device_id TEXT NOT NULL,
            metric TEXT NOT NULL,
            occurred_at TEXT NOT NULL,
            event_type TEXT NOT NULL,
            message TEXT NOT NULL,
            protocol TEXT NOT NULL
        );
        CREATE INDEX IF NOT EXISTS events_device_metric_time
            ON collection_events(device_id, metric, occurred_at);
    """)


def insert_measurement(conn, metric, value, collected_at):
    return conn.execute("""INSERT INTO measurements
        (device_id, metric, value, unit, collected_at, source_time, quality, protocol)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
        (DEVICE_ID, metric, value, POINTS[metric].unit, collected_at, None, "good", PROTOCOL)).lastrowid


def save_measurement(conn, value, collected_at, *, evaluate_alarm=False, alarm_session=None, monotonic_now=None):
    """保留单温度历史/测试入口；新版采集器使用save_round。"""
    if not math.isfinite(value):
        raise ValueError("温度必须为有限数值")
    with conn:
        measurement_id = insert_measurement(conn, METRIC, value, collected_at)
        if evaluate_alarm:
            evaluate(conn, measurement_id, value, collected_at, DEVICE_ID, METRIC, alarm_session,
                     time.monotonic() if monotonic_now is None else monotonic_now)


def save_round(conn, values, collected_at, *, alarm_session, monotonic_now=None):
    if set(values) != set(POINTS) or any(not math.isfinite(v) for v in values.values()):
        raise ValueError('一轮必须包含四个有限数值：temperature、current、speed、running_state')
    for metric, point in POINTS.items():
        if point.allowed_raw is not None and values[metric] not in point.allowed_raw:
            raise ValueError(f'{metric} 必须为 {point.allowed_raw}，实际值={values[metric]}')
    with conn:
        temperature_id = insert_measurement(conn, METRIC, values[METRIC], collected_at)
        evaluate(conn, temperature_id, values[METRIC], collected_at, DEVICE_ID, METRIC, alarm_session,
                 time.monotonic() if monotonic_now is None else monotonic_now)
        # 任意后续写入失败时温度、告警、pending一起回滚。
        for metric in POINTS:
            if metric != METRIC:
                insert_measurement(conn, metric, values[metric], collected_at)


def save_failure(conn, occurred_at, message, *, alarm_session=None, metrics=(METRIC,), event_type="communication_error"):
    with conn:
        for metric in metrics:
            conn.execute("""INSERT INTO collection_events
                (device_id, metric, occurred_at, event_type, message, protocol)
                VALUES (?, ?, ?, ?, ?, ?)""",
                (DEVICE_ID, metric, occurred_at, event_type, message, PROTOCOL))
        reset_pending_on_failure(conn, DEVICE_ID, METRIC, alarm_session)


def save_round_failure(conn, occurred_at, message, *, alarm_session, event_type="communication_error"):
    save_failure(conn, occurred_at, message, alarm_session=alarm_session, metrics=tuple(POINTS), event_type=event_type)


def query_history(conn, device_id, metric, limit, events=False):
    if not 1 <= limit <= 1000:
        raise ValueError("查询条数必须在 1～1000 之间")
    # 表名和时间列来自固定选项，所有外部输入使用 SQL 参数。
    table, time_column = ("collection_events", "occurred_at") if events else (
        "measurements", "collected_at"
    )
    conn.row_factory = sqlite3.Row
    rows = conn.execute(f"""
        SELECT * FROM {table} WHERE device_id = ? AND metric = ?
        ORDER BY {time_column} DESC, id DESC LIMIT ?
    """, (device_id, metric, limit)).fetchall()
    return [dict(row) for row in rows]


def open_readonly_database(path):
    """每个请求独立连接；文件不存在时失败，不建库、不建表。"""
    uri = Path(path).resolve().as_uri() + "?mode=ro"
    conn = sqlite3.connect(uri, uri=True, timeout=2)
    conn.row_factory = sqlite3.Row
    return conn


def latest_observations(conn, device_id, metric):
    # 两次 SELECT 使用同一短只读快照，防止中间插入造成不一致。
    if not conn.in_transaction:
        conn.execute("BEGIN")
    conn.row_factory = sqlite3.Row
    row = conn.execute("""SELECT * FROM measurements WHERE device_id=? AND metric=? AND quality='good'
        ORDER BY collected_at DESC, id DESC LIMIT 1""", (device_id, metric)).fetchone()
    samples = [dict(row)] if row else []
    failure = conn.execute("""
        SELECT * FROM collection_events
        WHERE device_id = ? AND metric = ? AND event_type IN (?, ?)
        ORDER BY occurred_at DESC, id DESC LIMIT 1
    """, (device_id, metric, "communication_error", "data_validation_error")).fetchone()
    return (samples[0] if samples else None, dict(failure) if failure else None)


def history_between(conn, device_id, metric, start, end, limit):
    # 采集器存储的是固定微秒精度的 UTC ISO 文本；参数转换为同一格式后可按索引比较。
    rows = conn.execute("""
        SELECT * FROM measurements
        WHERE device_id = ? AND metric = ? AND collected_at >= ? AND collected_at <= ?
        ORDER BY collected_at ASC, id ASC LIMIT ?
    """, (device_id, metric, start, end, limit)).fetchall()
    return [dict(row) for row in rows]
