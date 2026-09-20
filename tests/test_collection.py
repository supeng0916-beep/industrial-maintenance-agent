"""检验真实采集进程的持久化、断线恢复与有界查询。"""

from contextlib import closing
from datetime import datetime, timedelta
import json
from pathlib import Path
import signal
import sqlite3
import subprocess
import sys
import tempfile
import time
import unittest

import test_modbus

ROOT = test_modbus.ROOT


class CollectionTests(unittest.TestCase):
    start_simulator = test_modbus.ModbusAcceptanceTests.start_simulator
    stop_simulator = staticmethod(test_modbus.ModbusAcceptanceTests.stop_simulator)

    def setUp(self):
        directory = tempfile.TemporaryDirectory()
        self.addCleanup(directory.cleanup)
        self.db = Path(directory.name) / "measurements.sqlite3"

    def run_cli(self, script, *args):
        return subprocess.run(
            [sys.executable, script, "--db", str(self.db), *map(str, args)],
            cwd=ROOT, capture_output=True, text=True, timeout=8,
        )

    def rows(self, table="measurements"):
        if not self.db.exists():
            return []
        with closing(sqlite3.connect(self.db)) as conn:
            conn.row_factory = sqlite3.Row
            if not conn.execute(
                "SELECT 1 FROM sqlite_master WHERE name=?", (table,)
            ).fetchone():
                return []
            return [dict(row) for row in conn.execute(f"SELECT * FROM {table} ORDER BY id")]

    def wait_for(self, predicate, process):
        deadline = time.monotonic() + 6
        while time.monotonic() < deadline:
            if predicate():
                return
            if process.poll() is not None:
                self.fail(f"采集器提前退出：{process.communicate()}")
            time.sleep(0.03)
        self.fail("等待数据库状态变化超时")

    def test_finite_samples_have_utc_metadata_and_survive_restart(self):
        _, port = self.start_simulator()
        result = self.run_cli("collect_temperature.py", "--port", port,
                              "--interval", 0.1, "--count", 3)
        self.assertEqual(result.returncode, 0, result.stderr)
        original = self.rows()
        self.assertEqual(len(original), 12)
        self.assertEqual([r["metric"] for r in original],["temperature","current","speed","running_state"]*3)
        self.assertTrue(all(original[i]["collected_at"] == original[i+1]["collected_at"] for i in (0,4,8)))
        times = [datetime.fromisoformat(row["collected_at"]) for row in original[::4]]
        self.assertTrue(all(t.utcoffset() == timedelta(0) for t in times))
        self.assertTrue(all(a < b for a, b in zip(times, times[1:])))
        for row in original:
            self.assertAlmostEqual(row["value"], {"temperature":65.3,"current":1.23,"speed":1450,"running_state":1}[row["metric"]])
            self.assertEqual((row["device_id"], row["metric"], row["unit"],
                              row["quality"], row["protocol"], row["source_time"]),
                             ("motor-a", row["metric"], {"temperature":"℃","current":"A","speed":"rpm","running_state":""}[row["metric"]], "good", "modbus_tcp", None))
        result = self.run_cli("collect_temperature.py", "--port", port, "--count", 1)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(len(self.rows()), 16)
        self.assertEqual(self.rows()[:12], original)
        query = self.run_cli("query_history.py", "--limit", 2)
        self.assertEqual(query.returncode, 0, query.stderr)
        self.assertEqual([r["id"] for r in json.loads(query.stdout)], [13, 9])
        empty = self.run_cli("query_history.py", "--device-id", "' OR 1=1 --")
        self.assertEqual(json.loads(empty.stdout), [])

    def test_running_collector_records_failures_then_recovers_to_728(self):
        server, port = self.start_simulator()
        collector = subprocess.Popen(
            [sys.executable, "collect_temperature.py", "--db", str(self.db),
             "--port", str(port), "--interval", "0.15"],
            cwd=ROOT, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True,
        )
        self.addCleanup(self.stop_simulator, collector)
        self.wait_for(lambda: len(self.rows()) >= 2, collector)
        self.stop_simulator(server)
        self.wait_for(lambda: len(self.rows("collection_events")) >= 1, collector)
        old_samples = self.rows()
        self.wait_for(lambda: len(self.rows("collection_events")) >= 8, collector)
        self.assertEqual(self.rows(), old_samples)
        self.start_simulator(728, port=port)
        self.wait_for(lambda: any(abs(r["value"] - 72.8) < 0.001 for r in self.rows()), collector)
        collector.send_signal(signal.SIGINT)
        out, err = collector.communicate(timeout=5)
        self.assertEqual(collector.returncode, 130, (out, err))
        self.assertEqual(self.rows()[:len(old_samples)], old_samples)
        query = self.run_cli("query_history.py", "--events", "--limit", 2)
        self.assertEqual(query.returncode, 0, query.stderr)
        events = json.loads(query.stdout)
        self.assertEqual(len(events), 2)
        self.assertGreater(events[0]["id"], events[1]["id"])
        self.assertTrue(all(e["message"] and e["event_type"] == "communication_error" for e in events))

    def test_failed_attempts_are_counted_and_never_make_measurements(self):
        server, port = self.start_simulator()
        self.stop_simulator(server)
        result = self.run_cli("collect_temperature.py", "--port", port,
                              "--interval", 0.05, "--count", 2)
        self.assertEqual(result.returncode, 1, result.stderr)
        self.assertIn("通信失败", result.stderr)
        self.assertEqual(self.rows(), [])
        self.assertEqual(len(self.rows("collection_events")), 8)

    def test_database_errors_and_query_bounds(self):
        missing = self.run_cli("query_history.py")
        self.assertEqual(missing.returncode, 1)
        self.assertIn("数据库", missing.stderr)
        self.assertFalse(self.db.exists())
        self.db.mkdir()
        bad = self.run_cli("collect_temperature.py", "--count", 1)
        self.assertEqual(bad.returncode, 1)
        self.assertIn("数据库", bad.stderr)
        for limit in (0, 1001):
            result = self.run_cli("query_history.py", "--limit", limit)
            self.assertEqual(result.returncode, 2)
        for interval in ("nan", "inf", "0", "-1"):
            result = self.run_cli("collect_temperature.py", "--interval", interval)
            self.assertEqual(result.returncode, 2)

    def test_insert_failure_and_lock_timeout_stop_without_fake_success(self):
        _, port = self.start_simulator()
        first = self.run_cli("collect_temperature.py", "--port", port, "--count", 1)
        self.assertEqual(first.returncode, 0, first.stderr)
        original = self.rows()
        with closing(sqlite3.connect(self.db)) as conn:
            conn.execute("""
                CREATE TRIGGER reject_measurement BEFORE INSERT ON measurements
                BEGIN SELECT RAISE(ABORT, '验收注入写入失败'); END
            """)
            conn.commit()
        failed = self.run_cli("collect_temperature.py", "--port", port, "--count", 1)
        self.assertEqual(failed.returncode, 1)
        self.assertIn("验收注入写入失败", failed.stderr)
        self.assertNotIn("已保存", failed.stdout)
        self.assertEqual(self.rows(), original)
        self.assertEqual(self.rows("collection_events"), [])
        with closing(sqlite3.connect(self.db)) as lock:
            lock.execute("DROP TRIGGER reject_measurement")
            lock.commit()
            lock.execute("BEGIN IMMEDIATE")
            blocked = self.run_cli("collect_temperature.py", "--port", port, "--count", 1)
            lock.rollback()
        self.assertEqual(blocked.returncode, 1)
        self.assertIn("database is locked", blocked.stderr)
        self.assertNotIn("已保存", blocked.stdout)
        self.assertEqual(self.rows(), original)


if __name__ == "__main__":
    unittest.main()
