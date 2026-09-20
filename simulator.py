"""温度、电流、转速和运行状态四个保持寄存器的 Modbus TCP 教学模拟器。"""

import argparse
from points import POINTS

from pymodbus.datastore import (
    ModbusDeviceContext,
    ModbusSequentialDataBlock,
    ModbusServerContext,
)
from pymodbus.server import StartTcpServer


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--raw", type=int, default=POINTS["temperature"].default_raw, help="温度原始值，默认 653")
    parser.add_argument("--current-raw", type=int, default=POINTS["current"].default_raw, help="电流原始值，默认123，即1.23A")
    parser.add_argument("--speed-raw", type=int, default=POINTS["speed"].default_raw, help="转速原始值，默认1450 rpm")
    parser.add_argument("--running-state-raw", type=int, default=POINTS["running_state"].default_raw, help="运行状态：0停止、1运行；其他uint16用于校验故障注入")
    parser.add_argument("--port", type=int, default=15020, help="TCP 端口，默认 15020")
    args = parser.parse_args()
    if not 0 <= args.raw <= 65535:
        parser.error("--raw 必须在 0～65535 之间（一个无符号 16 位寄存器）")
    if not 0 <= args.current_raw <= 65535:
        parser.error("--current-raw 必须在0～65535之间")
    for name in ("speed_raw", "running_state_raw"):
        if not 0 <= getattr(args, name) <= 65535:
            parser.error(f"--{name.replace('_', '-')} 必须在0～65535之间")
    if not 1024 <= args.port <= 65535:
        parser.error("--port 必须在 1024～65535 之间")

    # PyModbus 3.11.3 的 DeviceContext 会把协议地址加 1。
    # 因此内部索引 1 对应客户端使用的协议地址 0。
    block = ModbusSequentialDataBlock(1, [args.raw, args.current_raw, args.speed_raw, args.running_state_raw])
    device = ModbusDeviceContext(hr=block)
    context = ModbusServerContext(devices={1: device}, single=False)
    print(
        f"启动模拟器：127.0.0.1:{args.port}，设备 ID=1，"
        f"保持寄存器协议地址=0，温度原始值={args.raw}，地址1电流原始值={args.current_raw}，地址2转速原始值={args.speed_raw}，地址3运行状态原始值={args.running_state_raw}；按 Ctrl+C 停止。",
        flush=True,
    )
    StartTcpServer(context=context, address=("127.0.0.1", args.port))


if __name__ == "__main__":
    main()
