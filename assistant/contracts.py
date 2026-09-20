"""共享设备白名单、参数边界和可序列化错误契约。"""
from datetime import datetime, timedelta, timezone
from points import POINTS

DEVICES = {
    'motor-a': {'id':'motor-a','name':'模拟电机 A','protocol':'modbus_tcp','metrics':tuple(POINTS)},
    'motor-b': {'id':'motor-b','name':'模拟电机 B','protocol':'opcua','metrics':('temperature',)},
    # 合成数据集历史回放；指标与单位见 docs/datasets/ai4i-2020/README.md。
    'motor-c': {'id':'motor-c','name':'AI4I 2020 数控机床（历史回放）','protocol':'replay',
                'metrics':('temperature','air_temperature','speed','torque','tool_wear','running_state')},
}

class QueryError(Exception):
    def __init__(self, code, message, status=422):
        super().__init__(message)
        self.code, self.message, self.status = code, message, status


def utc_text(value):
    return value.astimezone(timezone.utc).isoformat(timespec='microseconds')


def parse_time(value):
    try:
        if not isinstance(value, str): raise ValueError()
        parsed = datetime.fromisoformat(value)
        if parsed.tzinfo is None or parsed.utcoffset() is None: raise ValueError()
        return parsed.astimezone(timezone.utc)
    except (ValueError, OverflowError):
        raise QueryError('invalid_time', '时间必须为带时区的 ISO 8601 日期时间') from None


def check_device(device_id, metric=None):
    if not isinstance(device_id,str) or device_id not in DEVICES:
        raise QueryError('device_not_found','未知设备',404)
    if metric is not None and (not isinstance(metric,str) or metric not in DEVICES[device_id]['metrics']):
        raise QueryError('invalid_metric', '此设备支持的指标：' + '、'.join(DEVICES[device_id]['metrics']))
    return DEVICES[device_id]


def time_range(start, end):
    first, last = parse_time(start), parse_time(end)
    if last < first or last - first > timedelta(hours=24):
        raise QueryError('invalid_range','start不得晚于end，范围不得超过24小时')
    return utc_text(first), utc_text(last)


def check_limit(limit):
    if type(limit) is not int or not 1 <= limit <= 1000:
        raise QueryError('invalid_parameters','limit必须为1～1000的整数')
    return limit
