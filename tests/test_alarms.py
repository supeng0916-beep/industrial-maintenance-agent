"""真实 SQLite 与只读 HTTP 验证告警，所有文件在临时目录。"""
from contextlib import closing
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timedelta, timezone
from pathlib import Path
import sqlite3
import tempfile
import unittest
from fastapi.testclient import TestClient
import storage
from api import create_app

BASE = datetime(2026, 9, 16, 12, tzinfo=timezone.utc)

class AlarmFixture(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.path = Path(self.temp.name) / 'alarm.sqlite3'
        self.conn = storage.open_database(self.path)
        self.addCleanup(self.conn.close)
        storage.initialize(self.conn)
        self.now = BASE
        self.client = TestClient(create_app(self.path, now=lambda: self.now))
        self.addCleanup(self.client.close)

    def enable(self):
        import alarms
        self.session = alarms.initialize_alarms(self.conn)

    def sample(self, value):
        self.now += timedelta(seconds=1)
        storage.save_measurement(self.conn, value, self.now.isoformat(timespec='microseconds'), evaluate_alarm=True,
                                 alarm_session=getattr(self, "session", None), monotonic_now=(self.now-BASE).total_seconds())

    def trigger(self, value=81):
        for _ in range(6):
            self.sample(value)

    def alarm(self):
        response = self.client.get('/api/devices/motor-a/alarms')
        self.assertEqual(response.status_code, 200, response.text)
        return response.json()



class AlarmTests(AlarmFixture):
    def test_legacy_database_unknown_and_no_get_migration_or_replay(self):
        storage.save_measurement(self.conn, 90, BASE.isoformat(timespec='microseconds'))
        before = self.path.read_bytes()
        self.assertEqual(self.alarm()['current'], 'not_enabled')
        self.assertEqual(self.path.read_bytes(), before)
        self.enable()
        self.assertEqual(self.alarm()['current'], 'unknown')
        self.assertEqual(self.alarm()['history'], [])
        self.sample(65)
        self.assertEqual(self.alarm()['current'], 'clear')

    def test_boundaries_continuous_high_restart_recovery_and_retrigger(self):
        self.enable()
        self.sample(80)
        self.assertEqual(self.alarm()['current'],'clear')
        self.trigger(80.1)
        for value, current, total in [(90,'active',1),(80,'active',1),(78,'active',1)]:
            self.sample(value)
            result = self.alarm()
            self.assertEqual((result['current'],len(result['history'])),(current,total))
        self.conn.close()
        self.conn = storage.open_database(self.path)
        self.addCleanup(self.conn.close)
        self.enable()
        self.sample(88)
        self.assertEqual(len(self.alarm()['history']),1)
        self.sample(77.9)
        result = self.alarm()
        self.assertEqual(result['current'],'clear')
        event = result['history'][0]
        self.assertEqual((event['trigger_value'],event['recovery_value']),(80.1,77.9))
        self.assertEqual(event['recovered_at'],self.now.isoformat(timespec='microseconds'))
        for prefix in ('trigger','recovery'):
            row = self.conn.execute('SELECT value,collected_at FROM measurements WHERE id=?',(event[prefix+'_measurement_id'],)).fetchone()
            self.assertEqual(row,(event[prefix+'_value'],event['started_at' if prefix=='trigger' else 'recovered_at']))
        self.trigger()
        self.assertEqual(len(self.alarm()['history']),2)
        self.assertNotEqual(self.alarm()['active']['id'],event['id'])

    def test_failure_stale_and_unassessed_sample_never_clear_active(self):
        self.enable()
        self.trigger()
        active = self.alarm()['active']
        self.now += timedelta(seconds=1)
        storage.save_failure(self.conn,self.now.isoformat(timespec='microseconds'),'offline')
        self.assertEqual(self.alarm()['current'],'unknown')
        self.assertEqual(self.alarm()['active'],active)
        self.sample(79)
        self.assertEqual(self.alarm()['current'],'active')
        self.now += timedelta(seconds=6)
        self.assertEqual(self.alarm()['current'],'unknown')
        self.assertEqual(self.alarm()['active'],active)
        storage.save_measurement(self.conn,60,self.now.isoformat(timespec='microseconds'))
        self.assertEqual(self.alarm()['current'],'unknown')
        self.assertEqual(self.alarm()['active'],active)

    def test_recovery_write_failure_rolls_back_measurement_and_state(self):
        self.enable()
        self.trigger()
        self.conn.execute("CREATE TRIGGER fail_recovery BEFORE UPDATE ON temperature_alarms BEGIN SELECT RAISE(ABORT,'test failure'); END")
        with self.assertRaises(sqlite3.IntegrityError):
            self.sample(77)
        self.assertEqual(self.conn.execute('SELECT count(*) FROM measurements').fetchone()[0],6)
        self.assertEqual(self.alarm()['current'],'active')

    def test_parallel_collectors_create_one_active_alarm(self):
        self.enable()
        self.trigger()
        def collect_one(index):
            with closing(storage.open_database(self.path)) as conn:
                storage.save_measurement(conn, 81, (BASE + timedelta(microseconds=index)).isoformat(timespec='microseconds'), evaluate_alarm=True, alarm_session=self.session, monotonic_now=10+index)
        with ThreadPoolExecutor(max_workers=4) as pool:
            list(pool.map(collect_one, range(12)))
        self.assertEqual(self.conn.execute('SELECT count(*) FROM measurements').fetchone()[0], 18)
        self.assertEqual(self.alarm()['total'], 1)
        self.assertIsNotNone(self.alarm()['active'])

    def test_invalid_temperature_or_missing_rule_cannot_commit(self):
        for value in (float('nan'), float('inf'), float('-inf')):
            with self.assertRaises(ValueError):
                self.sample(value)
        self.assertEqual(self.conn.execute('SELECT count(*) FROM measurements').fetchone()[0], 0)
        with self.assertRaises(sqlite3.OperationalError):
            self.sample(81)
        self.assertEqual(self.conn.execute('SELECT count(*) FROM measurements').fetchone()[0], 0)

    def test_readonly_latest_consistency_history_limit_and_invalid_device(self):
        self.enable()
        for _ in range(23):
            self.trigger()
            self.sample(77)
        before = self.path.read_bytes()
        data = self.alarm()
        self.assertEqual(len(data['history']),20)
        self.assertEqual(data['history'][0]['id'],23)
        self.assertEqual(data['total'],23)
        self.assertEqual(self.client.get('/api/devices/motor-a/latest').json()['alarm'],data)
        self.assertEqual(self.client.get('/api/devices/wrong/alarms').status_code,404)
        self.assertEqual(self.path.read_bytes(),before)

if __name__ == '__main__':
    unittest.main()
