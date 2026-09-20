"""Four-register protocol, atomic rounds, and read-only per-metric evidence."""
from contextlib import closing
from datetime import timedelta
import sqlite3
import unittest
import tempfile
from fastapi.testclient import TestClient
from api import create_app
import modbus_reader
import storage
from collect_temperature import collect
import test_current
from test_alarms import AlarmFixture, BASE


class FourProtocolTests(unittest.TestCase):
    start_simulator = test_current.BatchProtocolTests.start_simulator
    stop_simulator = staticmethod(test_current.BatchProtocolTests.stop_simulator)
    def test_configured_speed_and_stopped_state(self):
        _, port = self.start_simulator(speed=1600, running_state=0)
        self.assertEqual(modbus_reader.read_points(port),
                         {'temperature':65.3,'current':1.23,'speed':1600,'running_state':0})

    def test_invalid_enum_protocol_succeeds_but_collector_saves_only_failures(self):
        from alarms import initialize_alarms
        for raw in (2, 7):
            with self.subTest(raw=raw), tempfile.TemporaryDirectory() as directory:
                server, port = self.start_simulator(running_state=raw)
                self.assertEqual(modbus_reader.read_registers(port,0,4), [653,123,1450,raw])
                path = directory + '/invalid.sqlite3'
                with closing(storage.open_database(path)) as conn:
                    storage.initialize(conn)
                    session = initialize_alarms(conn)
                    self.assertEqual(collect(conn,port,.01,1,session),1)
                    self.assertEqual(conn.execute('SELECT count(*) FROM measurements').fetchone()[0],0)
                    rows=conn.execute('SELECT metric,event_type,message FROM collection_events ORDER BY id').fetchall()
                    self.assertEqual([r[0] for r in rows],['temperature','current','speed','running_state'])
                    self.assertTrue(all(r[1]=='data_validation_error' and f'raw={raw}' in r[2] and 'running_state' in r[2] for r in rows))
                with TestClient(create_app(path)) as client:
                    for metric in ('temperature','current','speed','running_state'):
                        response=client.get('/api/devices/motor-a/latest',params={'metric':metric})
                        self.assertEqual(response.status_code,200)
                        result=response.json()
                        self.assertIsNone(result['measurement'])
                        self.assertEqual(result['status']['last_attempt_status'],'failure')
                        self.assertEqual(result['status']['last_failure_type'],'data_validation_error')
                        self.assertIn(f'raw={raw}',result['status']['last_failure_message'])
                self.stop_simulator(server)



class FourStorageTests(AlarmFixture):
    round = test_current.CurrentStorageTests.round
    def test_fourth_insert_rolls_back_whole_round_and_alarm(self):
        self.enable()
        for t in range(5): self.round(t)
        before=self.alarm()['pending']
        self.conn.execute("CREATE TRIGGER reject_state BEFORE INSERT ON measurements WHEN NEW.metric='running_state' BEGIN SELECT RAISE(ABORT,'fourth write'); END")
        with self.assertRaises(sqlite3.IntegrityError): self.round(5)
        self.assertEqual(self.conn.execute('SELECT count(*) FROM measurements').fetchone()[0],20)
        self.assertEqual(self.alarm()['pending'],before)
        self.assertEqual(self.alarm()['total'],0)

    def test_validation_failure_resets_pending_retains_old_samples_and_active_alarm(self):
        self.enable()
        for t in range(6): self.round(t)
        active=self.alarm()["active"]
        self.round(6,79)
        self.now=BASE+timedelta(seconds=7)
        storage.save_round_failure(self.conn,self.now.isoformat(timespec='microseconds'),
            'running_state raw=2',alarm_session=self.session,event_type='data_validation_error')
        self.assertIsNone(self.alarm()['pending'])
        self.assertEqual(self.alarm()['total'],1)
        self.assertEqual(self.alarm()['active'],active)
        for metric in ('temperature','current','speed','running_state'):
            result=self.client.get('/api/devices/motor-a/latest',params={'metric':metric}).json()
            self.assertEqual(result['status']['last_attempt_status'],'failure')
            self.assertEqual(result['status']['last_failure_type'],'data_validation_error')
            self.assertIn('raw=2',result['status']['last_failure_message'])
            self.assertEqual(result['measurement']['collected_at'],(BASE+timedelta(seconds=6)).isoformat(timespec='microseconds'))
        self.assertEqual(self.conn.execute('SELECT count(*) FROM measurements').fetchone()[0],28)

    def test_no_samples_validation_failure_is_visible(self):
        self.enable()
        storage.save_round_failure(self.conn,BASE.isoformat(timespec='microseconds'),'running_state raw=2',
            alarm_session=self.session,event_type='data_validation_error')
        for metric in ('speed','running_state'):
            result=self.client.get('/api/devices/motor-a/latest',params={'metric':metric}).json()
            self.assertIsNone(result['measurement'])
            self.assertEqual(result['status']['last_attempt_status'],'failure')
            self.assertEqual(result['status']['last_failure_type'],'data_validation_error')
            self.assertEqual(result['status']['last_failure_message'],'running_state raw=2')

    def test_old_two_point_database_does_not_invent_new_point_timestamps(self):
        storage.save_measurement(self.conn,65.3,BASE.isoformat(timespec='microseconds'))
        with self.conn: storage.insert_measurement(self.conn,'current',1.23,BASE.isoformat(timespec='microseconds'))
        before=self.path.read_bytes()
        self.assertEqual(self.client.get('/api/devices').json()['devices'][0]['metrics'],['temperature','current','speed','running_state'])
        for metric in ('speed','running_state'):
            result=self.client.get('/api/devices/motor-a/latest',params={'metric':metric})
            self.assertEqual(result.status_code,200)
            data=result.json()
            self.assertIsNone(data['measurement'])
            self.assertIsNone(data['status']['last_success_at'])
            self.assertEqual(data['status']['last_attempt_status'],'unknown')
            self.assertIsNone(data['alarm'])
        self.assertEqual(self.path.read_bytes(),before)

    def test_new_point_history_and_independent_freshness(self):
        self.enable()
        self.round(0,65.3)
        self.now=BASE+timedelta(seconds=6)
        storage.save_measurement(self.conn,66,self.now.isoformat(timespec='microseconds'))
        for metric,value in [('speed',1450),('running_state',1)]:
            result=self.client.get('/api/devices/motor-a/latest',params={'metric':metric}).json()
            self.assertTrue(result['status']['is_stale'])
            self.assertIsNone(result['alarm'])
            history=self.client.get('/api/devices/motor-a/history',params={'metric':metric,'from':BASE.isoformat(),'to':self.now.isoformat()}).json()
            self.assertEqual([p['value'] for p in history['points']],[value])

    def test_storage_rejects_invalid_enum_before_any_write(self):
        self.enable()
        self.round(0)
        before=self.alarm()['pending']
        with self.assertRaisesRegex(ValueError,'running_state'):
            storage.save_round(self.conn,{'temperature':81,'current':1.23,'speed':1450,'running_state':2},
                (BASE+timedelta(seconds=1)).isoformat(timespec='microseconds'),alarm_session=self.session,monotonic_now=1)
        self.assertEqual(self.conn.execute('SELECT count(*) FROM measurements').fetchone()[0],4)
        self.assertEqual(self.alarm()['pending'],before)

    def test_validation_fourth_event_failure_rolls_back_events_and_pending(self):
        self.enable()
        self.round(0)
        before=self.alarm()['pending']
        self.conn.execute("CREATE TRIGGER reject_event BEFORE INSERT ON collection_events WHEN NEW.metric='running_state' BEGIN SELECT RAISE(ABORT,'fourth event'); END")
        with self.assertRaises(sqlite3.IntegrityError):
            storage.save_round_failure(self.conn,(BASE+timedelta(seconds=1)).isoformat(timespec='microseconds'),
                'running_state raw=2',alarm_session=self.session,event_type='data_validation_error')
        self.assertEqual(self.conn.execute('SELECT count(*) FROM collection_events').fetchone()[0],0)
        self.assertEqual(self.alarm()['pending'],before)

    def test_validation_failure_clears_pending_and_later_success_recovers(self):
        self.enable()
        self.round(0)
        self.assertIsNotNone(self.alarm()['pending'])
        self.now=BASE+timedelta(seconds=1)
        storage.save_round_failure(self.conn,self.now.isoformat(timespec='microseconds'),'running_state raw=2',
            alarm_session=self.session,event_type='data_validation_error')
        self.assertIsNone(self.alarm()['pending'])
        self.round(2,65.3)
        for metric in ('temperature','current','speed','running_state'):
            result=self.client.get('/api/devices/motor-a/latest',params={'metric':metric}).json()
            self.assertEqual(result['status']['last_attempt_status'],'success')
            self.assertEqual(result['measurement']['collected_at'],self.now.isoformat(timespec='microseconds'))
        self.assertEqual(self.alarm()['current'],'clear')
