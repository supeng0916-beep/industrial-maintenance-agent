"""仅针对本地教学模拟器：主动读取、订阅、设温。"""

import argparse
import asyncio
from datetime import datetime, timezone
import math
import sys

from asyncua import Client, ua

from .common import describe, emit, endpoint, port_number, temperature_node, timestamp


class TemperatureHandler:
    def datachange_notification(self, node, value, data):
        emit("notification", **describe(node, data.monitored_item.Value),
             ReceivedAt=timestamp(datetime.now(timezone.utc)))

    def status_change_notification(self, status):
        emit("subscription_status", status=str(status))


async def run(args):
    async with Client(endpoint(args.port), timeout=4, auto_reconnect=False) as client:
        node = await temperature_node(client)
        if args.command == "read":
            value = await node.read_data_value(raise_on_bad_status=False)
            emit("read", **describe(node, value))
        elif args.command == "set-temperature":
            # 显式 Double；只发送值，不把设温客户端时钟冒充设备源时间。
            value = ua.DataValue(ua.Variant(float(args.value), ua.VariantType.Double))
            await node.write_value(value)
            emit("local_lab_write", NodeId=node.nodeid.to_string(), Value=args.value, DataType="Double")
        else:
            subscription = await client.create_subscription(250, TemperatureHandler())
            try:
                # 2.0.1 无额外过滤器时默认 StatusValue：时间戳单独变化不触发。
                await subscription.subscribe_data_change(node, queuesize=10, sampling_interval=100)
                emit("subscribed", NodeId=node.nodeid.to_string(), monitored_items=1,
                     requested_publishing_ms=250, requested_sampling_ms=100, requested_queue_size=10,
                     trigger="StatusValue")
                await asyncio.Event().wait()
            finally:
                await subscription.delete()
                emit("subscription_deleted")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest="command", required=True)
    for command in ("read", "subscribe", "set-temperature"):
        subparser = commands.add_parser(command)
        subparser.add_argument("--port", type=port_number, default=4840)
        if command == "set-temperature":
            subparser.add_argument("value", type=float, help="仅设定本地教学模拟器温度，Double工程值℃")
    args = parser.parse_args()
    if args.command == "set-temperature" and not math.isfinite(args.value):
        parser.error("温度必须是有限数值")
    try:
        asyncio.run(run(args))
    except KeyboardInterrupt:
        return 130
    except (OSError, TimeoutError, ua.UaError, ValueError) as exc:
        print(f"OPC UA 实验通信失败：{exc}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
