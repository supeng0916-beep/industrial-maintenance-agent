"""随机端口、临时库的两个真实采集进程隔离验收。"""
import subprocess
import socket
import sqlite3
import sys
import tempfile
import time
import unittest
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]

class DualCollectorTests(unittest.TestCase):
    def spawn(self,script,*args):
        p=subprocess.Popen([sys.executable,str(ROOT/script),*map(str,args)],stdout=subprocess.PIPE,stderr=subprocess.PIPE,text=True)
        self.addCleanup(self.stop,p)
        return p

    @staticmethod
    def stop(p):
        if p.poll() is None: p.terminate()
        try: p.communicate(timeout=5)
        except subprocess.TimeoutExpired: p.kill(); p.communicate()

    def port(self):
        with socket.socket() as s:
            s.bind(('127.0.0.1',0)); return s.getsockname()[1]

    def wait_port(self,port,p):
        until=time.monotonic()+10
        while time.monotonic()<until:
            if p.poll() is not None: self.fail(str(p.communicate()))
            try:
                with socket.create_connection(('127.0.0.1',port),timeout=.1): return
            except OSError: time.sleep(.03)
        self.fail('server timeout')

    def test_dual_collectors_same_database_alarm_sessions(self):
        with tempfile.TemporaryDirectory() as directory:
            db=Path(directory)/'dual.sqlite3'
            a_port,b_port=self.port(),self.port()
            sa=self.spawn('simulator.py','--port',a_port,'--raw',850)
            sb=self.spawn('opcua_simulator.py','--port',b_port,'--value',85,'--extra-namespace')
            self.wait_port(a_port,sa); self.wait_port(b_port,sb)
            ca=self.spawn('collect_temperature.py','--port',a_port,'--db',db,'--count',7)
            cb=self.spawn('collect_opcua.py','--port',b_port,'--db',db,'--count',7)
            for p in (ca,cb):
                out,err=p.communicate(timeout=12)
                self.assertEqual(p.returncode,0,(out,err))
            with sqlite3.connect(db) as conn:
                self.assertEqual(conn.execute('select device_id,count(*) from measurements group by device_id order by device_id').fetchall(),[('motor-a',28),('motor-b',7)])
                self.assertEqual(conn.execute('select device_id,count(*) from temperature_alarms group by device_id order by device_id').fetchall(),[('motor-a',1),('motor-b',1)])
                self.assertEqual(conn.execute('select count(distinct session_id) from temperature_alarm_state').fetchone()[0],2)
            self.stop(sa); self.stop(sb)
