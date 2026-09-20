"""电机B OPC UA采集：默认主动read，可选持久subscribe；假设UTC时钟同步。"""
import argparse
import asyncio
from contextlib import closing
from datetime import datetime, timezone
import math
import sqlite3
import sys
import time
from asyncua import Client, ua
from alarms import initialize_alarms
from storage import DEFAULT_DB, open_database
from opcua_storage import initialize_opcua, save_data_value, save_communication_failure
from opcua_runtime import initialize_runtime, update_runtime, interrupt_runtime, SessionSuperseded
from opcua_simulator import NAMESPACE_URI, TEMPERATURE_ID, endpoint


async def read_once(port):
    async with Client(endpoint(port),timeout=2) as client:
        index=await client.get_namespace_index(NAMESPACE_URI)
        node=client.get_node(ua.NodeId(TEMPERATURE_ID,index))
        return await node.read_data_value(raise_on_bad_status=False)


async def collect(conn, port, interval, count, alarm_session, source_max_age=5):
    initialize_runtime(conn,alarm_session,'read',datetime.now(timezone.utc))
    try:
        return await _collect_read(conn,port,interval,count,alarm_session,source_max_age)
    except sqlite3.Error as exc:
        try:
            interrupt_runtime(conn,alarm_session,datetime.now(timezone.utc),str(exc),state='failed',event_type='collector_lifecycle')
        except sqlite3.Error:
            pass
        raise
    finally:
        try:
            runtime=conn.execute('SELECT state FROM opcua_runtime WHERE device_id=? AND session_id=?',('motor-b',alarm_session)).fetchone()
            if runtime and runtime[0]!='failed':
                interrupt_runtime(conn,alarm_session,datetime.now(timezone.utc),'collector_stopped',state='stopped',event_type='collector_lifecycle')
        except SessionSuperseded:
            pass


async def _collect_read(conn,port,interval,count,alarm_session,source_max_age):
    attempts=failures=0
    while count==0 or attempts<count:
        update_runtime(conn,alarm_session,datetime.now(timezone.utc),state='reading')
        started=time.monotonic(); attempts+=1
        try:
            data=await read_once(port)
        except (OSError,ua.UaError,asyncio.TimeoutError,ValueError) as exc:
            failures+=1
            now=datetime.now(timezone.utc)
            save_communication_failure(conn,now,str(exc),alarm_session=alarm_session)
            update_runtime(conn,alarm_session,now,error=str(exc))
            print(f'{now.isoformat()} 第{attempts}次 通信失败：{exc}',file=sys.stderr,flush=True)
        else:
            now=datetime.now(timezone.utc)
            diagnostic=save_data_value(conn,data,now,alarm_session=alarm_session,monotonic_now=time.monotonic(),source_max_age=source_max_age)
            update_runtime(conn,alarm_session,now,error=None)
            failures+=not diagnostic['accepted']
            print(f"{now.isoformat()} 第{attempts}次 {diagnostic['reason']} value={diagnostic['value_json']} source={diagnostic['source_time']}",flush=True)
        if count==0 or attempts<count:
            await asyncio.sleep(max(0,interval-(time.monotonic()-started)))
    print(f'采集结束：尝试={attempts} 成功={attempts-failures} 失败={failures}',flush=True)
    return 1 if failures else 0


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--mode',choices=['read','subscribe'],default='read')
    parser.add_argument('--queue-size',type=int,default=256,help='订阅应用缓冲队列上限')
    parser.add_argument('--server-queue-size',type=int,default=16,help='请求服务端monitored item队列长度')
    parser.add_argument('--publishing-interval-ms',type=float,default=250)
    parser.add_argument('--sampling-interval-ms',type=float,default=250)
    parser.add_argument('--port',type=int,default=4841)
    parser.add_argument('--db',default=DEFAULT_DB)
    parser.add_argument('--interval',type=float,default=1)
    parser.add_argument('--count',type=int,default=0)
    parser.add_argument('--source-max-age',type=float,default=5,help='教学源时间门槛秒数；API门槛不得大于此值')
    args=parser.parse_args()
    if not 1024<=args.port<=65535: parser.error('--port 必须在1024～65535之间')
    if not math.isfinite(args.interval) or not 0<args.interval<=5/1.5: parser.error('--interval 必须为正且不超过10/3秒')
    if not math.isfinite(args.source_max_age) or args.source_max_age<1.5*args.interval: parser.error('--source-max-age 必须有限且不少于1.5倍interval')
    if args.count<0: parser.error('--count 必须非负')
    if not 1<=args.queue_size<=100000: parser.error('--queue-size 必须在1～100000之间')
    if not 2<=args.server_queue_size<=100000: parser.error('--server-queue-size 必须在2～100000之间')
    if not math.isfinite(args.publishing_interval_ms) or not 0<args.publishing_interval_ms<=args.interval*1500: parser.error('--publishing-interval-ms 必须为正且不超过1.5倍interval毫秒数')
    if not math.isfinite(args.sampling_interval_ms) or not 0<=args.sampling_interval_ms<=args.interval*1500: parser.error('--sampling-interval-ms 必须非负且不超过1.5倍interval毫秒数')
    try:
        if args.mode=='subscribe':
            from opcua_subscription import collect_subscription
            return asyncio.run(collect_subscription(args.db,args.port,args.interval,args.count,args.source_max_age,queue_size=args.queue_size,server_queue_size=args.server_queue_size,publishing_interval_ms=args.publishing_interval_ms,sampling_interval_ms=args.sampling_interval_ms))
        with closing(open_database(args.db)) as conn:
            initialize_opcua(conn)
            session=initialize_alarms(conn,args.interval,device_id='motor-b')
            return asyncio.run(collect(conn,args.port,args.interval,args.count,session,args.source_max_age))
    except KeyboardInterrupt: return 130
    except (OSError,sqlite3.Error) as exc:
        print(f'数据库初始化或写入失败：{exc}；采集停止',file=sys.stderr); return 1

if __name__=='__main__': sys.exit(main())
