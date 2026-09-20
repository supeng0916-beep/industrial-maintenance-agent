"""Range contracts against real temporary SQLite snapshots."""
from datetime import datetime, timedelta, timezone
import importlib
import sqlite3
import unittest

from storage import initialize
from alarms import initialize_alarms

BASE = datetime(2026, 9, 17, tzinfo=timezone.utc)


def stamp(seconds):
    return (BASE + timedelta(seconds=seconds)).isoformat(timespec='microseconds')


class RangeTests(unittest.TestCase):
    def setUp(self):
        self.assertIsNotNone(importlib.util.find_spec('assistant.ranges'), 'Range query implementation missing')
        self.ranges = importlib.import_module('assistant.ranges')
        self.conn = sqlite3.connect(':memory:')
        self.conn.row_factory = sqlite3.Row
        self.addCleanup(self.conn.close)
        initialize(self.conn)

    def sample(self, second, value, metric='temperature', device='motor-a', quality='good'):
        self.conn.execute('INSERT INTO measurements (device_id,metric,value,unit,collected_at,quality,protocol) VALUES (?,?,?,?,?,?,?)',
                          (device, metric, value, 'fixture', stamp(second), quality, 'modbus_tcp'))

    def snapshot(self):
        self.conn.commit()
        self.conn.execute('PRAGMA query_only=ON')
        self.conn.execute('BEGIN')

    def history(self, metric='temperature', start=0, end=2000, limit=1000):
        return self.ranges.metric_history(self.conn, 'motor-a', metric, stamp(start), stamp(end), limit)

    def alarm(self, start, end=None, device='motor-a'):
        return self.conn.execute('''INSERT INTO temperature_alarms
            (device_id,metric,started_at,trigger_measurement_id,trigger_value,trigger_above,recover_below,
             recovered_at,recovery_measurement_id,recovery_value)
            VALUES (?,'temperature',?,1,81,80,78,?,?,?)''',
            (device, stamp(start), None if end is None else stamp(end), None if end is None else 2,
             None if end is None else 77)).lastrowid

    def alarms(self, status='all', limit=1000):
        return self.ranges.alarm_history(self.conn, 'motor-a', stamp(10), stamp(20), status, limit)

    def test_statistics_include_extremes_beyond_truncated_points(self):
        for second in range(1000):
            self.sample(second, 50)
        self.sample(1000, -5)
        self.sample(1001, 105)
        self.snapshot()
        data = self.history()
        self.assertEqual(data['statistics'], dict(count=1002, min=-5, max=105,
            first_collected_at=stamp(0), last_collected_at=stamp(1001), kind='numeric'))
        self.assertEqual(len(data['points']), 1000)
        self.assertEqual(data['returned_count'], 1000)
        self.assertTrue(data['truncated'])
        self.assertEqual(data['points'][-1]['collected_at'], stamp(999))
        self.assertEqual(data['unit'], '℃')
        self.assertEqual(data['time_basis'], 'collected_at')
        self.assertEqual(data['interval'], 'closed')
        self.assertTrue(data['limitations'])
        self.assertTrue(self.conn.in_transaction)

    def test_closed_endpoints_device_metric_quality_isolation(self):
        for second, value in [(9, -99), (10, 11), (20, 22), (21, 999)]:
            self.sample(second, value)
        self.sample(15, 555, device='motor-b')
        self.sample(15, 444, metric='current')
        self.sample(15, 333, quality='bad')
        self.snapshot()
        data = self.history(start=10, end=20)
        self.assertEqual(data['statistics']['count'], 2)
        self.assertEqual([p['value'] for p in data['points']], [11, 22])
        self.assertFalse(data['truncated'])

    def test_empty_has_null_statistics(self):
        self.snapshot()
        data = self.history()
        self.assertEqual(data['statistics'], dict(count=0, min=None, max=None,
            first_collected_at=None, last_collected_at=None, kind='numeric'))
        self.assertEqual(data['points'], [])
        self.assertFalse(data['truncated'])

    def test_enum_counts_full_range_and_preserves_unknown_state(self):
        for second, value in [(0, 0), (1, 1), (2, 1), (3, 9)]:
            self.sample(second, value, metric='running_state')
        self.snapshot()
        data = self.history(metric='running_state', limit=1)
        stats = data['statistics']
        self.assertEqual((stats['kind'], stats['min'], stats['max']), ('enum', None, None))
        self.assertEqual(stats['state_counts'], [dict(value=0, label='stopped', count=1),
            dict(value=1, label='running', count=2), dict(value=9, label='undefined', count=1)])
        self.assertTrue(data['truncated'])

    def test_alarms_overlap_closed_interval_counts_and_full_evidence(self):
        initialize_alarms(self.conn)
        active = self.alarm(1)
        for _ in range(25):
            self.alarm(11, 12)
        self.alarm(2, 10)  # Recovery at start still intersects.
        last = self.alarm(20, 21)  # Start at end still intersects.
        self.alarm(2, 9)
        self.alarm(21, 22)
        self.alarm(11, 12, device='motor-b')
        self.snapshot()
        data = self.alarms(limit=20)
        self.assertEqual((data['total'], data['matched_active_count']), (28, 1))
        self.assertEqual((data['device_total'], data['device_active_count']), (30, 1))
        self.assertEqual((data['returned_count'], data['truncated']), (20, True))
        self.assertEqual(data['items'][0]['id'], last)
        self.assertEqual(data['items'][0]['recovery_value'], 77)
        self.assertIn('first_exceeded_at', data['items'][0])
        self.assertEqual(self.alarms(status='active')['items'][0]['id'], active)
        recovered = self.alarms(status='recovered')
        self.assertEqual((recovered['total'], recovered['matched_active_count']), (27, 0))
        self.assertEqual(recovered['device_active_count'], 1)
        self.assertTrue(data['range_semantics'])

    def test_missing_alarm_table_is_unavailable_without_migration(self):
        self.snapshot()
        before = list(self.conn.execute('SELECT sql FROM sqlite_master'))
        data = self.alarms()
        self.assertIs(data.get('history_available'), False)
        self.assertEqual(data['items'], [])
        self.assertEqual((data['total'], data['device_total'], data['matched_active_count'], data['device_active_count']), (0, 0, 0, 0))
        self.assertEqual(list(self.conn.execute('SELECT sql FROM sqlite_master')), before)
        self.assertTrue(self.conn.in_transaction)

    def test_legacy_alarm_evidence_stays_legacy(self):
        self.conn.execute('''CREATE TABLE temperature_alarms (
            id INTEGER PRIMARY KEY, device_id TEXT, metric TEXT, started_at TEXT,
            trigger_measurement_id INTEGER, trigger_value REAL, trigger_above REAL,
            recover_below REAL, recovered_at TEXT, recovery_measurement_id INTEGER, recovery_value REAL)''')
        self.alarm(5)
        self.snapshot()
        data = self.alarms()
        self.assertIs(data.get('history_available'), True)
        self.assertNotIn('confirm_seconds', data['items'][0])
        self.assertEqual(data['items'][0]['trigger_value'], 81)
        self.assertTrue(self.conn.in_transaction)

    def test_actual_schema_errors_propagate_instead_of_becoming_empty(self):
        self.conn.execute('CREATE TABLE temperature_alarms (id INTEGER)')
        self.snapshot()
        with self.assertRaises(sqlite3.DatabaseError):
            self.alarms()
        self.conn.execute('ROLLBACK')
        self.conn.execute('PRAGMA query_only=OFF')
        self.conn.execute('DROP TABLE measurements')
        self.snapshot()
        with self.assertRaises(sqlite3.DatabaseError):
            self.history()
