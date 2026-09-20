"""Only random ports and temporary databases; exercise the actual collector CLI."""
import signal
import socket
import sqlite3
import subprocess
import sys
import tempfile
import time
import unittest
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]


class SubscriptionProcessTests(unittest.TestCase):
    def setUp(self):
        self.directory=tempfile.TemporaryDirectory()
        self.addCleanup(self.directory.cleanup)
        self.db=Path(self.directory.name)/'processes.sqlite3'

    def spawn(self,script,*args):
        process=subprocess.Popen([sys.executable,str(ROOT/script),*map(str,args)],stdout=subprocess.PIPE,stderr=subprocess.PIPE,text=True)
        self.addCleanup(self.stop,process)
        return process

    @staticmethod
    def stop(process):
        if process.poll() is None: process.send_signal(signal.SIGINT)
        try: process.communicate(timeout=6)
        except subprocess.TimeoutExpired: process.kill(); process.communicate()

    @staticmethod
    def port():
        with socket.socket() as sock:
            sock.bind(('127.0.0.1',0)); return sock.getsockname()[1]

    def wait(self,predicate,timeout=8):
        deadline=time.monotonic()+timeout
        while time.monotonic()<deadline:
            try:
                result=predicate()
                if result: return result
            except (sqlite3.Error,OSError): pass
            time.sleep(.03)
        self.fail('condition timed out')

    def server(self,script,*args):
        port=self.port(); process=self.spawn(script,'--port',port,*args)
        def ready():
            if process.poll() is not None: self.fail(str(process.communicate()))
            with socket.create_connection(('127.0.0.1',port),timeout=.1): return True
        self.wait(ready)
        return process,port

    def scalar(self,query):
        with sqlite3.connect(self.db) as conn:
            row=conn.execute(query).fetchone()
            return row[0] if row else None

    def test_modbus_a_and_subscribed_b_share_database_and_each_trigger(self):
        _,a_port=self.server('simulator.py','--raw',850)
        _,b_port=self.server('opcua_simulator.py','--value',85,'--extra-namespace')
        a=self.spawn('collect_temperature.py','--port',a_port,'--db',self.db,'--count',7)
        b=self.spawn('collect_opcua.py','--mode','subscribe','--port',b_port,'--db',self.db,'--count',14)
        for process in (a,b):
            output,error=process.communicate(timeout=15)
            self.assertEqual(process.returncode,0,(output,error))
        with sqlite3.connect(self.db) as conn:
            self.assertEqual(conn.execute('SELECT device_id,count(*) FROM measurements GROUP BY device_id ORDER BY device_id').fetchall(),[('motor-a',28),('motor-b',14)])
            self.assertEqual(conn.execute('SELECT device_id,count(*) FROM temperature_alarms GROUP BY device_id ORDER BY device_id').fetchall(),[('motor-a',1),('motor-b',1)])
            self.assertEqual(conn.execute('SELECT count(distinct session_id) FROM temperature_alarm_state').fetchone()[0],2)
            self.assertEqual(conn.execute('SELECT mode,state FROM opcua_runtime').fetchone(),('subscribe','stopped'))

    def test_new_read_process_fences_old_subscription_process(self):
        _,port=self.server('opcua_simulator.py','--value',85)
        old=self.spawn('collect_opcua.py','--mode','subscribe','--port',port,'--db',self.db)
        old_session=self.wait(lambda:self.scalar('SELECT session_id FROM opcua_runtime WHERE last_notification_at IS NOT NULL'))
        new=self.spawn('collect_opcua.py','--port',port,'--db',self.db,'--count',3)
        new_session=self.wait(lambda:(session if (session:=self.scalar('SELECT session_id FROM opcua_runtime')) and session!=old_session else None))
        output,error=old.communicate(timeout=6)
        self.assertEqual(old.returncode,1,(output,error))
        output,error=new.communicate(timeout=7)
        self.assertIn(new.returncode,(0,1),(output,error))  # its initial source may equal the old writer's watermark
        with sqlite3.connect(self.db) as conn:
            self.assertEqual(conn.execute('SELECT mode,state,session_id FROM opcua_runtime').fetchone(),('read','stopped',new_session))
            self.assertEqual(conn.execute('SELECT session_id FROM temperature_alarm_state').fetchone()[0],new_session)

    def test_sigint_stops_subscription_and_leaves_server_alive(self):
        server,port=self.server('opcua_simulator.py','--value',85)
        collector=self.spawn('collect_opcua.py','--mode','subscribe','--port',port,'--db',self.db)
        self.wait(lambda:self.scalar('SELECT count(*) FROM measurements'))
        collector.send_signal(signal.SIGINT)
        output,error=collector.communicate(timeout=7)
        self.assertEqual(collector.returncode,130,(output,error))
        self.assertIsNone(server.poll())
        with sqlite3.connect(self.db) as conn:
            self.assertEqual(conn.execute('SELECT state FROM opcua_runtime').fetchone()[0],'stopped')
            self.assertIsNone(conn.execute('SELECT pending_at FROM temperature_alarm_state').fetchone()[0])

if __name__=='__main__': unittest.main()
