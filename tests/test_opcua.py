"""独立 OPC UA 服务端与客户端的真实进程验收。"""

import json
from pathlib import Path
import queue
import signal
import socket
import subprocess
import sys
import threading
import time
import unittest

ROOT = Path(__file__).resolve().parents[1]


class OpcuaLabTests(unittest.TestCase):
    def start(self, module, *args):
        self.assertTrue((ROOT / "experiments/opcua/server.py").exists(), "OPC UA 实验尚未实现")
        process = subprocess.Popen([sys.executable, "-m", module, *map(str, args)],
                                   cwd=ROOT, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
        output = queue.Queue()
        def read_lines():
            for line in process.stdout:
                output.put(json.loads(line))
        reader = threading.Thread(target=read_lines, daemon=True)
        reader.start()
        self.addCleanup(self.stop, process, reader)
        return process, output, reader

    @staticmethod
    def stop(process, reader):
        if process.poll() is None:
            process.send_signal(signal.SIGINT)
        try:
            process.wait(timeout=6)
        except subprocess.TimeoutExpired:
            process.kill()
            process.wait()
        reader.join(timeout=2)
        if not process.stderr.closed:
            error = process.stderr.read()
            if error:
                print("OPC UA stderr:", error, flush=True)
            process.stderr.close()
            process.stdout.close()

    def event(self, output, kind):
        deadline = time.monotonic() + 12
        while time.monotonic() < deadline:
            try:
                item = output.get(timeout=max(.01, deadline - time.monotonic()))
            except queue.Empty:
                break
            print(json.dumps(item, ensure_ascii=False), flush=True)
            if item["event"] == kind:
                return item
        self.fail(f"未收到 {kind}")

    def command(self, port, *args):
        result = subprocess.run([sys.executable, "-m", "experiments.opcua.client", *args, "--port", str(port)],
                                cwd=ROOT, capture_output=True, text=True, timeout=10)
        self.assertEqual(result.returncode, 0, result.stderr)
        print(result.stdout.strip(), flush=True)
        return json.loads(result.stdout)

    def test_uri_resolution_double_and_actual_subscription(self):
        with socket.socket() as sock:
            sock.bind(("127.0.0.1", 0))
            port = sock.getsockname()[1]
        server, messages, reader = self.start("experiments.opcua.server", "--port", port, "--extra-namespace")
        self.event(messages, "server_ready")
        first = self.command(port, "read")
        self.assertEqual(first["NodeId"], "ns=3;s=MotorA.Temperature")
        self.assertEqual(first["Value"], 65.3)
        self.assertEqual(first["DataType"], "Double")
        self.assertEqual(first["StatusCode"], "Good")
        self.assertIsNotNone(first["SourceTimestamp"])
        subscriber, notifications, sub_reader = self.start("experiments.opcua.client", "subscribe", "--port", port)
        initial = self.event(notifications, "notification")
        self.assertEqual(initial["Value"], 65.3)
        self.command(port, "set-temperature", "72.8")
        changed = self.event(notifications, "notification")
        self.assertEqual(changed["Value"], 72.8)
        self.assertEqual(changed["StatusCode"], "Good")
        self.assertIsNone(changed["SourceTimestamp"])
        self.assertIsNotNone(changed["ReceivedAt"])
        before_repeat = self.command(port, "read")
        self.command(port, "set-temperature", "72.8")
        after_repeat = self.command(port, "read")
        self.assertNotEqual(before_repeat["ServerTimestamp"], after_repeat["ServerTimestamp"])
        # 观察一个明确窗口；这不是关于所有设备或所有情况下的必然承诺。
        time.sleep(1.2)
        extra = []
        while not notifications.empty():
            extra.append(notifications.get_nowait())
        self.assertFalse(any(item["event"] == "notification" for item in extra), extra)
        print("同值写入后1.2秒：新增数据变化通知0；主动读取仍成功。", flush=True)
        self.command(port, "set-temperature", "73")
        last = self.command(port, "read")
        self.assertEqual(last["Value"], 73.0)
        self.assertEqual(last["DataType"], "Double")
        subscriber.send_signal(signal.SIGINT)
        self.event(notifications, "subscription_deleted")
        subscriber.wait(timeout=6)
        self.assertEqual(subscriber.returncode, 130)
        self.assertIsNone(server.poll())

    def test_nonfinite_temperature_is_rejected_before_connect(self):
        for value in ("nan", "inf"):
            result = subprocess.run([sys.executable, "-m", "experiments.opcua.client", "set-temperature", value],
                                    cwd=ROOT, capture_output=True, text=True, timeout=5)
            self.assertEqual(result.returncode, 2)
            self.assertIn("有限", result.stderr)
