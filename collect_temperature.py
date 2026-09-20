"""批量采集温度、电流、转速与运行状态到 SQLite；失败只写事件，下个周期重新尝试。"""

import argparse
from contextlib import closing
from datetime import datetime, timezone
import math
import sqlite3
import sys
import time

from pymodbus.exceptions import ModbusException

from alarms import initialize_alarms
from modbus_reader import DataValidationError, read_points
from storage import DEFAULT_DB, initialize, open_database, save_round_failure, save_round


def utc_now():
    return datetime.now(timezone.utc).isoformat(timespec="microseconds")


def collect(conn, port, interval, count, alarm_session):
    attempts = failures = 0
    while count == 0 or attempts < count:
        started = time.monotonic()
        attempts += 1
        try:
            values = read_points(port)
        except (OSError, ModbusException, DataValidationError) as exc:
            failures += 1
            timestamp = utc_now()
            message = f"127.0.0.1:{port}：{exc}"
            invalid = isinstance(exc, DataValidationError)
            event_type = "data_validation_error" if invalid else "communication_error"
            label = "数据校验失败" if invalid else "通信失败"
            save_round_failure(conn, timestamp, message, alarm_session=alarm_session, event_type=event_type)
            print(f"{timestamp} 第{attempts}次 {label}：{message}", file=sys.stderr, flush=True)
        else:
            timestamp = utc_now()
            save_round(conn, values, timestamp,
                             alarm_session=alarm_session, monotonic_now=time.monotonic())
            print(f"{timestamp} 第{attempts}次 已保存：温度={values['temperature']:.1f}℃ 电流={values['current']:.2f}A 转速={values['speed']:.0f}rpm 运行状态={values['running_state']:.0f}", flush=True)
        if count == 0 or attempts < count:
            # 以每轮起点计算间隔；慢请求不排队补采，不在事务内等待。
            time.sleep(max(0, interval - (time.monotonic() - started)))
    print(f"采集结束：尝试={attempts} 成功={attempts - failures} 失败={failures}", flush=True)
    return 1 if failures else 0


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--port", type=int, default=15020)
    parser.add_argument("--db", default=DEFAULT_DB, help="SQLite 文件路径")
    parser.add_argument("--interval", type=float, default=1, help="采集间隔秒数，默认 1")
    parser.add_argument("--count", type=int, default=0, help="尝试次数（失败也计数），0 表示持续")
    args = parser.parse_args()
    if not 1024 <= args.port <= 65535:
        parser.error("--port 必须在 1024～65535 之间")
    if not math.isfinite(args.interval) or not 0 < args.interval <= 5 / 1.5:
        parser.error("--interval 必须为大于0、不超过10/3的有限秒数；持续告警容忍1.5倍间隔且不超过5秒")
    if args.count < 0:
        parser.error("--count 必须为非负整数")
    try:
        with closing(open_database(args.db)) as conn:
            initialize(conn)
            alarm_session = initialize_alarms(conn, interval=args.interval)
            return collect(conn, args.port, args.interval, args.count, alarm_session)
    except (OSError, sqlite3.Error) as exc:
        print(f"数据库初始化或写入失败（{args.db}）：{exc}；采集已停止。", file=sys.stderr)
        return 1
    except KeyboardInterrupt:
        print("采集已停止，已提交的历史保留。", file=sys.stderr)
        return 130


if __name__ == "__main__":
    sys.exit(main())
