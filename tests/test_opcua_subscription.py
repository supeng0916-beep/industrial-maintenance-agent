"""Public subscription boundaries: bounded callback queue and real UA lifecycle."""
import asyncio
import importlib.util
import socket
import sqlite3
import tempfile
import unittest
from datetime import datetime, timezone
from pathlib import Path
from asyncua import ua
from opcua_simulator import build_server, publish


def load_module(test):
    test.assertIsNotNone(importlib.util.find_spec('opcua_subscription'), 'formal subscription is required')
    import opcua_subscription
    return opcua_subscription


def message(sequence, value=85.0, status=0, count=1):
    now=datetime.now(timezone.utc)
    data=ua.DataValue(ua.Variant(value,ua.VariantType.Double),StatusCode=ua.StatusCode(status),SourceTimestamp=now)
    items=[ua.MonitoredItemNotification(ClientHandle=1,Value=data) for _ in range(count)]
    return ua.PublishResult(78,NotificationMessage=ua.NotificationMessage(SequenceNumber=sequence,NotificationData=[ua.DataChangeNotification(MonitoredItems=items)]))


class CallbackTests(unittest.IsolatedAsyncioTestCase):
    async def test_queue_overflow_invalidates_accumulated_evidence(self):
        module=load_module(self)
        queue=module.NotificationBuffer('session',1,1)
        callback=queue.callback
        callback(message(1)); callback(message(2))
        self.assertEqual(queue.fault,'application_queue_overflow')
        self.assertFalse(queue.accepting)
        self.assertGreaterEqual(queue.dropped,1)

    async def test_callback_capture_identity_ignores_old_generation_and_detects_gap(self):
        module=load_module(self)
        queue=module.NotificationBuffer('session',2,4)
        queue.callback(message(8,count=2))
        one=queue.queue.get_nowait(); two=queue.queue.get_nowait()
        self.assertEqual(one.identity,('session',2,78,8,0,0))
        self.assertEqual(two.identity,('session',2,78,8,0,1))
        queue.callback(message(10))
        self.assertEqual(queue.fault,'publish_sequence_gap')
        queue.close()
        queue.callback(message(11))
        self.assertTrue(queue.queue.empty())

    async def test_duplicate_publish_and_keepalive_are_not_gaps(self):
        module=load_module(self)
        queue=module.NotificationBuffer('session',1,5)
        queue.callback(message(1)); queue.callback(message(1))
        queue.callback(ua.PublishResult(78,NotificationMessage=ua.NotificationMessage(SequenceNumber=2,NotificationData=[])))
        queue.callback(message(2))
        self.assertIsNone(queue.fault)
        self.assertEqual(queue.queue.qsize(),2)
        self.assertEqual(queue.duplicates,1)

    async def test_server_overflow_and_statuschange_interrupt(self):
        module=load_module(self)
        queue=module.NotificationBuffer('session',1,5)
        queue.callback(message(1,status=0x480))
        self.assertEqual(queue.fault,'server_queue_overflow')
        queue=module.NotificationBuffer('session',1,5)
        queue.callback(ua.PublishResult(78,NotificationMessage=ua.NotificationMessage(NotificationData=[ua.StatusChangeNotification(Status=ua.StatusCode(ua.StatusCodes.BadTimeout))])))
        self.assertIn('subscription_status',queue.fault)

    async def test_duplicate_storm_cannot_overflow_queue_or_interrupt_evidence(self):
        module=load_module(self)
        queue=module.NotificationBuffer('session',1,1)
        queue.callback(message(10))
        for _ in range(50): queue.callback(message(10))
        queue.callback(message(9))  # an old retransmission outside the remembered set
        self.assertIsNone(queue.fault)
        self.assertEqual(queue.queue.qsize(),1)
        self.assertEqual(queue.duplicates,51)



class SubscriptionIntegrationTests(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        self.module=load_module(self)
        self.directory=tempfile.TemporaryDirectory(); self.addCleanup(self.directory.cleanup)
        self.db=Path(self.directory.name)/'subscription.sqlite3'
        with socket.socket() as sock:
            sock.bind(('127.0.0.1',0)); self.port=sock.getsockname()[1]
        self.server,self.node=await build_server(self.port,extra_namespace=True)
        await self.server.start()
        self.addAsyncCleanup(self.server.stop)

    async def wait_rows(self,number,timeout=5):
        until=asyncio.get_running_loop().time()+timeout
        while asyncio.get_running_loop().time()<until:
            if self.db.exists():
                with sqlite3.connect(self.db) as conn:
                    try:
                        if conn.execute('SELECT count(*) FROM opcua_diagnostics').fetchone()[0]>=number: return
                    except sqlite3.OperationalError: pass
            await asyncio.sleep(.025)
        self.fail('notification not persisted')

    async def test_real_constant_value_new_source_and_revised_parameters(self):
        now=datetime.now(timezone.utc)
        await publish(self.node,85,'good','fresh',now,now,0)
        task=asyncio.create_task(self.module.collect_subscription(self.db,self.port,1,4))
        self.addAsyncCleanup(self.cancel,task)
        await self.wait_rows(1)
        for number in range(2,5):
            now=datetime.now(timezone.utc)
            await publish(self.node,85,'good','fresh',now,now,number)
            await self.wait_rows(number)
        self.assertEqual(await asyncio.wait_for(task,5),0)
        with sqlite3.connect(self.db) as conn:
            self.assertEqual(conn.execute('SELECT count(*),count(distinct source_time),min(value),max(value) FROM measurements').fetchone(),(4,4,85.0,85.0))
            from opcua_runtime import read_runtime
            runtime=read_runtime(conn,datetime.now(timezone.utc))
            self.assertEqual(runtime['state'],'stopped')
            self.assertEqual(runtime['revised']['queue_size'],16)
            self.assertEqual(runtime['revised']['publishing_interval_ms'],250)
        self.assertEqual(len(self.server.iserver.subscription_service.subscriptions),0)


    async def test_continuous_bad_quality_does_not_reconnect_or_report_communication_failure(self):
        now=datetime.now(timezone.utc)
        await publish(self.node,85,'bad','fresh',now,now,0)
        task=asyncio.create_task(self.module.collect_subscription(self.db,self.port,1,0))
        self.addAsyncCleanup(self.cancel,task)
        await self.wait_rows(1)
        for number in range(10):
            now=datetime.now(timezone.utc)
            await publish(self.node,85,'bad','fresh',now,now,number)
            await asyncio.sleep(.32)
        with sqlite3.connect(self.db) as conn:
            conn.row_factory=sqlite3.Row
            from opcua_runtime import read_runtime
            from opcua_storage import read_opcua_status
            runtime=read_runtime(conn,datetime.now(timezone.utc))
            self.assertEqual(runtime['state'],'subscribed')
            self.assertEqual(runtime['generation'],1)
            status=read_opcua_status(conn,datetime.now(timezone.utc),5)
            self.assertEqual(status['communication'],'success')
            self.assertEqual(status['quality'],'bad')
            self.assertFalse(status['eligible'])

    async def test_keepalive_without_source_evidence_clears_pending_without_reconnect(self):
        now=datetime.now(timezone.utc)
        await publish(self.node,85,'good','fresh',now,now,0)
        task=asyncio.create_task(self.module.collect_subscription(self.db,self.port,1,0))
        self.addAsyncCleanup(self.cancel,task)
        await self.wait_rows(1)
        await asyncio.sleep(1.9)
        with sqlite3.connect(self.db) as conn:
            conn.row_factory=sqlite3.Row
            from opcua_runtime import read_runtime
            from opcua_storage import read_opcua_status
            runtime=read_runtime(conn,datetime.now(timezone.utc))
            self.assertEqual(runtime['state'],'subscribed')
            self.assertEqual(runtime['generation'],1)
            self.assertIsNone(conn.execute('SELECT pending_at FROM temperature_alarm_state').fetchone()[0])
            status=read_opcua_status(conn,datetime.now(timezone.utc),5)
            self.assertEqual(status['communication'],'success')
            self.assertFalse(status['eligible'])


    async def test_real_constant_high_for_five_seconds_triggers_then_low_recovers(self):
        now=datetime.now(timezone.utc)
        await publish(self.node,85,'good','fresh',now,now,0)
        task=asyncio.create_task(self.module.collect_subscription(self.db,self.port,1,14))
        self.addAsyncCleanup(self.cancel,task)
        await self.wait_rows(1)
        for number in range(12):
            await asyncio.sleep(.5)
            now=datetime.now(timezone.utc)
            await publish(self.node,85,'good','fresh',now,now,number)
        await self.wait_rows(13)
        with sqlite3.connect(self.db) as conn:
            alarm=conn.execute('SELECT observed_seconds,recovered_at FROM temperature_alarms').fetchone()
            self.assertIsNotNone(alarm)
            self.assertGreaterEqual(alarm[0],5)
            self.assertIsNone(alarm[1])
        now=datetime.now(timezone.utc)
        await publish(self.node,77,'good','fresh',now,now,13)
        self.assertEqual(await asyncio.wait_for(task,5),0)
        with sqlite3.connect(self.db) as conn:
            self.assertIsNotNone(conn.execute('SELECT recovered_at FROM temperature_alarms').fetchone()[0])

    async def test_real_bad_uncertain_missing_future_stale_backward_and_duplicate_source_are_rejected(self):
        from datetime import timedelta
        initial=datetime.now(timezone.utc)
        await publish(self.node,85,'good','fresh',initial,initial,0)
        task=asyncio.create_task(self.module.collect_subscription(self.db,self.port,1,8))
        self.addAsyncCleanup(self.cancel,task)
        await self.wait_rows(1)
        cases=[('bad','fresh','bad'),('uncertain','fresh','uncertain'),('good','missing','missing'),
            ('good','future','future'),('good','stale','stale'),('good','backward','backward'),('good','frozen','duplicate')]
        for number,(quality,source,reason) in enumerate(cases,2):
            await publish(self.node,86,quality,source,datetime.now(timezone.utc),initial,.2 if source=='backward' else number)
            await self.wait_rows(number)
            with sqlite3.connect(self.db) as conn:
                self.assertEqual(conn.execute('SELECT reason FROM opcua_diagnostics ORDER BY id DESC LIMIT 1').fetchone()[0],reason)
                self.assertIsNone(conn.execute('SELECT pending_at FROM temperature_alarm_state').fetchone()[0])
        self.assertEqual(await asyncio.wait_for(task,5),1)
        with sqlite3.connect(self.db) as conn:
            self.assertEqual(conn.execute('SELECT count(*) FROM measurements').fetchone()[0],1)

    async def test_server_restart_same_port_creates_new_generation(self):
        task=asyncio.create_task(self.module.collect_subscription(self.db,self.port,1,2))
        self.addAsyncCleanup(self.cancel,task)
        await self.wait_rows(1)
        await self.server.stop()
        self.server,self.node=await build_server(self.port)
        await self.server.start(); self.addAsyncCleanup(self.server.stop)
        self.assertEqual(await asyncio.wait_for(task,10),0)
        with sqlite3.connect(self.db) as conn:
            self.assertGreaterEqual(conn.execute('SELECT generation FROM opcua_runtime').fetchone()[0],2)
            self.assertGreaterEqual(conn.execute('SELECT reconnect_count FROM opcua_runtime').fetchone()[0],1)
            self.assertEqual(conn.execute('SELECT count(distinct generation) FROM opcua_notification_receipts').fetchone()[0],2)

    async def test_initial_server_unavailable_retries_and_then_subscribes(self):
        await self.server.stop()
        task=asyncio.create_task(self.module.collect_subscription(self.db,self.port,1,1))
        self.addAsyncCleanup(self.cancel,task)
        await asyncio.sleep(.4)
        self.server,self.node=await build_server(self.port)
        await self.server.start(); self.addAsyncCleanup(self.server.stop)
        self.assertEqual(await asyncio.wait_for(task,8),0)
        with sqlite3.connect(self.db) as conn:
            self.assertGreaterEqual(conn.execute('SELECT reconnect_count FROM opcua_runtime').fetchone()[0],1)

    async def test_database_failure_stops_and_rolls_back_notification(self):
        task=asyncio.create_task(self.module.collect_subscription(self.db,self.port,1,0))
        self.addAsyncCleanup(self.cancel,task)
        await self.wait_rows(1)
        with sqlite3.connect(self.db) as conn:
            conn.execute("CREATE TRIGGER force_failure BEFORE INSERT ON measurements BEGIN SELECT RAISE(FAIL,'forced disk failure'); END")
        now=datetime.now(timezone.utc)
        await publish(self.node,85,'good','fresh',now,now,1)
        self.assertEqual(await asyncio.wait_for(task,5),1)
        with sqlite3.connect(self.db) as conn:
            self.assertEqual(conn.execute('SELECT state FROM opcua_runtime').fetchone()[0],'failed')
            self.assertEqual(conn.execute('SELECT count(*) FROM opcua_notification_receipts').fetchone()[0],1)
            self.assertEqual(conn.execute('SELECT count(*) FROM opcua_diagnostics').fetchone()[0],1)
        self.assertEqual(len(self.server.iserver.subscription_service.subscriptions),0)

    async def test_new_session_supersedes_subscriber_without_touching_new_pending(self):
        from alarms import initialize_alarms
        from opcua_storage import save_data_value
        from opcua_runtime import initialize_runtime
        task=asyncio.create_task(self.module.collect_subscription(self.db,self.port,1,0))
        self.addAsyncCleanup(self.cancel,task)
        await self.wait_rows(1)
        with sqlite3.connect(self.db) as conn:
            session=initialize_alarms(conn,1,device_id='motor-b')
            now=datetime.now(timezone.utc)
            initialize_runtime(conn,session,'read',now)
            save_data_value(conn,ua.DataValue(ua.Variant(85.0,ua.VariantType.Double),SourceTimestamp=now),now,alarm_session=session)
        self.assertEqual(await asyncio.wait_for(task,4),1)
        with sqlite3.connect(self.db) as conn:
            self.assertEqual(conn.execute('SELECT mode,state,session_id FROM opcua_runtime').fetchone(),('read','reading',session))
            self.assertIsNotNone(conn.execute('SELECT pending_at FROM temperature_alarm_state').fetchone()[0])
            self.assertEqual(conn.execute('SELECT count(*) FROM collection_events').fetchone()[0],0)

    async def test_application_overflow_is_visible_and_reconnects_without_blocking_event_loop(self):
        task=asyncio.create_task(self.module.collect_subscription(self.db,self.port,1,0,queue_size=1))
        self.addAsyncCleanup(self.cancel,task)
        await self.wait_rows(1)
        for number in range(5):
            now=datetime.now(timezone.utc)
            await publish(self.node,85,'good','fresh',now,now,number)
        deadline=asyncio.get_running_loop().time()+4
        while asyncio.get_running_loop().time()<deadline:
            with sqlite3.connect(self.db) as conn:
                row=conn.execute("SELECT message FROM collection_events WHERE event_type='evidence_interruption'").fetchone()
                if row:
                    self.assertEqual(row[0],'application_queue_overflow')
                    self.assertGreater(conn.execute('SELECT dropped_count FROM opcua_runtime').fetchone()[0],0)
                    self.assertIsNone(conn.execute('SELECT pending_at FROM temperature_alarm_state').fetchone()[0])
                    break
            await asyncio.sleep(.03)
        else: self.fail('overflow did not surface')

    async def test_delayed_notification_persists_rejection_and_counts_one_drop(self):
        task=asyncio.create_task(self.module.collect_subscription(self.db,self.port,1,2))
        self.addAsyncCleanup(self.cancel,task)
        await self.wait_rows(1)
        conn=sqlite3.connect(self.db); self.addCleanup(conn.close)
        conn.execute('BEGIN IMMEDIATE')
        now=datetime.now(timezone.utc)
        await publish(self.node,77,'good','fresh',now,now,1)
        await asyncio.sleep(1.9)
        conn.commit()
        self.assertEqual(await asyncio.wait_for(task,5),1)
        row=conn.execute('SELECT accepted,reason,received_at,decision_at FROM opcua_diagnostics ORDER BY id DESC LIMIT 1').fetchone()
        self.assertEqual(row[:2],(0,'notification_processing_delay'))
        self.assertGreater((datetime.fromisoformat(row[3])-datetime.fromisoformat(row[2])).total_seconds(),1.5)
        self.assertEqual(conn.execute('SELECT dropped_count FROM opcua_runtime').fetchone()[0],1)
        self.assertEqual(conn.execute('SELECT count(*) FROM measurements').fetchone()[0],1)
        self.assertEqual(conn.execute('SELECT count(*) FROM opcua_notification_receipts').fetchone()[0],2)

    async def test_incompatible_revised_interval_fails_without_hiding_server_parameters(self):
        result=await self.module.collect_subscription(self.db,self.port,.1,1)
        self.assertEqual(result,1)
        with sqlite3.connect(self.db) as conn:
            from opcua_runtime import read_runtime
            runtime=read_runtime(conn,datetime.now(timezone.utc))
            self.assertEqual(runtime['state'],'failed')
            self.assertIsNotNone(runtime['revised'])
            self.assertEqual(runtime['revised']['publishing_interval_ms'],250)
        self.assertEqual(len(self.server.iserver.subscription_service.subscriptions),0)

    @staticmethod
    async def cancel(task):
        if not task.done(): task.cancel()
        try: await task
        except asyncio.CancelledError: pass

if __name__=='__main__': unittest.main()
