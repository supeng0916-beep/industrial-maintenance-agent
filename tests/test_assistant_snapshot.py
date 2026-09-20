"""真实SQLite并发快照与超时，不连接现有练习库。"""
import sqlite3
import tempfile
import time
import unittest
from datetime import datetime, timezone, timedelta
from pathlib import Path
from unittest.mock import patch
from storage import initialize, open_database
from assistant.contracts import QueryError
from assistant.query_service import QueryService
from assistant.tools import ReadOnlyTools

NOW=datetime(2026,9,17,12,tzinfo=timezone.utc)

class SnapshotTests(unittest.TestCase):
    def setUp(self):
        folder=tempfile.TemporaryDirectory();self.addCleanup(folder.cleanup)
        self.path=Path(folder.name)/'snapshot.db'
        self.writer=open_database(self.path);self.addCleanup(self.writer.close)
        initialize(self.writer)
        self.tools=ReadOnlyTools(self.path,now=lambda:NOW)

    def sample(self, metric, value, stamp=None):
        self.writer.execute('''INSERT INTO measurements(device_id,metric,value,unit,collected_at,quality,protocol)
           VALUES ('motor-a',?,?,?,?,'good','modbus_tcp')''',(metric,value,'A' if metric=='current' else '℃',(stamp or NOW).isoformat(timespec='microseconds')))
        self.writer.commit()

    def change_before_second_measurement_select(self, action):
        original=sqlite3.connect
        count=0
        def connect(*args,**kwargs):
            conn=original(*args,**kwargs)
            def trace(sql):
                nonlocal count
                if sql.lstrip().upper().startswith('SELECT') and 'FROM measurements' in sql:
                    count+=1
                    if count==2: action()
            conn.set_trace_callback(trace)
            return conn
        return patch('assistant.query_service.sqlite3.connect',side_effect=connect)

    def test_status_all_metrics_share_snapshot_during_writer_commit(self):
        self.writer.execute('PRAGMA journal_mode=WAL')
        self.sample('temperature',65.3);self.sample('current',1.23)
        with self.change_before_second_measurement_select(lambda:self.sample('current',99)):
            result=self.tools.get_device_status('motor-a')
        self.assertTrue(result['ok'],result)
        self.assertEqual(result['data']['metrics']['current']['measurement']['value'],1.23)
        self.assertEqual(self.writer.execute("SELECT value FROM measurements WHERE metric='current' ORDER BY id DESC LIMIT 1").fetchone()[0],99)
        self.assertEqual({m['status']['checked_at'] for m in result['data']['metrics'].values()},{NOW.isoformat(timespec='microseconds')})

    def test_history_count_and_details_share_snapshot_during_writer_commit(self):
        self.writer.execute('PRAGMA journal_mode=WAL')
        self.sample('temperature',65.3)
        with self.change_before_second_measurement_select(lambda:self.sample('temperature',999)):
            result=self.tools.query_metric_history('motor-a','temperature',NOW.isoformat(),NOW.isoformat())
        self.assertTrue(result['ok'],result)
        data=result['data'];self.assertEqual(data['statistics']['count'],1)
        self.assertEqual(data['statistics']['max'],65.3)
        self.assertEqual(len(data['points']),1)
        self.assertEqual(self.writer.execute('select count(*) from measurements').fetchone()[0],2)

    def test_lock_wait_is_bounded_and_not_empty(self):
        self.writer.execute('BEGIN EXCLUSIVE')
        started=time.monotonic()
        result=self.tools.get_device_status('motor-a')
        elapsed=time.monotonic()-started
        self.writer.rollback()
        self.assertFalse(result['ok'])
        self.assertEqual(result['error']['code'],'database_unavailable')
        self.assertLess(elapsed,1)

    def test_actual_sql_progress_timeout_and_connection_closed(self):
        service=QueryService(self.path,timeout_seconds=.03)
        started=time.monotonic(); held=None
        with self.assertRaises(QueryError) as raised:
            with service.snapshot() as conn:
                held=conn
                conn.execute('WITH RECURSIVE n(x) AS (VALUES(1) UNION ALL SELECT x+1 FROM n WHERE x<100000000) SELECT sum(x) FROM n').fetchone()
        self.assertEqual(raised.exception.code,'query_timeout')
        self.assertLess(time.monotonic()-started,.8)
        with self.assertRaises(sqlite3.ProgrammingError): held.execute('select 1')

    def test_readonly_connection_rejects_write_and_budget_covers_multiple_queries(self):
        with QueryService(self.path).snapshot() as conn:
            with self.assertRaises(sqlite3.OperationalError): conn.execute('DELETE FROM measurements')
        service=QueryService(self.path,timeout_seconds=.02)
        with self.assertRaises(QueryError) as raised:
            with service.snapshot() as conn:
                conn.execute('select 1').fetchone()
                time.sleep(.03)
                conn.execute('select 2').fetchone()
        self.assertEqual(raised.exception.code,'query_timeout')
