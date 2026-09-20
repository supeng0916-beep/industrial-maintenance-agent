"""临时库与固定时钟测试 API 契约，不连接模拟器。"""

from concurrent.futures import ThreadPoolExecutor
from contextlib import closing
from datetime import datetime, timedelta, timezone
import importlib
from pathlib import Path
import sqlite3
import tempfile
import unittest

from fastapi.testclient import TestClient

from storage import initialize, open_database, save_failure, save_measurement

NOW = datetime(2026, 9, 16, 12, tzinfo=timezone.utc)


class ApiTests(unittest.TestCase):
    def setUp(self):
        self.assertIsNotNone(importlib.util.find_spec("api"), "只读 API 尚未实现")
        self.api = importlib.import_module("api")
        directory = tempfile.TemporaryDirectory()
        self.addCleanup(directory.cleanup)
        self.db = Path(directory.name) / "api.sqlite3"
        self.now = NOW
        self.client = TestClient(self.api.create_app(self.db, now=lambda: self.now))
        self.addCleanup(self.client.close)

    def initialize(self):
        with closing(open_database(self.db)) as conn:
            initialize(conn)

    def sample(self, age, value=65.3):
        with closing(open_database(self.db)) as conn:
            save_measurement(conn, value, (NOW - timedelta(seconds=age)).isoformat(timespec="microseconds"))

    def failure(self, age):
        with closing(open_database(self.db)) as conn:
            save_failure(conn, (NOW - timedelta(seconds=age)).isoformat(timespec="microseconds"), "通信失败")

    def latest(self):
        result = self.client.get("/api/devices/motor-a/latest")
        self.assertEqual(result.status_code, 200, result.text)
        return result.json()

    def test_missing_database_recovers_without_restart_and_empty_data(self):
        result = self.client.get("/api/devices")
        self.assertEqual(result.status_code, 503)
        self.assertEqual(result.json()["error"]["code"], "database_unavailable")
        self.assertFalse(self.db.exists())
        self.initialize()
        data = self.latest()
        self.assertIsNone(data["measurement"])
        self.assertEqual(data["status"]["last_attempt_status"], "unknown")
        self.assertFalse(data["status"]["has_data"])
        self.assertIsNone(data["status"]["data_age_seconds"])
        self.assertIsNone(data["status"]["is_stale"])
        devices = self.client.get("/api/devices").json()["devices"]
        self.assertEqual(devices[0]["id"], "motor-a")
        self.assertEqual(devices[0]["status"], data["status"])

    def test_exact_stale_boundary_and_last_success_stays_historical(self):
        self.initialize()
        self.sample(5)
        data = self.latest()
        self.assertEqual(data["status"]["data_age_seconds"], 5)
        self.assertFalse(data["status"]["is_stale"])
        self.now += timedelta(microseconds=1)
        self.assertTrue(self.latest()["status"]["is_stale"])
        self.now += timedelta(days=1)
        old = self.latest()
        self.assertTrue(old["status"]["is_stale"])
        self.assertEqual(old["status"]["last_attempt_status"], "success")
        self.assertEqual(old["measurement"], data["measurement"])
        self.assertNotIn("connection_status", old["status"])
        custom = TestClient(self.api.create_app(self.db, stale_after_seconds=10, now=lambda: NOW))
        with custom:
            self.assertFalse(custom.get("/api/devices/motor-a/latest").json()["status"]["is_stale"])

    def test_failure_then_recovery_compares_record_times_not_insert_order(self):
        self.initialize()
        self.failure(4)
        data = self.latest()
        self.assertIsNone(data["measurement"])
        self.assertEqual(data["status"]["last_attempt_status"], "failure")
        self.sample(10)
        data = self.latest()
        self.assertEqual(data["status"]["last_attempt_status"], "failure")
        self.assertEqual(data["status"]["last_attempt_at"], data["status"]["last_failure_at"])
        self.sample(1, 72.8)
        self.failure(20)  # 更晚插入，但事件实际更旧，不能覆盖最近尝试。
        data = self.latest()
        self.assertEqual(data["status"]["last_attempt_status"], "success")
        self.assertEqual(data["measurement"]["value"], 72.8)
        self.assertEqual(data["status"]["last_attempt_at"], data["status"]["last_success_at"])
        self.assertIsNotNone(data["status"]["last_failure_at"])
        self.failure(1)
        self.assertEqual(self.latest()["status"]["last_attempt_status"], "unknown")

    def test_history_utc_range_limit_order_and_empty_result(self):
        self.initialize()
        for age, value in ((1, 72.8), (3, 65.3), (2, 70.0)):
            self.sample(age, value)
        params = {"from": "2026-09-16T19:59:57+08:00", "to": "2026-09-16T12:00:00Z", "limit": 2}
        result = self.client.get("/api/devices/motor-a/history", params=params)
        self.assertEqual(result.status_code, 200, result.text)
        self.assertEqual([p["value"] for p in result.json()["points"]], [65.3, 70.0])
        self.assertEqual(result.json()["from"], "2026-09-16T11:59:57.000000+00:00")
        params["from"] = params["to"] = "2026-09-16T11:59:59Z"
        self.assertEqual(len(self.client.get("/api/devices/motor-a/history", params=params).json()["points"]), 1)
        params["from"] = params["to"] = "2026-09-16T12:00:00Z"
        self.assertEqual(self.client.get("/api/devices/motor-a/history", params=params).json()["points"], [])

    def test_bad_device_metric_dates_range_and_limit_have_consistent_errors(self):
        self.initialize()
        unknown = self.client.get("/api/devices/unknown/latest")
        self.assertEqual(unknown.status_code, 404)
        self.assertIn("error", unknown.json())
        base = {"from": "2026-09-16T00:00:00Z", "to": "2026-09-16T12:00:00Z"}
        for changes in ({"metric": "voltage"}, {"from": "invalid"}, {"from": "2026-09-16T00:00:00"},
                        {"to": "2026-09-15T00:00:00Z"}, {"to": "2026-09-18T00:00:00Z"},
                        {"limit": 0}, {"limit": 1001}, {"limit": "abc"}):
            with self.subTest(changes=changes):
                result = self.client.get("/api/devices/motor-a/history", params=base | changes)
                self.assertEqual(result.status_code, 422, result.text)
                self.assertEqual(set(result.json()["error"]), {"code", "message"})
        self.assertEqual(self.client.get("/api/devices/motor-a/history").status_code, 422)

    def test_readonly_concurrent_requests_and_locked_database(self):
        self.initialize()
        self.sample(1)
        before = self.db.read_bytes()
        with ThreadPoolExecutor(max_workers=4) as pool:
            codes = list(pool.map(lambda _: self.client.get("/api/devices/motor-a/latest").status_code, range(12)))
        self.assertEqual(codes, [200] * 12)
        self.assertEqual(self.db.read_bytes(), before)
        with closing(self.api.open_readonly_database(self.db)) as readonly:
            with self.assertRaises(sqlite3.OperationalError):
                readonly.execute("DELETE FROM measurements")
        with closing(sqlite3.connect(self.db)) as locked:
            locked.execute("BEGIN EXCLUSIVE")
            result = self.client.get("/api/devices/motor-a/latest")
            self.assertEqual(result.status_code, 503)
            self.assertEqual(result.json()["error"]["code"], "database_unavailable")
            locked.rollback()
        self.assertEqual(self.client.get("/api/devices/motor-a/latest").status_code, 200)


if __name__ == "__main__":
    unittest.main()
