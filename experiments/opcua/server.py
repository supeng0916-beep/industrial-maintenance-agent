"""仅限本机、无认证加密的 OPC UA 教学模拟器。"""

import argparse
import asyncio
import sys

from asyncua import Server, ua

from .common import NAMESPACE_URI, TEMPERATURE_ID, emit, endpoint, port_number


async def run(port, extra_namespace=False):
    server = Server()
    await server.init()
    server.set_endpoint(endpoint(port))
    server.set_server_name("本地 OPC UA 温度教学模拟器")
    server.set_security_policy([ua.SecurityPolicyType.NoSecurity])
    server.set_identity_tokens([ua.AnonymousIdentityToken])
    if extra_namespace:
        await server.register_namespace("urn:industrial-maintenance:opcua-lab:padding")
    index = await server.register_namespace(NAMESPACE_URI)
    motor = await server.nodes.objects.add_object(ua.NodeId("MotorA", index), ua.QualifiedName("MotorA", index))
    temperature = await motor.add_variable(
        ua.NodeId(TEMPERATURE_ID, index), ua.QualifiedName("Temperature", index),
        ua.Variant(65.3, ua.VariantType.Double),
    )
    await temperature.set_writable()
    # 在服务端生成初始源时间；之后客户端只写值，不伪造源时间。
    await temperature.write_value(65.3, ua.VariantType.Double)
    async with server:
        emit("server_ready", endpoint=endpoint(port), namespace_uri=NAMESPACE_URI,
             NodeId=temperature.nodeid.to_string(), initial_value=65.3)
        await asyncio.Event().wait()  # 不定时改变值，仅在教学设温请求时更新。


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--port", type=port_number, default=4840)
    parser.add_argument("--extra-namespace", action="store_true", help="先注册一个无关命名空间，验证客户端不写死索引")
    args = parser.parse_args()
    try:
        asyncio.run(run(args.port, args.extra_namespace))
    except KeyboardInterrupt:
        return 130
    except (OSError, ua.UaError) as exc:
        print(f"OPC UA 模拟器启动失败：{exc}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
