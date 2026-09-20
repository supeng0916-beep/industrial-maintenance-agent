"""HTTP与业务工具共享的事实拼装；连接和快照由调用方拥有。"""
from alarms import read_alarms
from opcua_storage import read_opcua_status
from opcua_runtime import read_runtime
from replay_ai4i import DATASET_INFO, DEVICE_ID as REPLAY_DEVICE, FAULT_EVENT_TYPE
from storage import METRIC, latest_observations, query_history
from .contracts import utc_text, parse_time

REPLAY_NOTE = ('合成数据集历史回放：时间为回放时刻，非原始采集时间；'
               '故障标注来自数据集自身，本系统不做再判定。')


def read_replay_status(conn, limit=5):
    """回放设备的来源声明与最近故障标注；事件按 occurred_at 倒序有界读取。"""
    faults = conn.execute(
        """SELECT occurred_at, message FROM collection_events
           WHERE device_id = ? AND event_type = ?
           ORDER BY occurred_at DESC, id DESC LIMIT ?""",
        (REPLAY_DEVICE, FAULT_EVENT_TYPE, limit)).fetchall()
    total = conn.execute(
        """SELECT count(*) FROM collection_events
           WHERE device_id = ? AND event_type = ?""",
        (REPLAY_DEVICE, FAULT_EVENT_TYPE)).fetchone()[0]
    return {'mode': 'historical_replay', 'dataset': DATASET_INFO,
            'note': REPLAY_NOTE, 'faults': [dict(row) for row in faults],
            'faults_total': total}

def observation_status(sample, failure, now, stale_after_seconds):
    success_at = parse_time(sample["collected_at"]) if sample else None
    failure_at = parse_time(failure["occurred_at"]) if failure else None
    if success_at is not None and (failure_at is None or success_at > failure_at):
        attempt_status, attempt_at = "success", success_at
    elif failure_at is not None and (success_at is None or failure_at > success_at):
        attempt_status, attempt_at = "failure", failure_at
    else:
        # 两种记录同刻时没有跨表顺序证据，保守返回 unknown。
        attempt_status, attempt_at = "unknown", success_at
    age = (now - success_at).total_seconds() if success_at else None
    return {
        "has_data": sample is not None,
        "last_attempt_status": attempt_status,
        "last_attempt_at": utc_text(attempt_at) if attempt_at else None,
        "last_success_at": utc_text(success_at) if success_at else None,
        "last_failure_type": failure["event_type"] if failure else None,
        "last_failure_message": failure["message"] if failure else None,
        "last_failure_at": utc_text(failure_at) if failure_at else None,
        "data_age_seconds": age,
        "is_stale": age > stale_after_seconds if age is not None else None,
        "checked_at": utc_text(now),
        "stale_after_seconds": stale_after_seconds,
    }


def latest_metric(conn, device_id, metric, checked, stale_after_seconds):
    sample, failure = latest_observations(conn, device_id, metric)
    status = observation_status(sample, failure, checked, stale_after_seconds)
    opcua = None
    if device_id == 'motor-b':
        opcua = read_opcua_status(conn, checked, stale_after_seconds)
        diagnostic = opcua['diagnostic']
        runtime = read_runtime(conn, checked)
        opcua['runtime'] = runtime
        if runtime is not None:
            current_generation = diagnostic is not None and diagnostic['received_at'] == runtime['last_notification_at']
            if runtime['state'] not in ('reading', 'subscribed') or not current_generation:
                opcua.update(eligible=False, reason='awaiting_notification' if runtime['state'] in ('reading', 'subscribed') else 'collector_' + runtime['state'])
        threshold = min(stale_after_seconds, diagnostic['source_max_age']) if diagnostic else stale_after_seconds
        age = (checked - parse_time(sample['source_time'])).total_seconds() if sample and sample['source_time'] else None
        status.update(data_age_seconds=age, is_stale=(age < 0 or age > threshold) if age is not None else None,
                      stale_after_seconds=threshold)
        if diagnostic and (not failure or diagnostic['received_at'] >= failure['occurred_at']):
            status.update(last_attempt_status='success' if diagnostic['accepted'] else 'failure',
                          last_attempt_at=diagnostic['received_at'])
        if not opcua['eligible'] and status['last_attempt_status'] == 'success':
            status['last_attempt_status'] = 'unknown'

    # 导入/旧库可能含不合格measurement；保留最后good值，另列最新存储证据。
    latest_rows = query_history(conn, device_id, metric, 1)
    rejected = latest_rows[0] if latest_rows and latest_rows[0]['quality'] != 'good' else None
    if rejected and (status['last_attempt_at'] is None or parse_time(rejected['collected_at']) >= parse_time(status['last_attempt_at'])):
        status.update(last_attempt_status='unknown', last_attempt_at=rejected['collected_at'])
        if opcua is not None:
            opcua.update(eligible=False, reason='stored_quality_rejected')
    alarm = read_alarms(conn, device_id, METRIC, sample, status) if metric == METRIC else None
    replay = read_replay_status(conn) if device_id == REPLAY_DEVICE else None
    return {"device_id": device_id, "metric": metric, "measurement": sample,
        "status": status, "alarm": alarm,
        **({"latest_stored_record": rejected} if rejected else {}),
        **({"opcua": opcua} if opcua is not None else {}),
        **({"replay": replay} if replay is not None else {})}

