"""读取一次温度；通信失败时不输出测量值，以状态码 1 退出。"""

import argparse
import sys

from pymodbus.exceptions import ModbusException

from modbus_reader import SCALE, read_temperature


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--port", type=int, default=15020, help="TCP 端口，默认 15020")
    args = parser.parse_args()
    if not 1024 <= args.port <= 65535:
        parser.error("--port 必须在 1024～65535 之间")

    try:
        raw, temperature = read_temperature(args.port)
        print(f"原始值：{raw}\n倍率：{SCALE}\n温度：{temperature:.1f}℃")
        return 0
    except (OSError, ModbusException) as exc:
        print(f"通信失败（127.0.0.1:{args.port}）：{exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(main())
