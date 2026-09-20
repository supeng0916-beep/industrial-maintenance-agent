"""真实子进程验收；错误地址、倍率或失败时输出假值都会使测试失败。"""

from pathlib import Path
import socket
import subprocess
import sys
import time
import unittest

from pymodbus.client import ModbusTcpClient

ROOT = Path(__file__).resolve().parents[1]


class ModbusAcceptanceTests(unittest.TestCase):
    def start_simulator(self, raw=None, port=None, speed=None, running_state=None):
        if port is None:
            with socket.socket() as sock:
                sock.bind(("127.0.0.1", 0))
                port = sock.getsockname()[1]
        command = [sys.executable, "simulator.py", "--port", str(port)]
        if raw is not None:
            command += ["--raw", str(raw)]
        if speed is not None:
            command += ["--speed-raw", str(speed)]
        if running_state is not None:
            command += ["--running-state-raw", str(running_state)]
        process = subprocess.Popen(
            command, cwd=ROOT, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
            text=True,
        )
        self.addCleanup(self.stop_simulator, process)
        deadline = time.monotonic() + 5
        while time.monotonic() < deadline:
            if process.poll() is not None:
                self.fail(f"模拟器提前退出：{process.communicate()}")
            try:
                with socket.create_connection(("127.0.0.1", port), timeout=0.1):
                    return process, port
            except OSError:
                time.sleep(0.05)
        self.fail("模拟器未在 5 秒内开始监听")

    @staticmethod
    def stop_simulator(process):
        if process.poll() is None:
            process.terminate()
        try:
            process.communicate(timeout=3)
        except subprocess.TimeoutExpired:
            process.kill()
            process.communicate()

    def read_once(self, port):
        return subprocess.run(
            [sys.executable, "read_temperature.py", "--port", str(port)],
            cwd=ROOT, capture_output=True, text=True, timeout=5,
        )

    def assert_sample(self, port, raw, temperature):
        # 独立指定协议地址，避免两个程序同时用错地址却相互通过。
        with ModbusTcpClient("127.0.0.1", port=port) as client:
            response = client.read_holding_registers(0, count=1, device_id=1)
            self.assertFalse(response.isError())
            self.assertEqual(response.registers, [raw])
        result = self.read_once(port)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn(f"原始值：{raw}", result.stdout)
        self.assertIn("倍率：0.1", result.stdout)
        self.assertIn(f"温度：{temperature}℃", result.stdout)
        self.assertEqual(result.stderr, "")

    def test_default_653_at_protocol_address_zero(self):
        _, port = self.start_simulator()
        self.assert_sample(port, 653, "65.3")

    def test_configured_728(self):
        _, port = self.start_simulator(728)
        self.assert_sample(port, 728, "72.8")

    def test_stopped_simulator_has_no_sample_and_nonzero_exit(self):
        process, port = self.start_simulator()
        self.assert_sample(port, 653, "65.3")
        self.stop_simulator(process)
        result = self.read_once(port)
        self.assertEqual(result.returncode, 1)
        self.assertIn("通信失败", result.stderr)
        self.assertEqual(result.stdout, "")


if __name__ == "__main__":
    unittest.main()
