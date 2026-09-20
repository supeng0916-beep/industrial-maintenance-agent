"""Persistent OPC UA subscriptions with bounded intake and a single database writer."""
import asyncio
from collections import OrderedDict
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass
from datetime import datetime, timezone
from functools import partial
import math
import sqlite3
import sys
import time

from asyncua import Client, ua
from alarms import initialize_alarms
from storage import open_database
from opcua_runtime import (SessionSuperseded, initialize_runtime, update_runtime,
                           interrupt_runtime)
from opcua_simulator import NAMESPACE_URI, TEMPERATURE_ID, endpoint
from opcua_storage import initialize_opcua, save_data_value


def utc_now():
    return datetime.now(timezone.utc)


class SubscriptionConfigurationError(ValueError):
    pass


@dataclass(frozen=True)
class Notification:
    identity: tuple
    data: ua.DataValue
    received_at: datetime
    received_mono: float


class NotificationBuffer:
    """Callback-owned, generation-local state. No SQLite or awaits in callbacks."""
    def __init__(self, session, generation, size):
        if size < 1:
            raise ValueError('queue size must be positive')
        self.session=session
        self.generation=generation
        self.queue=asyncio.Queue(maxsize=size)
        self.accepting=True
        self.fault=None
        self.dropped=0
        self.duplicates=0
        self.last_publish_at=None
        self.last_publish_mono=time.monotonic()
        self.last_sequence=None
        self.seen_sequences=OrderedDict()

    def fail(self, reason):
        if not self.accepting:
            return
        self.fault=reason
        self.close()

    def close(self):
        self.accepting=False
        while not self.queue.empty():
            self.queue.get_nowait()
            self.dropped+=1

    def callback(self, result):
        if not self.accepting:
            return
        now=utc_now(); mono=time.monotonic()
        self.last_publish_at=now; self.last_publish_mono=mono
        notifications=result.NotificationMessage.NotificationData or []
        if not notifications:  # Keepalive sequence is the NEXT notification, not consumed.
            return
        for notification in notifications:
            if isinstance(notification,ua.StatusChangeNotification):
                self.fail(f'subscription_status:{notification.Status.name}'); return
        sequence=int(result.NotificationMessage.SequenceNumber)
        if not 1 <= sequence <= 0xFFFFFFFF:
            self.fail('invalid_publish_sequence'); return
        distance=(sequence-self.last_sequence)%0xFFFFFFFF if self.last_sequence is not None else 1
        if sequence in self.seen_sequences or distance>0xFFFFFFFF//2:
            self.duplicates+=sum(len(n.MonitoredItems) for n in notifications if isinstance(n,ua.DataChangeNotification))
            return
        if self.last_sequence is not None and distance!=1:
            self.fail('publish_sequence_gap'); return
        self.last_sequence=sequence
        self.seen_sequences[sequence]=None
        if len(self.seen_sequences)>4096:
            self.seen_sequences.popitem(last=False)
        for data_index, notification in enumerate(notifications):
            if isinstance(notification,ua.StatusChangeNotification):
                self.fail(f'subscription_status:{notification.Status.name}'); return
            if not isinstance(notification,ua.DataChangeNotification):
                continue
            for item_index,item in enumerate(notification.MonitoredItems):
                if item.ClientHandle != 1:
                    self.fail('unknown_monitored_item'); return
                status=item.Value.StatusCode.value
                if status & 0xC00 == 0x400 and status & 0x80:
                    self.dropped+=1
                    self.fail('server_queue_overflow'); return
                identity=(self.session,self.generation,result.SubscriptionId,sequence,data_index,item_index)
                try:
                    self.queue.put_nowait(Notification(identity,item.Value,now,mono))
                except asyncio.QueueFull:
                    self.dropped+=1
                    self.fail('application_queue_overflow'); return


class DatabaseWriter:
    """One dedicated thread owns the SQLite connection for its entire lifetime."""
    def __init__(self, path, interval):
        self.path=path; self.interval=interval
        self.executor=ThreadPoolExecutor(max_workers=1,thread_name_prefix='opcua-db')
        self.conn=None
        self.session=None

    async def start(self):
        def initialize():
            self.conn=open_database(self.path)
            initialize_opcua(self.conn)
            self.session=initialize_alarms(self.conn,self.interval,device_id='motor-b')
            initialize_runtime(self.conn,self.session,'subscribe',utc_now())
            return self.session
        return await asyncio.get_running_loop().run_in_executor(self.executor,initialize)

    async def call(self, function, *args, **kwargs):
        return await asyncio.get_running_loop().run_in_executor(self.executor,partial(function,self.conn,*args,**kwargs))

    async def close(self):
        if self.conn is not None:
            await asyncio.get_running_loop().run_in_executor(self.executor,self.conn.close)
            self.conn=None
        self.executor.shutdown(wait=True)


async def close_client(client, subscription_id):
    """Tear down only this connection. Local callbacks cannot survive failed delete."""
    if subscription_id is not None:
        try:
            await asyncio.wait_for(client.uaclient.delete_subscriptions([subscription_id]),2)
        except (OSError,ua.UaError,asyncio.TimeoutError):
            pass
        finally:
            client.uaclient.session._subscription_callbacks.pop(subscription_id,None)
    publish_task=client.uaclient.session._publish_task
    try:
        await asyncio.wait_for(client.disconnect(),3)
    except (OSError,ua.UaError,asyncio.TimeoutError):
        client.disconnect_socket()
    finally:
        if publish_task is not None:
            if not publish_task.done(): publish_task.cancel()
            await asyncio.gather(publish_task,return_exceptions=True)


async def create_monitored_subscription(client, buffer, interval, publishing_ms, sampling_ms, server_queue_size):
    index=await client.get_namespace_index(NAMESPACE_URI)
    params=ua.CreateSubscriptionParameters(RequestedPublishingInterval=publishing_ms,
        RequestedLifetimeCount=120,RequestedMaxKeepAliveCount=4,
        MaxNotificationsPerPublish=server_queue_size,PublishingEnabled=True,Priority=0)
    subscription=await client.uaclient.create_subscription(params,buffer.callback)
    # Assign immediately: failures below must still delete the created subscription.
    buffer.subscription_id=subscription.SubscriptionId
    filtering=ua.DataChangeFilter(Trigger=ua.DataChangeTrigger.StatusValueTimestamp,
        DeadbandType=0,DeadbandValue=0)
    request=ua.MonitoredItemCreateRequest(
        ItemToMonitor=ua.ReadValueId(NodeId=ua.NodeId(TEMPERATURE_ID,index),AttributeId=ua.AttributeIds.Value),
        MonitoringMode=ua.MonitoringMode.Reporting,
        RequestedParameters=ua.MonitoringParameters(ClientHandle=1,SamplingInterval=sampling_ms,
            Filter=filtering,QueueSize=server_queue_size,DiscardOldest=True))
    results=await client.uaclient.create_monitored_items(ua.CreateMonitoredItemsParameters(
        SubscriptionId=subscription.SubscriptionId,TimestampsToReturn=ua.TimestampsToReturn.Both,ItemsToCreate=[request]))
    if len(results)!=1 or not results[0].StatusCode.is_good():
        raise SubscriptionConfigurationError(f'monitored item rejected: {results}')
    item=results[0]
    revised=dict(publishing_interval_ms=subscription.RevisedPublishingInterval,
        sampling_interval_ms=item.RevisedSamplingInterval,queue_size=item.RevisedQueueSize,
        keepalive_count=subscription.RevisedMaxKeepAliveCount,lifetime_count=subscription.RevisedLifetimeCount)
    return revised


def validate_revised(revised, interval):
    if (not all(math.isfinite(value) for value in revised.values())
        or not 0 < revised['publishing_interval_ms'] <= interval*1500
        or not 0 <= revised['sampling_interval_ms'] <= interval*1500
        or revised['queue_size']<2 or revised['keepalive_count']<1 or revised['lifetime_count']<3):
        raise SubscriptionConfigurationError(f'revised parameters cannot preserve continuous evidence: {revised}')



async def collect_subscription(path, port, interval=1, count=0, source_max_age=5, *,
                               queue_size=256,publishing_interval_ms=250,
                               sampling_interval_ms=250,server_queue_size=16):
    """Run until count data notifications, cancellation, or an unrecoverable DB/config fault."""
    writer=DatabaseWriter(path,interval)
    generation=0; reconnects=0; dropped=0; duplicates=0; attempts=0; rejected=0
    session=None; buffer=None; terminal='stopped'; terminal_error=None
    delay=1
    try:
        session=await writer.start()
        while count==0 or attempts<count:
            generation+=1
            buffer=NotificationBuffer(session,generation,queue_size)
            client=Client(endpoint(port),timeout=2,watchdog_intervall=1,auto_reconnect=False)
            async def connection_lost(exc, active_buffer=buffer):
                active_buffer.fail(f'connection_lost:{exc}')
            client.connection_lost_callback=connection_lost
            await writer.call(update_runtime,session,utc_now(),generation=generation,
                state='connecting' if reconnects==0 else 'reconnecting',error=None,
                last_notification_at=None,last_publish_at=None,revised=None)
            try:
                await asyncio.wait_for(client.connect(),5)
                revised=await create_monitored_subscription(client,buffer,interval,publishing_interval_ms,
                    sampling_interval_ms,server_queue_size)
                await writer.call(update_runtime,session,utc_now(),expected_generation=generation,revised=revised)
                validate_revised(revised,interval)
                await writer.call(update_runtime,session,utc_now(),expected_generation=generation,
                    state='subscribed',error=None)
                last_evidence=time.monotonic()
                heartbeat=0
                evidence_interrupted=False
                while count==0 or attempts<count:
                    if buffer.fault:
                        raise ConnectionError(buffer.fault)
                    now_mono=time.monotonic()
                    publish_timeout=max(1.5,3*revised['publishing_interval_ms']*revised['keepalive_count']/1000)
                    if now_mono-buffer.last_publish_mono>publish_timeout:
                        raise ConnectionError('publish_timeout')
                    if not evidence_interrupted and now_mono-last_evidence>interval*1.5:
                        await writer.call(interrupt_runtime,session,utc_now(),'source_notification_gap',
                            generation=generation,state='subscribed',event_type='evidence_interruption')
                        evidence_interrupted=True
                    if now_mono-heartbeat>=.5:
                        await writer.call(update_runtime,session,utc_now(),expected_generation=generation,
                            last_publish_at=buffer.last_publish_at,duplicate_count=duplicates+buffer.duplicates)
                        heartbeat=now_mono
                    try:
                        notification=await asyncio.wait_for(buffer.queue.get(),.1)
                    except asyncio.TimeoutError:
                        continue
                    if buffer.fault or not buffer.accepting:
                        buffer.dropped+=1
                        continue
                    diagnostic=await writer.call(save_data_value,notification.data,notification.received_at,
                        alarm_session=session,generation=generation,notification_identity=notification.identity,
                        monotonic_now=notification.received_mono,source_max_age=source_max_age,
                        processing_deadline=notification.received_mono+interval*1.5,decision_clock=utc_now)
                    if diagnostic.get('duplicate'):
                        continue
                    attempts+=1
                    rejected+=not diagnostic['accepted']
                    if diagnostic['accepted']:
                        last_evidence=notification.received_mono
                        evidence_interrupted=False
                        delay=1
                    print(f"{notification.received_at.isoformat()} 订阅通知{attempts} {diagnostic['reason']} value={diagnostic['value_json']} generation={generation}",flush=True)
                    if diagnostic['reason']=='notification_processing_delay':
                        raise ConnectionError('notification_processing_delay')
            except (ConnectionError,OSError,ua.UaError,asyncio.TimeoutError) as exc:
                if str(exc)=='notification_processing_delay': buffer.dropped+=1
                buffer.close()
                dropped+=buffer.dropped
                reconnects+=1
                await writer.call(interrupt_runtime,session,utc_now(),str(exc) or type(exc).__name__,
                    generation=generation,state='reconnecting',event_type=('evidence_interruption' if str(exc) in ('application_queue_overflow','server_queue_overflow','publish_sequence_gap','notification_processing_delay','unknown_monitored_item','invalid_publish_sequence') else 'communication_error'),
                    reconnect_count=reconnects,dropped_count=dropped)
                print(f'订阅中断，准备重连：{exc}',file=sys.stderr,flush=True)
            finally:
                buffer.close()
                await close_client(client,getattr(buffer,'subscription_id',None))
                duplicates+=buffer.duplicates
            if count and attempts>=count:
                break
            # Keep runtime fresh and fence ownership during bounded exponential backoff.
            deadline=time.monotonic()+delay
            while time.monotonic()<deadline:
                await writer.call(update_runtime,session,utc_now(),expected_generation=generation)
                await asyncio.sleep(min(.5,max(0,deadline-time.monotonic())))
            delay=min(delay*2,5)
        return 1 if rejected else 0
    except SessionSuperseded as exc:
        terminal='superseded'
        print(str(exc),file=sys.stderr,flush=True)
        return 1
    except (sqlite3.Error,SubscriptionConfigurationError,ValueError) as exc:
        terminal='failed'; terminal_error=str(exc)
        print(f'订阅采集停止：{exc}',file=sys.stderr,flush=True)
        return 1
    finally:
        if buffer is not None:
            buffer.close()
        try:
            if session is not None and terminal!='superseded':
                await writer.call(interrupt_runtime,session,utc_now(),terminal_error or 'collector_stopped',
                    state=terminal,generation=generation,event_type='collector_lifecycle',duplicate_count=duplicates)
        except sqlite3.Error as exc:
            print(f'无法保存采集结束状态：{exc}',file=sys.stderr,flush=True)
        finally:
            await writer.close()
