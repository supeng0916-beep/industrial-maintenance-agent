"""Transport identity and session fencing must protect persisted alarm evidence."""
import importlib.util
import sqlite3
import unittest
from datetime import datetime, timezone, timedelta
from asyncua import ua
from alarms import initialize_alarms
from opcua_storage import initialize_opcua, save_data_value, save_communication_failure


class SubscriptionStorageTests(unittest.TestCase):
    def setUp(self):
        self.conn = sqlite3.connect(':memory:')
        self.conn.row_factory = sqlite3.Row
        initialize_opcua(self.conn)
        self.session = initialize_alarms(self.conn, 1, device_id='motor-b')
        self.now = datetime.now(timezone.utc)

    def tearDown(self):
        self.conn.close()

    def runtime(self):
        self.assertIsNotNone(importlib.util.find_spec('opcua_runtime'), 'runtime module is required')
        import inspect
        self.assertIn('decision_clock',inspect.signature(save_data_value).parameters,'decision-time admission is required')
        import opcua_runtime
        opcua_runtime.initialize_runtime(self.conn, self.session, 'subscribe', self.now)
        opcua_runtime.update_runtime(self.conn, self.session, self.now, generation=1, state='subscribed')
        return opcua_runtime

    def data(self, value=85.0, source=None):
        return ua.DataValue(ua.Variant(value, ua.VariantType.Double), SourceTimestamp=source or self.now)

    def save(self, sequence=1, source=None, **kwargs):
        return save_data_value(self.conn, self.data(source=source), self.now,
            alarm_session=self.session, monotonic_now=100, generation=1,
            notification_identity=(self.session,1,78,sequence,0,0), **kwargs)

    def test_transport_duplicate_preserves_pending_and_has_no_second_diagnostic(self):
        runtime=self.runtime()
        self.save()
        pending=dict(self.conn.execute('SELECT * FROM temperature_alarm_state').fetchone())
        result=self.save()
        self.assertEqual(result['reason'], 'duplicate_notification')
        self.assertEqual(self.conn.execute('SELECT count(*) FROM opcua_diagnostics').fetchone()[0], 1)
        self.assertEqual(self.conn.execute('SELECT count(*) FROM measurements').fetchone()[0], 1)
        self.assertEqual(dict(self.conn.execute('SELECT * FROM temperature_alarm_state').fetchone()), pending)
        self.assertEqual(runtime.read_runtime(self.conn,self.now)['duplicate_count'], 1)

    def test_new_identity_same_source_rejects_and_clears_pending(self):
        self.runtime(); self.save(); result=self.save(sequence=2)
        self.assertEqual(result['reason'], 'duplicate')
        self.assertEqual(self.conn.execute('SELECT count(*) FROM opcua_diagnostics').fetchone()[0],2)
        self.assertIsNone(self.conn.execute('SELECT pending_at FROM temperature_alarm_state').fetchone()[0])

    def test_old_generation_and_session_cannot_write_or_clear_new_pending(self):
        runtime=self.runtime(); self.save()
        runtime.update_runtime(self.conn,self.session,self.now,generation=2)
        with self.assertRaises(sqlite3.OperationalError): self.save(sequence=2)
        old=self.session
        self.session=initialize_alarms(self.conn,1,device_id='motor-b')
        runtime.initialize_runtime(self.conn,self.session,'read',self.now)
        save_data_value(self.conn,self.data(source=self.now+timedelta(seconds=.1)),self.now+timedelta(seconds=.1),alarm_session=self.session,monotonic_now=101)
        before=dict(self.conn.execute('SELECT * FROM temperature_alarm_state').fetchone())
        with self.assertRaises(sqlite3.OperationalError):
            save_communication_failure(self.conn,self.now,'old failure',alarm_session=old)
        with self.assertRaises(sqlite3.OperationalError):
            runtime.update_runtime(self.conn,old,self.now,state='failed')
        self.assertEqual(dict(self.conn.execute('SELECT * FROM temperature_alarm_state').fetchone()),before)
        self.assertEqual(self.conn.execute('SELECT count(*) FROM collection_events').fetchone()[0],0)

    def test_identity_rollback_does_not_lose_retry_after_database_failure(self):
        self.runtime()
        self.conn.execute("CREATE TRIGGER fail_measurement BEFORE INSERT ON measurements BEGIN SELECT RAISE(FAIL,'disk failure'); END")
        with self.assertRaises(sqlite3.Error): self.save()
        self.conn.execute('DROP TRIGGER fail_measurement')
        self.assertTrue(self.save()['accepted'])
        self.assertEqual(self.conn.execute('SELECT count(*) FROM opcua_notification_receipts').fetchone()[0],1)

    def test_database_lock_delay_cannot_turn_old_callback_time_into_continuous_evidence(self):
        import time
        self.runtime()
        import inspect
        self.assertIn('processing_deadline',inspect.signature(save_data_value).parameters,'writer must reject delayed notifications after obtaining its DB lock')
        result=self.save(processing_deadline=time.monotonic()-1,decision_clock=lambda:self.now+timedelta(seconds=2))
        self.assertEqual(result['reason'],'notification_processing_delay')
        self.assertFalse(result['accepted'])
        self.assertEqual(self.conn.execute('SELECT count(*) FROM measurements').fetchone()[0],0)
        self.assertEqual(self.conn.execute('SELECT count(*) FROM opcua_notification_receipts').fetchone()[0],1)

    def test_runtime_read_is_readonly_and_ages_live_state(self):
        self.assertIsNotNone(importlib.util.find_spec('opcua_runtime'), 'runtime module is required')
        import inspect
        self.assertIn('decision_clock',inspect.signature(save_data_value).parameters,'decision-time admission is required')
        import opcua_runtime
        self.assertIsNone(opcua_runtime.read_runtime(self.conn,self.now))
        runtime=self.runtime()
        result=runtime.read_runtime(self.conn,self.now+timedelta(seconds=6))
        self.assertEqual(result['state'],'unknown')
        self.assertEqual(result['reported_state'],'subscribed')
        self.assertEqual(runtime.read_runtime(self.conn,self.now)['state'],'subscribed')

    def test_new_alarm_session_makes_old_runtime_unknown_before_new_runtime_initialization(self):
        runtime=self.runtime()
        initialize_alarms(self.conn,1,device_id='motor-b')
        value=runtime.read_runtime(self.conn,self.now)
        self.assertEqual(value['state'],'unknown')
        self.assertEqual(value['reported_state'],'subscribed')
        self.assertEqual(self.conn.execute('SELECT state FROM opcua_runtime').fetchone()[0],'subscribed')

    def test_source_expiring_at_decision_clears_pending_without_overwriting_receive_time(self):
        self.runtime(); self.save()
        received=self.now+timedelta(seconds=5)
        source=self.now+timedelta(seconds=.1)
        decision=received+timedelta(seconds=.2)
        result=save_data_value(self.conn,self.data(value=77.,source=source),received,alarm_session=self.session,
            generation=1,notification_identity=(self.session,1,78,2,0,0),decision_clock=lambda:decision)
        self.assertFalse(result['accepted'])
        self.assertEqual(result['reason'],'stale_at_decision')
        self.assertEqual(result['received_at'],received.isoformat(timespec='microseconds'))
        self.assertEqual(result['decision_at'],decision.isoformat(timespec='microseconds'))
        runtime=self.conn.execute('SELECT updated_at,last_notification_at FROM opcua_runtime').fetchone()
        self.assertEqual(tuple(runtime),(decision.isoformat(timespec='microseconds'),received.isoformat(timespec='microseconds')))
        self.assertEqual(self.conn.execute('SELECT occurred_at FROM collection_events ORDER BY id DESC LIMIT 1').fetchone()[0],decision.isoformat(timespec='microseconds'))
        self.assertEqual(self.conn.execute('SELECT count(*) FROM measurements').fetchone()[0],1)
        self.assertIsNone(self.conn.execute('SELECT pending_at FROM temperature_alarm_state').fetchone()[0])

    def test_source_expiring_at_decision_does_not_recover_active_alarm(self):
        self.runtime()
        for index in range(6):
            received=self.now+timedelta(seconds=index)
            save_data_value(self.conn,self.data(source=received),received,alarm_session=self.session,
                monotonic_now=100+index,generation=1,notification_identity=(self.session,1,78,index+1,0,0))
        received=self.now+timedelta(seconds=10)
        result=save_data_value(self.conn,self.data(value=77.,source=self.now+timedelta(seconds=5.1)),received,
            alarm_session=self.session,generation=1,notification_identity=(self.session,1,78,7,0,0),
            decision_clock=lambda:received+timedelta(seconds=.2))
        self.assertEqual(result['reason'],'stale_at_decision')
        self.assertEqual(self.conn.execute('SELECT count(*) FROM temperature_alarms WHERE recovered_at IS NULL').fetchone()[0],1)
        self.assertEqual(self.conn.execute('SELECT count(*) FROM measurements').fetchone()[0],6)

    def test_diagnostic_migration_preserves_old_rows_without_fabricating_decision_time(self):
        self.runtime(); self.save()
        self.conn.execute('ALTER TABLE opcua_diagnostics DROP COLUMN decision_at')
        initialize_opcua(self.conn)
        self.assertIsNone(self.conn.execute('SELECT decision_at FROM opcua_diagnostics').fetchone()[0])
        self.assertEqual(self.conn.execute('SELECT count(*) FROM measurements').fetchone()[0],1)

    def test_future_at_receive_cannot_become_acceptable_while_waiting(self):
        self.runtime()
        result=save_data_value(self.conn,self.data(source=self.now+timedelta(seconds=1)),self.now,
            alarm_session=self.session,generation=1,notification_identity=(self.session,1,78,1,0,0),
            decision_clock=lambda:self.now+timedelta(seconds=2))
        self.assertFalse(result['accepted'])
        self.assertEqual(result['reason'],'future')

    def test_source_gap_breaks_pending_even_if_received_quickly(self):
        self.runtime(); self.save()
        result=save_data_value(self.conn,self.data(source=self.now+timedelta(seconds=3)),self.now+timedelta(seconds=3),alarm_session=self.session,monotonic_now=101,generation=1,notification_identity=(self.session,1,78,2,0,0))
        self.assertTrue(result['accepted'])
        row=self.conn.execute('SELECT elapsed_seconds,pending_mono FROM temperature_alarm_state').fetchone()
        self.assertEqual(tuple(row),(0.0,101.0))
        self.assertEqual(self.conn.execute('SELECT event_type FROM collection_events').fetchone()[0],'evidence_interruption')

if __name__=='__main__': unittest.main()

class ActiveReadRuntimeTests(unittest.IsolatedAsyncioTestCase):
    async def test_read_failure_and_completion_are_visible_in_runtime(self):
        import socket
        from collect_opcua import collect
        from opcua_runtime import read_runtime
        conn=sqlite3.connect(':memory:'); self.addCleanup(conn.close)
        initialize_opcua(conn); session=initialize_alarms(conn,1,device_id='motor-b')
        with socket.socket() as sock:
            sock.bind(('127.0.0.1',0)); port=sock.getsockname()[1]
        self.assertEqual(await collect(conn,port,1,1,session),1)
        runtime=read_runtime(conn,datetime.now(timezone.utc))
        self.assertIsNotNone(runtime, 'active read lifecycle must be visible')
        self.assertEqual(runtime['mode'],'read')
        self.assertEqual(runtime['state'],'stopped')

class LockedWriterTests(unittest.IsolatedAsyncioTestCase):
    async def test_lock_wait_over_admission_deadline_cannot_recover_active_alarm(self):
        import asyncio
        import tempfile
        import time
        from pathlib import Path
        from opcua_runtime import initialize_runtime, update_runtime
        with tempfile.TemporaryDirectory() as directory:
            path=Path(directory)/'locked.sqlite3'
            conn=sqlite3.connect(path,timeout=2)
            self.addCleanup(conn.close)
            initialize_opcua(conn); session=initialize_alarms(conn,1,device_id='motor-b')
            now=datetime.now(timezone.utc)
            initialize_runtime(conn,session,'subscribe',now)
            update_runtime(conn,session,now,generation=1,state='subscribed')
            for index in range(6):
                timestamp=now-timedelta(seconds=5-index)
                save_data_value(conn,ua.DataValue(ua.Variant(85.,ua.VariantType.Double),SourceTimestamp=timestamp),timestamp,
                    alarm_session=session,monotonic_now=100+index,generation=1,
                    notification_identity=(session,1,78,index+1,0,0))
            self.assertEqual(conn.execute('SELECT count(*) FROM temperature_alarms WHERE recovered_at IS NULL').fetchone()[0],1)
            conn.execute('BEGIN IMMEDIATE')
            received=datetime.now(timezone.utc); deadline=time.monotonic()+1.5
            def write_while_locked():
                with sqlite3.connect(path,timeout=2) as writer:
                    return save_data_value(writer,ua.DataValue(ua.Variant(77.,ua.VariantType.Double),SourceTimestamp=received),received,
                        alarm_session=session,generation=1,notification_identity=(session,1,78,7,0,0),
                        processing_deadline=deadline,decision_clock=lambda:datetime.now(timezone.utc))
            task=asyncio.create_task(asyncio.to_thread(write_while_locked))
            await asyncio.sleep(1.7)
            conn.commit()
            result=await task
            self.assertEqual(result['reason'],'notification_processing_delay')
            self.assertFalse(result['accepted'])
            self.assertEqual(result['received_at'],received.isoformat(timespec='microseconds'))
            self.assertGreater((datetime.fromisoformat(result['decision_at'])-received).total_seconds(),1.5)
            self.assertEqual(conn.execute('SELECT count(*) FROM temperature_alarms WHERE recovered_at IS NULL').fetchone()[0],1)
            self.assertEqual(conn.execute('SELECT count(*) FROM measurements').fetchone()[0],6)
            self.assertEqual(conn.execute('SELECT count(*) FROM opcua_notification_receipts').fetchone()[0],7)
