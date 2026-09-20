"""正式电机B教学模拟器：本机无认证，0.5秒生成源测量，假设UTC时钟同步。"""
import argparse
import asyncio
from datetime import datetime, timedelta, timezone
import json
import math
import sys
from asyncua import Server, ua

NAMESPACE_URI='urn:industrial-maintenance:motor-b'
TEMPERATURE_ID='MotorB.Temperature'


def endpoint(port): return f'opc.tcp://127.0.0.1:{port}/motor-b/'


async def build_server(port, extra_namespace=False):
    server=Server()
    await server.init()
    server.set_endpoint(endpoint(port))
    server.set_security_policy([ua.SecurityPolicyType.NoSecurity])
    server.set_identity_tokens([ua.AnonymousIdentityToken])
    if extra_namespace: await server.register_namespace(NAMESPACE_URI+':padding')
    index=await server.register_namespace(NAMESPACE_URI)
    motor=await server.nodes.objects.add_object(ua.NodeId('MotorB',index),'MotorB')
    node=await motor.add_variable(ua.NodeId(TEMPERATURE_ID,index),'Temperature',ua.Variant(65.3,ua.VariantType.Double))
    return server,node


async def publish(node, value, quality, source_mode, now, initial, sequence):
    source={'fresh':now,'missing':None,'stale':now-timedelta(seconds=60),'future':now+timedelta(seconds=60),
            'frozen':initial,'backward':initial-timedelta(seconds=sequence*.5)}[source_mode]
    status={'good':ua.StatusCodes.Good,'bad':ua.StatusCodes.BadSensorFailure,'uncertain':ua.StatusCodes.UncertainSensorNotAccurate}[quality]
    data=ua.DataValue(ua.Variant(value,ua.VariantType.Double),StatusCode=ua.StatusCode(status),SourceTimestamp=source,ServerTimestamp=now)
    await node.write_attribute(ua.AttributeIds.Value,data)


async def run(args):
    server,node=await build_server(args.port,args.extra_namespace)
    initial=datetime.now(timezone.utc)
    await publish(node,args.value,args.quality,args.source_mode,initial,initial,0)
    async with server:
        print(json.dumps({'event':'server_ready','endpoint':endpoint(args.port),'namespace_uri':NAMESPACE_URI,'NodeId':node.nodeid.to_string()}),flush=True)
        sequence=0
        while True:
            await asyncio.sleep(.5)
            sequence+=1
            await publish(node,args.value,args.quality,args.source_mode,datetime.now(timezone.utc),initial,sequence)


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--port',type=int,default=4841)
    parser.add_argument('--value',type=float,default=65.3)
    parser.add_argument('--quality',choices=['good','bad','uncertain'],default='good')
    parser.add_argument('--source-mode',choices=['fresh','missing','stale','future','frozen','backward'],default='fresh')
    parser.add_argument('--extra-namespace',action='store_true')
    args=parser.parse_args()
    if not 1024<=args.port<=65535: parser.error('--port 必须在1024～65535之间')
    if not math.isfinite(args.value): parser.error('--value 必须有限')
    try: asyncio.run(run(args))
    except KeyboardInterrupt: return 130
    except (OSError,ua.UaError) as exc:
        print(str(exc),file=sys.stderr); return 1
    return 0

if __name__=='__main__': sys.exit(main())
