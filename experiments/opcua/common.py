"""独立本地教学实验的端点、节点与输出约定。"""

import argparse
from datetime import timezone
import json

from asyncua import ua

NAMESPACE_URI = "urn:industrial-maintenance:opcua-lab"
TEMPERATURE_ID = "MotorA.Temperature"


def port_number(value):
    port = int(value)
    if not 1024 <= port <= 65535:
        raise argparse.ArgumentTypeError("端口必须在1024～65535之间")
    return port


def endpoint(port):
    return f"opc.tcp://127.0.0.1:{port}/opcua-lab/"


async def temperature_node(client):
    index = await client.get_namespace_index(NAMESPACE_URI)
    return client.get_node(ua.NodeId(TEMPERATURE_ID, index))


def timestamp(value):
    return value.astimezone(timezone.utc).isoformat() if value else None


def describe(node, value):
    return {
        "NodeId": node.nodeid.to_string(),
        "Value": value.Value.Value if value.Value else None,
        "DataType": value.Value.VariantType.name if value.Value else None,
        "StatusCode": value.StatusCode.name if value.StatusCode else None,
        "StatusCodeValue": value.StatusCode.value if value.StatusCode else None,
        "SourceTimestamp": timestamp(value.SourceTimestamp),
        "ServerTimestamp": timestamp(value.ServerTimestamp),
        "UnitConvention": "℃（文档约定，无EngineeringUnits属性）",
    }


def emit(event, **fields):
    print(json.dumps({"event": event, **fields}, ensure_ascii=False), flush=True)
