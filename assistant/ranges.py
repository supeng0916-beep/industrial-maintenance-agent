"""Bounded detail queries and complete aggregates within a caller-owned snapshot.

The caller validates device/metric, canonical UTC bounds, status and limit,
opens the read-only connection with sqlite3.Row, and owns its transaction.
"""

from points import POINTS


_MEASUREMENT_WHERE = '''device_id = ? AND metric = ?
    AND collected_at >= ? AND collected_at <= ? AND quality = 'good' '''
_ALARM_OVERLAP = '''device_id = ? AND started_at <= ?
    AND (recovered_at IS NULL OR recovered_at >= ?)'''


def metric_history(conn, device_id, metric, start, end, limit):
    """Aggregate all recorded good samples; limit only the ascending details."""
    parameters = (device_id, metric, start, end)
    is_enum = POINTS[metric].allowed_raw is not None
    # Enum codes have no physical ordering; never report their min/max.
    extrema = 'NULL AS min, NULL AS max' if is_enum else 'MIN(value) AS min, MAX(value) AS max'
    statistics = dict(conn.execute(f'''
        SELECT COUNT(*) AS count, {extrema},
            MIN(collected_at) AS first_collected_at,
            MAX(collected_at) AS last_collected_at
        FROM measurements WHERE {_MEASUREMENT_WHERE}
    ''', parameters).fetchone())
    statistics['kind'] = 'enum' if is_enum else 'numeric'
    if is_enum:
        states = conn.execute(f'''
            SELECT value, COUNT(*) AS count FROM measurements
            WHERE {_MEASUREMENT_WHERE} GROUP BY value ORDER BY value
        ''', parameters).fetchall()
        statistics['state_counts'] = [
            {'value': row['value'], 'label': {0: 'stopped', 1: 'running'}.get(row['value'], 'undefined'),
             'count': row['count']} for row in states
        ]
    points = [dict(row) for row in conn.execute(f'''
        SELECT * FROM measurements WHERE {_MEASUREMENT_WHERE}
        ORDER BY collected_at ASC, id ASC LIMIT ?
    ''', (*parameters, limit))]
    return {
        'device_id': device_id, 'metric': metric, 'unit': POINTS[metric].unit,
        'start': start, 'end': end, 'time_basis': 'collected_at', 'interval': 'closed',
        'statistics': statistics, 'points': points, 'returned_count': len(points),
        'limit': limit, 'truncated': statistics['count'] > len(points),
        'limitations': [
            '统计只覆盖查询范围内已记录且quality=good的有效样本；最小值和最大值不是设备实际物理极值。',
            '首末观测时间不证明整个区间连续采集；未观测时段的数值和缺口完整率未知。',
            '未按固定采样频率推算丢样数量或完整率；订阅通知不保证等间隔。',
        ],
    }


def alarm_history(conn, device_id, start, end, status, limit):
    """List overlaps; history_available means the table exists, not rule enablement."""
    result = {
        'device_id': device_id, 'start': start, 'end': end, 'status': status,
        'history_available': False, 'items': [], 'total': 0, 'matched_active_count': 0,
        'device_total': 0, 'device_active_count': 0, 'returned_count': 0,
        'limit': limit, 'truncated': False,
        'range_semantics': {
            'interval': 'closed',
            'overlap': 'started_at <= end AND (recovered_at IS NULL OR recovered_at >= start)',
            'status_basis': 'stored_recovery_state_at_checked_at',
            'description': '按告警持续区间与查询闭区间相交筛选；status依据检查时记录是否已恢复，不推断查询时段内的状态。',
            'total': '通过时间范围与status筛选的完整匹配条数',
            'matched_active_count': '完整匹配结果中记录仍未恢复的数量',
            'device_counts': '本设备全历史告警条数与检查时记录未恢复数量，不受范围或status筛选影响',
        },
        'limitations': ['告警是已记录规则判定；未解除记录不证明设备此刻仍超温，缺口期间状态未知。'],
    }
    exists = conn.execute("SELECT 1 FROM sqlite_master WHERE type='table' AND name='temperature_alarms'").fetchone()
    if exists is None:
        return result
    result['history_available'] = True
    device_counts = conn.execute('''
        SELECT COUNT(*) AS device_total,
            COALESCE(SUM(recovered_at IS NULL), 0) AS device_active_count
        FROM temperature_alarms WHERE device_id = ?
    ''', (device_id,)).fetchone()
    result.update(dict(device_counts))
    status_clause = {
        'all': '', 'active': ' AND recovered_at IS NULL',
        'recovered': ' AND recovered_at IS NOT NULL',
    }[status]
    where = _ALARM_OVERLAP + status_clause
    parameters = (device_id, end, start)
    counts = conn.execute(f'''
        SELECT COUNT(*) AS total,
            COALESCE(SUM(recovered_at IS NULL), 0) AS matched_active_count
        FROM temperature_alarms WHERE {where}
    ''', parameters).fetchone()
    result.update(dict(counts))
    # SELECT * deliberately preserves legacy evidence: no invented duration.
    result['items'] = [dict(row) for row in conn.execute(f'''
        SELECT * FROM temperature_alarms WHERE {where}
        ORDER BY started_at DESC, id DESC LIMIT ?
    ''', (*parameters, limit))]
    result['returned_count'] = len(result['items'])
    result['truncated'] = result['total'] > result['returned_count']
    return result
