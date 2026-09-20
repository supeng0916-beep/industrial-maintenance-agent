from contextlib import closing
from datetime import timedelta
import sqlite3
import socket
import subprocess
import sys
import tempfile
import time
import unittest
from unittest.mock import patch
from types import SimpleNamespace
import test_modbus
from test_alarms import AlarmFixture, BASE
import storage
import modbus_reader

class BatchProtocolTests(unittest.TestCase):
    start_simulator = test_modbus.ModbusAcceptanceTests.start_simulator
    stop_simulator = staticmethod(test_modbus.ModbusAcceptanceTests.stop_simulator)

    def test_actual_batch_address_zero_and_scaling(self):
        _,port=self.start_simulator()
        from pymodbus.client import ModbusTcpClient
        with ModbusTcpClient('127.0.0.1',port=port) as client:
            response=client.read_holding_registers(0,count=4,device_id=1)
            self.assertFalse(response.isError())
            self.assertEqual(response.registers,[653,123,1450,1])
        self.assertEqual(modbus_reader.read_points(port), {'temperature':65.3,'current':1.23,'speed':1450,'running_state':1})
        self.assertEqual(modbus_reader.read_temperature(port),(653,65.3))

    def test_real_legacy_one_register_cli_works_batch_collector_fails_whole_round(self):
        for registers in ([653], [653,123]):
            with socket.socket() as sock:
                sock.bind(('127.0.0.1',0))
                port=sock.getsockname()[1]
            code = "from pymodbus.datastore import ModbusDeviceContext,ModbusSequentialDataBlock,ModbusServerContext; from pymodbus.server import StartTcpServer; import sys; StartTcpServer(context=ModbusServerContext(devices={1:ModbusDeviceContext(hr=ModbusSequentialDataBlock(1,"+repr(registers)+"))},single=False),address=('127.0.0.1',int(sys.argv[1])))"
            proc=subprocess.Popen([sys.executable,'-c',code,str(port)],cwd=test_modbus.ROOT,stdout=subprocess.PIPE,stderr=subprocess.PIPE,text=True)
            self.addCleanup(self.stop_simulator,proc)
            deadline=time.monotonic()+5
            while True:
                try:
                    with socket.create_connection(('127.0.0.1',port),timeout=.1): break
                except OSError:
                    if time.monotonic()>deadline: self.fail('旧模拟器未就绪')
                    time.sleep(.05)
            cli=subprocess.run([sys.executable,'read_temperature.py','--port',str(port)],cwd=test_modbus.ROOT,capture_output=True,text=True,timeout=5)
            self.assertEqual(cli.returncode,0,cli.stderr)
            self.assertIn('65.3℃',cli.stdout)
            with tempfile.TemporaryDirectory() as directory:
                db=directory+'/legacy.sqlite3'
                result=subprocess.run([sys.executable,'collect_temperature.py','--port',str(port),'--db',db,'--count','1'],cwd=test_modbus.ROOT,capture_output=True,text=True,timeout=5)
                self.assertEqual(result.returncode,1)
                self.assertNotIn('已保存',result.stdout)
                with closing(sqlite3.connect(db)) as conn:
                    self.assertEqual(conn.execute('SELECT count(*) FROM measurements').fetchone()[0],0)
                    self.assertEqual(conn.execute('SELECT metric FROM collection_events ORDER BY id').fetchall(),[('temperature',),('current',),('speed',),('running_state',)])

    def test_short_or_exception_response_never_returns_partial_values(self):
        from pymodbus.exceptions import ModbusException
        for registers,error in [([653],False),([],False),([653,123,0],False),([653,123],True)]:
            with patch('modbus_reader.ModbusTcpClient') as factory:
                client=factory.return_value
                client.connect.return_value=True
                client.read_holding_registers.return_value=SimpleNamespace(registers=registers,isError=lambda:error)
                with self.assertRaises(ModbusException): modbus_reader.read_points()
                client.read_holding_registers.assert_called_once_with(0,count=4,device_id=1)
                client.close.assert_called_once()

class CurrentStorageTests(AlarmFixture):
    def round(self,t,temp=81,current=1.23):
        self.now=BASE+timedelta(seconds=t)
        storage.save_round(self.conn,{'temperature':temp,'current':current,'speed':1450,'running_state':1},self.now.isoformat(timespec='microseconds'),
                           alarm_session=self.session,monotonic_now=t)

    def test_same_round_timestamp_metric_isolation_and_old_temperature_default(self):
        self.enable()
        self.round(0,65.3)
        rows=self.conn.execute('SELECT metric,value,unit,collected_at FROM measurements ORDER BY id').fetchall()
        self.assertEqual([(r[0],r[1],r[2]) for r in rows],[('temperature',65.3,'℃'),('current',1.23,'A'),('speed',1450,'rpm'),('running_state',1,'')])
        self.assertEqual(rows[0][3],rows[1][3])
        temp=self.client.get('/api/devices/motor-a/latest').json()
        current=self.client.get('/api/devices/motor-a/latest?metric=current').json()
        self.assertEqual(temp['measurement']['value'],65.3)
        self.assertEqual(current['metric'],'current')
        self.assertEqual(current['measurement']['value'],1.23)
        self.assertIsNone(current['alarm'])
        params={'metric':'current','from':BASE.isoformat(),'to':self.now.isoformat()}
        self.assertEqual([p['value'] for p in self.client.get('/api/devices/motor-a/history',params=params).json()['points']],[1.23])
        self.now+=timedelta(seconds=6)
        storage.save_measurement(self.conn,66,self.now.isoformat(timespec='microseconds'))
        self.assertFalse(self.client.get('/api/devices/motor-a/latest').json()['status']['is_stale'])
        self.assertTrue(self.client.get('/api/devices/motor-a/latest?metric=current').json()['status']['is_stale'])

    def test_second_insert_rolls_back_temperature_alarm_and_pending(self):
        self.enable()
        for t in range(5): self.round(t)
        before=self.alarm()['pending']
        self.conn.execute("CREATE TRIGGER reject_current BEFORE INSERT ON measurements WHEN NEW.metric='current' BEGIN SELECT RAISE(ABORT,'second write'); END")
        with self.assertRaises(sqlite3.IntegrityError): self.round(5)
        self.assertEqual(self.conn.execute('SELECT count(*) FROM measurements').fetchone()[0],20)
        self.assertEqual(self.alarm()['total'],0)
        self.assertEqual(self.alarm()['pending'],before)
        self.conn.execute('DROP TRIGGER reject_current')
        self.round(5)
        self.assertEqual(self.alarm()['total'],1)

    def test_failure_both_metrics_reset_pending_and_recovery(self):
        self.enable()
        self.round(0)
        self.now+=timedelta(seconds=1)
        storage.save_round_failure(self.conn,self.now.isoformat(timespec='microseconds'),'offline',alarm_session=self.session)
        self.assertIsNone(self.alarm()['pending'])
        for metric in ('temperature','current'):
            latest=self.client.get('/api/devices/motor-a/latest',params={'metric':metric}).json()
            self.assertEqual(latest['status']['last_attempt_status'],'failure')
            self.assertEqual(latest['status']['last_failure_type'],'communication_error')
            self.assertEqual(latest['measurement']['collected_at'],BASE.isoformat(timespec='microseconds'))
        self.assertEqual(self.conn.execute('SELECT count(*) FROM measurements').fetchone()[0],4)
        self.round(2,65.3,2.34)
        self.assertEqual(self.client.get('/api/devices/motor-a/latest?metric=current').json()['measurement']['value'],2.34)

    def test_old_temperature_database_readonly_current_empty(self):
        storage.save_measurement(self.conn,65.3,BASE.isoformat(timespec='microseconds'))
        before=self.path.read_bytes()
        response=self.client.get('/api/devices/motor-a/latest?metric=current')
        self.assertEqual(response.status_code,200)
        self.assertIsNone(response.json()['measurement'])
        self.assertFalse(response.json()['status']['has_data'])
        self.assertIsNone(response.json()['status']['is_stale'])
        self.assertEqual(self.path.read_bytes(),before)

    def test_second_failure_event_rolls_back_first_and_pending_reset(self):
        self.enable()
        self.round(0)
        before=self.alarm()['pending']
        self.conn.execute("CREATE TRIGGER reject_event BEFORE INSERT ON collection_events WHEN NEW.metric='current' BEGIN SELECT RAISE(ABORT,'second failure event'); END")
        with self.assertRaises(sqlite3.IntegrityError):
            storage.save_round_failure(self.conn,(BASE+timedelta(seconds=1)).isoformat(timespec='microseconds'),'offline',alarm_session=self.session)
        self.assertEqual(self.conn.execute('SELECT count(*) FROM collection_events').fetchone()[0],0)
        self.assertEqual(self.alarm()['pending'],before)

    def test_pending_reset_failure_rolls_back_both_events(self):
        self.enable()
        self.round(0)
        before=self.alarm()['pending']
        self.conn.execute("CREATE TRIGGER reject_reset BEFORE UPDATE ON temperature_alarm_state BEGIN SELECT RAISE(ABORT,'reset failure'); END")
        with self.assertRaises(sqlite3.IntegrityError):
            storage.save_round_failure(self.conn,(BASE+timedelta(seconds=1)).isoformat(timespec='microseconds'),'offline',alarm_session=self.session)
        self.assertEqual(self.conn.execute('SELECT count(*) FROM collection_events').fetchone()[0],0)
        self.assertEqual(self.alarm()['pending'],before)
