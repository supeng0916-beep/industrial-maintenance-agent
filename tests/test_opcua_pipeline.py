import unittest
import sqlite3
import tempfile
from pathlib import Path
from datetime import datetime, timedelta, timezone
from asyncua import ua
import alarms
import storage

class PipelineTests(unittest.TestCase):
    def setUp(self):
        self.conn = sqlite3.connect(':memory:')
        self.addCleanup(self.conn.close)
        storage.initialize(self.conn)
        self.now = datetime.now(timezone.utc)

    def setup_b(self):
        import opcua_storage as op
        op.initialize_opcua(self.conn)
        self.session = alarms.initialize_alarms(self.conn, device_id='motor-b')
        return op

    def dv(self, seconds=0, value=85., quality=ua.StatusCodes.Good):
        return ua.DataValue(ua.Variant(value, ua.VariantType.Double), StatusCode=ua.StatusCode(quality), SourceTimestamp=self.now+timedelta(seconds=seconds))

    def save(self, op, dv, second=0):
        return op.save_data_value(self.conn, dv, self.now+timedelta(seconds=second), alarm_session=self.session, monotonic_now=second)

    def test_device_sessions_are_independent(self):
        a = alarms.initialize_alarms(self.conn)
        b = alarms.initialize_alarms(self.conn, device_id='motor-b')
        storage.save_measurement(self.conn,85,self.now.isoformat(),evaluate_alarm=True,alarm_session=a,monotonic_now=0)
        self.assertNotEqual(a,b)

    def test_gate_pending_active_and_watermark_restart(self):
        op=self.setup_b()
        for i in range(6): self.assertTrue(self.save(op,self.dv(i),i)['accepted'])
        self.assertEqual(self.conn.execute('select count(*) from temperature_alarms').fetchone()[0],1)
        for dv, reason in [(self.dv(6,70,ua.StatusCodes.Bad), 'bad'),(self.dv(6,70,ua.StatusCodes.Uncertain),'uncertain'),(self.dv(9,70),'future'),(self.dv(0,70),'stale'),(self.dv(5,70),'duplicate'),(self.dv(4,70),'backward')]:
            result=self.save(op,dv,6)
            self.assertFalse(result['accepted'],reason)
            self.assertIn(reason,result['reason'])
            self.assertIsNone(self.conn.execute('select recovered_at from temperature_alarms').fetchone()[0])
        self.session=alarms.initialize_alarms(self.conn,device_id='motor-b')
        self.assertFalse(self.save(op,self.dv(5),6)['accepted'])
        self.assertTrue(self.save(op,self.dv(7,70),7)['accepted'])
        self.assertIsNotNone(self.conn.execute('select recovered_at from temperature_alarms').fetchone()[0])

    def test_missing_invalid_and_failure_clear_pending(self):
        op=self.setup_b()
        for dv in [ua.DataValue(ua.Variant(85.,ua.VariantType.Double)),self.dv(1,float('nan')),ua.DataValue(ua.Variant(85,ua.VariantType.Int64),SourceTimestamp=self.now)]:
            self.save(op,self.dv())
            self.assertFalse(self.save(op,dv,1)['accepted'])
            self.assertIsNone(self.conn.execute("select pending_id from temperature_alarm_state where device_id='motor-b'").fetchone()[0])
        op.save_communication_failure(self.conn,self.now,'offline',alarm_session=self.session)
        self.assertEqual(self.conn.execute("select count(*) from collection_events where event_type='communication_error'").fetchone()[0],1)

    def test_transaction_failure_rolls_back(self):
        op=self.setup_b()
        self.conn.execute("CREATE TRIGGER fail_measurement BEFORE INSERT ON measurements BEGIN SELECT RAISE(ABORT,'injected'); END")
        with self.assertRaises(sqlite3.Error): self.save(op,self.dv())
        self.assertEqual(self.conn.execute('select count(*) from opcua_diagnostics').fetchone()[0],0)

if __name__=='__main__': unittest.main()

class ApiBTests(unittest.TestCase):
    def test_readonly_legacy_and_recheck_source_age(self):
        from fastapi.testclient import TestClient
        from api import create_app
        import opcua_storage as op
        with tempfile.TemporaryDirectory() as folder:
            path=Path(folder)/'test.db'
            conn=storage.open_database(path); self.addCleanup(conn.close); storage.initialize(conn)
            now=datetime.now(timezone.utc)
            client=TestClient(create_app(path,now=lambda:now))
            result=client.get('/api/devices/motor-b/latest')
            self.assertEqual(result.status_code,200)
            self.assertIsNone(result.json()['opcua']['diagnostic'])
            self.assertFalse(conn.execute("select 1 from sqlite_master where name='opcua_diagnostics'").fetchone())
            op.initialize_opcua(conn); session=alarms.initialize_alarms(conn,device_id='motor-b')
            dv=ua.DataValue(ua.Variant(85.,ua.VariantType.Double),SourceTimestamp=now-timedelta(seconds=4))
            op.save_data_value(conn,dv,now,alarm_session=session,monotonic_now=0)
            self.assertTrue(client.get('/api/devices/motor-b/latest').json()['opcua']['eligible'])
            now+=timedelta(seconds=2)
            result=client.get('/api/devices/motor-b/latest').json()
            self.assertFalse(result['opcua']['eligible'])
            self.assertTrue(result['status']['is_stale'])
            self.assertEqual(result['status']['data_age_seconds'],6)

class WireTests(unittest.IsolatedAsyncioTestCase):
    async def test_real_namespace_and_bad_value_preserved(self):
        import asyncio
        import socket
        from opcua_simulator import build_server, publish
        from collect_opcua import read_once
        with socket.socket() as sock:
            sock.bind(('127.0.0.1',0)); port=sock.getsockname()[1]
        server,node=await build_server(port,True)
        async with server:
            now=datetime.now(timezone.utc)
            await publish(node,72.8,'bad','fresh',now,now,0)
            data=await read_once(port)
            self.assertEqual(node.nodeid.NamespaceIndex,3)
            self.assertIsNone(data.Value.Value)  # asyncua服务端遵循规范将Bad值置Null
            self.assertTrue(data.StatusCode.is_bad())
            self.assertIsNotNone(data.SourceTimestamp)
            for mode in ('missing','stale','future','frozen','backward'):
                await publish(node,72.8,'good',mode,now,now,2)
                data=await read_once(port)
                if mode=='missing': self.assertIsNone(data.SourceTimestamp)
                elif mode=='future': self.assertGreater(data.SourceTimestamp,now)
                elif mode=='backward': self.assertLess(data.SourceTimestamp,now)
            await publish(node,72.8,'good','fresh',now,now,0)
            first=await read_once(port)
            await publish(node,72.8,'good','fresh',now+timedelta(seconds=.5),now,1)
            second=await read_once(port)
            self.assertGreater(second.SourceTimestamp,first.SourceTimestamp)

class RecoveryTests(PipelineTests):
    def test_every_rejection_clears_pending_without_resetting_other_device(self):
        op=self.setup_b()
        a=alarms.initialize_alarms(self.conn)
        storage.save_measurement(self.conn,85,self.now.isoformat(),evaluate_alarm=True,alarm_session=a,monotonic_now=0)
        modes=[(None,'good'),(-60,'good'),(60,'good'),(0,'good'),(-1,'good'),(1,'bad'),(1,'uncertain')]
        for source,q in modes:
            self.conn.execute("DELETE FROM measurements WHERE device_id='motor-b'")
            self.conn.commit()
            self.save(op,self.dv(),0)
            dv=self.dv(source or 0,quality={'good':ua.StatusCodes.Good,'bad':ua.StatusCodes.Bad,'uncertain':ua.StatusCodes.Uncertain}[q])
            if source is None: dv=ua.DataValue(dv.Value,SourceTimestamp=None)
            self.assertFalse(self.save(op,dv,1)['accepted'])
            self.assertIsNone(self.conn.execute("select pending_id from temperature_alarm_state where device_id='motor-b'").fetchone()[0])
            self.assertIsNotNone(self.conn.execute("select pending_id from temperature_alarm_state where device_id='motor-a'").fetchone()[0])

    def test_future_does_not_poison_watermark_and_failure_recovers(self):
        op=self.setup_b()
        self.assertFalse(self.save(op,self.dv(100),0)['accepted'])
        self.assertTrue(self.save(op,self.dv(1),1)['accepted'])
        op.save_communication_failure(self.conn,self.now+timedelta(seconds=2),'offline',alarm_session=self.session)
        self.assertTrue(self.save(op,self.dv(3),3)['accepted'])
        self.assertEqual(self.conn.execute('select count(*) from measurements').fetchone()[0],2)

    def test_rejection_event_failure_rolls_back_diagnostic_and_pending(self):
        op=self.setup_b(); self.save(op,self.dv())
        before=self.conn.execute("select pending_id from temperature_alarm_state where device_id='motor-b'").fetchone()[0]
        self.conn.execute("CREATE TRIGGER fail_event BEFORE INSERT ON collection_events BEGIN SELECT RAISE(ABORT,'injected'); END")
        with self.assertRaises(sqlite3.Error): self.save(op,self.dv(1,quality=ua.StatusCodes.Bad),1)
        self.assertEqual(self.conn.execute('select count(*) from opcua_diagnostics').fetchone()[0],1)
        self.assertEqual(self.conn.execute("select pending_id from temperature_alarm_state where device_id='motor-b'").fetchone()[0],before)

class ApiQualityTests(unittest.TestCase):
    def test_latest_bad_and_communication_failure_not_hidden_by_previous_good(self):
        from fastapi.testclient import TestClient
        from api import create_app
        import opcua_storage as op
        with tempfile.TemporaryDirectory() as folder:
            path=Path(folder)/'quality.db'; conn=storage.open_database(path); self.addCleanup(conn.close)
            op.initialize_opcua(conn); session=alarms.initialize_alarms(conn,device_id='motor-b')
            now=datetime.now(timezone.utc)
            client=TestClient(create_app(path,now=lambda:now))
            def save(code):
                op.save_data_value(conn,ua.DataValue(ua.Variant(85.,ua.VariantType.Double),StatusCode=ua.StatusCode(code),SourceTimestamp=now),now,alarm_session=session)
            save(ua.StatusCodes.Good)
            now+=timedelta(seconds=1);save(ua.StatusCodes.Bad)
            latest=client.get('/api/devices/motor-b/latest').json()
            self.assertEqual(latest['opcua']['communication'],'success')
            self.assertEqual(latest['opcua']['quality'],'bad')
            self.assertEqual(latest['status']['last_attempt_status'],'failure')
            self.assertFalse(latest['opcua']['eligible'])
            now+=timedelta(seconds=1)
            op.save_communication_failure(conn,now,'offline',alarm_session=session)
            latest=client.get('/api/devices/motor-b/latest').json()
            self.assertEqual(latest['opcua']['communication'],'failure')
            self.assertEqual(latest['opcua']['quality'],'bad')
            now+=timedelta(seconds=1);save(ua.StatusCodes.Good)
            self.assertTrue(client.get('/api/devices/motor-b/latest').json()['opcua']['eligible'])

class WireRecoveryTests(unittest.IsolatedAsyncioTestCase):
    async def test_communication_failure_then_real_read_recovers(self):
        import socket
        from opcua_simulator import build_server,publish
        from collect_opcua import collect
        import opcua_storage as op
        with socket.socket() as sock:
            sock.bind(('127.0.0.1',0)); port=sock.getsockname()[1]
        with sqlite3.connect(':memory:') as conn:
            op.initialize_opcua(conn); session=alarms.initialize_alarms(conn,device_id='motor-b')
            self.assertEqual(await collect(conn,port,1,1,session),1)
            self.assertEqual(conn.execute('select count(*) from opcua_diagnostics').fetchone()[0],0)
            self.assertEqual(conn.execute("select event_type from collection_events").fetchone()[0],'communication_error')
            server,node=await build_server(port)
            async with server:
                now=datetime.now(timezone.utc)
                await publish(node,65.3,'good','fresh',now,now,0)
                self.assertEqual(await collect(conn,port,1,1,session),0)
                self.assertEqual(conn.execute('select count(*) from measurements').fetchone()[0],1)
                await publish(node,65.3,'uncertain','fresh',datetime.now(timezone.utc),now,1)
                self.assertEqual(await collect(conn,port,1,1,session),1)
                self.assertEqual(conn.execute('select count(*) from measurements').fetchone()[0],1)
                self.assertEqual(conn.execute('select quality from opcua_diagnostics order by id desc limit 1').fetchone()[0],'uncertain')
