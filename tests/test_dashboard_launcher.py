"""Verify the local launcher really serves one stack and cleans up its processes."""
import json
from pathlib import Path
import signal
import socket
import subprocess
import sys
import tempfile
import time
import unittest
from urllib.request import urlopen

ROOT = Path(__file__).resolve().parents[1]


class LauncherTests(unittest.TestCase):
    def test_occupied_port_is_reported_without_stopping_owner(self):
        with socket.socket() as occupied:
            occupied.bind(('127.0.0.1', 0))
            occupied.listen()
            port = occupied.getsockname()[1]
            result = subprocess.run([sys.executable, 'run_dashboard.py', '--web-port', str(port)], cwd=ROOT, capture_output=True, text=True, timeout=10)
            self.assertNotEqual(result.returncode, 0)
            self.assertIn('已被占用', result.stdout + result.stderr)
            self.assertEqual(occupied.getsockname()[1], port)

    def test_real_stack_serves_measurement_and_shutdown_frees_ports(self):
        sockets = [socket.socket() for _ in range(3)]
        for sock in sockets:
            sock.bind(('127.0.0.1', 0))
        ports = [sock.getsockname()[1] for sock in sockets]
        for sock in sockets:
            sock.close()
        with tempfile.TemporaryDirectory() as temp:
            logfile = open(Path(temp) / 'launcher.log', 'w+')
            proc = subprocess.Popen([sys.executable, 'run_dashboard.py', '--modbus-port', str(ports[0]), '--api-port', str(ports[1]), '--web-port', str(ports[2]), '--db', str(Path(temp) / 'samples.sqlite3'), '--current-raw', '234', '--speed-raw', '1600', '--running-state-raw', '0'], cwd=ROOT, stdout=logfile, stderr=subprocess.STDOUT)
            try:
                deadline = time.monotonic() + 25
                while True:
                    if proc.poll() is not None:
                        logfile.seek(0)
                        self.fail(logfile.read())
                    try:
                        with urlopen(f'http://127.0.0.1:{ports[2]}/api/devices/motor-a/latest', timeout=1) as response:
                            data = json.load(response)
                        if data.get('measurement'):
                            break
                    except (OSError, ValueError):
                        pass
                    if time.monotonic() > deadline:
                        self.fail('Stack did not become ready')
                    time.sleep(.1)
                self.assertEqual(data['measurement']['value'], 65.3)
                with urlopen(f'http://127.0.0.1:{ports[2]}/api/devices/motor-a/latest?metric=current', timeout=2) as response:
                    self.assertEqual(json.load(response)['measurement']['value'], 2.34)
                for metric, expected in [('speed',1600),('running_state',0)]:
                    with urlopen(f'http://127.0.0.1:{ports[2]}/api/devices/motor-a/latest?metric={metric}', timeout=2) as response:
                        self.assertEqual(json.load(response)['measurement']['value'],expected)
                with urlopen(f'http://127.0.0.1:{ports[2]}', timeout=2) as response:
                    self.assertIn('text/html', response.headers['Content-Type'])
            finally:
                if proc.poll() is None:
                    proc.send_signal(signal.SIGINT)
                proc.wait(timeout=15)
                logfile.close()
            self.assertEqual(proc.returncode, 130)
            for port in ports:
                with socket.socket() as sock:
                    self.assertNotEqual(sock.connect_ex(('127.0.0.1', port)), 0)
