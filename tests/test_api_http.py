"""真实启动 Uvicorn，通过 TCP HTTP 验收；仅使用临时数据库与空闲端口。"""

from concurrent.futures import ThreadPoolExecutor
from contextlib import closing
from datetime import datetime, timedelta, timezone
import json
from pathlib import Path
import signal
import socket
import sqlite3
import subprocess
import sys
import tempfile
import time
import unittest
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode
from urllib.request import urlopen

from storage import initialize, open_database, save_failure, save_measurement


class RealHttpTests(unittest.TestCase):
    def test_live_http_missing_database_recovery_and_readonly_concurrency(self):
        with tempfile.TemporaryDirectory() as directory:
            db = Path(directory) / "http.sqlite3"
            with socket.socket() as sock:
                sock.bind(("127.0.0.1", 0))
                port = sock.getsockname()[1]
            command = [sys.executable, "serve_api.py", "--db", str(db), "--port", str(port)]
            print("\nHTTP验收启动：", " ".join(command), flush=True)
            log_path = Path(directory) / "server.log"
            with log_path.open("w+") as log:
                process = subprocess.Popen(command, cwd=Path(__file__).resolve().parents[1], stdout=log, stderr=log)
                try:
                    def get(path):
                        try:
                            with urlopen(f"http://127.0.0.1:{port}{path}", timeout=5) as response:
                                return response.status, json.load(response)
                        except HTTPError as error:
                            with error:
                                return error.code, json.load(error)

                    deadline = time.monotonic() + 8
                    while True:
                        try:
                            status, data = get("/api/devices")
                            break
                        except URLError:
                            if time.monotonic() > deadline or process.poll() is not None:
                                self.fail("真实HTTP服务启动失败")
                            time.sleep(0.05)
                    self.assertEqual(status, 503)
                    self.assertFalse(db.exists())
                    print("缺库：", status, data, flush=True)
                    with closing(open_database(db)) as conn:
                        initialize(conn)
                    status, data = get("/api/devices/motor-a/latest")
                    self.assertEqual(status, 200)
                    self.assertIsNone(data["measurement"])
                    print("建库后无需重启：", status, data, flush=True)
                    now = datetime.now(timezone.utc)
                    old = (now - timedelta(seconds=10)).isoformat(timespec="microseconds")
                    with closing(open_database(db)) as conn:
                        save_measurement(conn, 65.3, old)
                    status, data = get("/api/devices/motor-a/latest")
                    self.assertTrue(data["status"]["is_stale"])
                    self.assertEqual(data["status"]["last_attempt_status"], "success")
                    self.assertEqual(data["measurement"]["collected_at"], old)
                    print("旧值仍保留原时间，已过期：", status, data, flush=True)
                    with closing(open_database(db)) as conn:
                        save_failure(conn, datetime.now(timezone.utc).isoformat(timespec="microseconds"), "HTTP验收注入通信失败事件")
                    status, data = get("/api/devices/motor-a/latest")
                    self.assertEqual(data["status"]["last_attempt_status"], "failure")
                    print("最近失败：", status, data["status"], flush=True)
                    with closing(open_database(db)) as conn:
                        save_measurement(conn, 72.8, datetime.now(timezone.utc).isoformat(timespec="microseconds"))
                    status, data = get("/api/devices/motor-a/latest")
                    self.assertEqual(data["status"]["last_attempt_status"], "success")
                    self.assertEqual(data["measurement"]["value"], 72.8)
                    print("后来成功覆盖最近尝试结论：", status, data, flush=True)
                    before = db.read_bytes()
                    with ThreadPoolExecutor(max_workers=4) as pool:
                        results = list(pool.map(lambda _: get("/api/devices/motor-a/latest"), range(12)))
                    self.assertTrue(all(code == 200 for code, _ in results))
                    self.assertEqual(db.read_bytes(), before)
                    print("并发12次HTTP读取：全部200，数据库文件逐字节不变", flush=True)
                    params = urlencode({"from": old, "to": (now + timedelta(minutes=1)).isoformat(), "limit": 1})
                    status, data = get("/api/devices/motor-a/history?" + params)
                    self.assertEqual(status, 200)
                    self.assertEqual([p["value"] for p in data["points"]], [65.3])
                    print("限量历史：", status, data, flush=True)
                    for path, expected in (("/api/devices/unknown/latest", 404), ("/api/devices/motor-a/history?limit=1001", 422)):
                        status, data = get(path)
                        self.assertEqual(status, expected)
                        print(path, status, data, flush=True)
                    with closing(sqlite3.connect(db)) as conn:
                        conn.execute("BEGIN EXCLUSIVE")
                        status, data = get("/api/devices")
                        self.assertEqual(status, 503)
                        conn.rollback()
                    print("独占锁：", status, data, flush=True)
                    self.assertEqual(get("/api/devices")[0], 200)
                finally:
                    if process.poll() is None:
                        process.send_signal(signal.SIGINT)
                    try:
                        process.wait(timeout=5)
                    except subprocess.TimeoutExpired:
                        process.kill()
                        process.wait()
                    log.seek(0)
                    print("服务日志：\n" + log.read(), flush=True)


if __name__ == "__main__":
    unittest.main()
