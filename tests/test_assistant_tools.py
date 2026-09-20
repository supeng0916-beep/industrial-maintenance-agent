import importlib
import importlib.util
import json
import sqlite3
import tempfile
import unittest
from pathlib import Path
from datetime import datetime, timezone, timedelta
from fastapi.testclient import TestClient
from storage import initialize, open_database, save_round
from alarms import initialize_alarms

NOW = datetime(2026, 9, 17, 12, tzinfo=timezone.utc)

class ToolTests(unittest.TestCase):
    def setUp(self):
        self.directory = tempfile.TemporaryDirectory(); self.addCleanup(self.directory.cleanup)
        self.path = Path(self.directory.name) / 'test.db'
        self.conn = open_database(self.path); self.addCleanup(self.conn.close)
        initialize(self.conn)

    def tools(self):
        self.assertIsNotNone(importlib.util.find_spec('assistant.tools'), '受限只读工具尚未实现')
        return importlib.import_module('assistant.tools').ReadOnlyTools(self.path, now=lambda: NOW)

    def test_status_all_points_reuses_http_facts(self):
        session = initialize_alarms(self.conn)
        save_round(self.conn, dict(temperature=65.3,current=1.23,speed=1450,running_state=1), NOW.isoformat(timespec='microseconds'), alarm_session=session)
        result = self.tools().invoke('get_device_status', {'device_id': 'motor-a'})
        self.assertTrue(result['ok'])
        data = result['data']; self.assertEqual(set(data['metrics']), {'temperature','current','speed','running_state'})
        from api import create_app
        with TestClient(create_app(self.path, now=lambda: NOW)) as client:
            for metric, reading in data['metrics'].items():
                http = client.get('/api/devices/motor-a/latest', params={'metric':metric}).json()
                self.assertEqual(reading['measurement'], http['measurement'])
                self.assertEqual(reading['status'], http['status'])
                self.assertEqual(reading['confidence']['state'], 'usable')
        json.dumps(result, allow_nan=False)

    def test_unknown_and_invalid_inputs_are_errors_not_empty(self):
        tools = self.tools()
        cases = [ ('get_device_status', {'device_id':'motor-z'}),
                  ('get_device_status', {'device_id':'motor-a','sql':'DELETE FROM measurements'}),
                  ('query_metric_history', {'device_id':'motor-b','metric':'speed','start':NOW.isoformat(),'end':NOW.isoformat()}),
                  ('query_metric_history', {'device_id':'motor-a','metric':'temperature','start':'2026-09-17T00:00:00','end':NOW.isoformat()}),
                  ('query_metric_history', {'device_id':'motor-a','metric':'temperature','start':(NOW-timedelta(hours=25)).isoformat(),'end':NOW.isoformat()}),
                  ('list_alarms', {'device_id':'motor-a','start':NOW.isoformat(),'end':NOW.isoformat(),'status':'open'}),
                  ('execute_sql', {'sql':'select 1'}) ]
        for name, args in cases:
            with self.subTest(name=name,args=args):
                result=tools.invoke(name,args)
                self.assertFalse(result['ok']); self.assertIn('code',result['error']); self.assertNotIn('data',result)

    def test_empty_and_legacy_reads_never_migrate(self):
        before=self.path.read_bytes()
        result=self.tools().invoke('get_device_status', {'device_id':'motor-a'})
        self.assertTrue(result['ok'])
        self.assertTrue(all(r['measurement'] is None for r in result['data']['metrics'].values()))
        self.assertEqual(result['data']['alarms']['current'],'not_enabled')
        self.assertEqual(self.path.read_bytes(),before)
        self.assertEqual(set(r[0] for r in self.conn.execute("select name from sqlite_master where type='table'")),{'measurements','collection_events'})

    def test_missing_database_is_not_created(self):
        self.tools()
        from assistant.tools import ReadOnlyTools
        path=Path(self.directory.name)/'absent.db'
        result=ReadOnlyTools(path).invoke('get_device_status',{'device_id':'motor-a'})
        self.assertFalse(result['ok']); self.assertEqual(result['error']['code'],'database_unavailable')
        self.assertFalse(path.exists())

    def test_real_cli_returns_json_and_exit_status(self):
        import subprocess, sys
        result=subprocess.run([sys.executable,'-m','assistant','--db',str(self.path),'get_device_status','--params','{"device_id":"motor-a"}'],capture_output=True,text=True)
        self.assertEqual(result.returncode,0,result.stderr)
        self.assertTrue(json.loads(result.stdout)['ok'])
        bad=subprocess.run([sys.executable,'-m','assistant','--db',str(self.path),'get_device_status','--params','{invalid'],capture_output=True,text=True)
        self.assertEqual(bad.returncode,1,bad.stderr)
        self.assertFalse(json.loads(bad.stdout)['ok'])

    def test_invalid_nonfinite_database_value_is_structured_error(self):
        self.conn.execute('INSERT INTO measurements(device_id,metric,value,unit,collected_at,quality,protocol) VALUES (?,?,?,?,?,?,?)', ('motor-a','temperature',float('inf'),'℃',NOW.isoformat(),'good','modbus_tcp'));self.conn.commit()
        result=self.tools().get_device_status('motor-a')
        self.assertFalse(result['ok'])
        self.assertEqual(result['error']['code'],'invalid_stored_data')
        json.dumps(result,allow_nan=False)

    def test_b_source_age_quality_runtime_do_not_infect_a(self):
        from asyncua import ua
        from opcua_storage import initialize_opcua, save_data_value
        from opcua_runtime import initialize_runtime, update_runtime
        a=initialize_alarms(self.conn)
        save_round(self.conn,dict(temperature=65.3,current=1.23,speed=1450,running_state=1),NOW.isoformat(timespec='microseconds'),alarm_session=a)
        initialize_opcua(self.conn);b=initialize_alarms(self.conn,device_id='motor-b')
        old=NOW-timedelta(seconds=6)
        save_data_value(self.conn,ua.DataValue(ua.Variant(85.,ua.VariantType.Double),SourceTimestamp=old),old,alarm_session=b)
        tools=self.tools()
        self.assertEqual(tools.get_device_status('motor-a')['data']['metrics']['temperature']['confidence']['state'],'usable')
        reading=tools.get_device_status('motor-b')['data']['metrics']['temperature']
        self.assertFalse(reading['opcua']['eligible']);self.assertEqual(reading['status']['data_age_seconds'],6)
        initialize_runtime(self.conn,b,'subscribe',NOW)
        update_runtime(self.conn,b,NOW,state='subscribed',generation=1)
        save_data_value(self.conn,ua.DataValue(ua.Variant(None,ua.VariantType.Null),StatusCode=ua.StatusCode(ua.StatusCodes.Bad),SourceTimestamp=NOW),NOW,alarm_session=b,generation=1)
        data=tools.get_device_status('motor-b')['data'];self.assertEqual(set(data['metrics']),{'temperature'})
        reading=data['metrics']['temperature']
        self.assertEqual(reading['measurement']['value'],85.)
        self.assertEqual(reading['opcua']['communication'],'success');self.assertEqual(reading['opcua']['quality'],'bad')
        self.assertEqual(reading['opcua']['runtime']['state'],'subscribed')
        self.assertEqual(reading['confidence']['state'],'unavailable')
        self.assertEqual(tools.get_device_status('motor-a')['data']['metrics']['temperature']['confidence']['state'],'usable')

    def test_tool_history_empty_json_and_timezone_boundary(self):
        tools=self.tools()
        args=dict(device_id='motor-a',metric='temperature',start='2026-09-17T20:00:00+08:00',end='2026-09-17T12:00:00Z')
        result=tools.query_metric_history(**args)
        self.assertTrue(result['ok']);self.assertEqual(result['data']['statistics']['count'],0)
        self.assertIsNone(result['data']['statistics']['max'])
        self.assertEqual(result['data']['start'],result['data']['end'])
        alarms=tools.list_alarms('motor-a',args['start'],args['end'])
        self.assertTrue(alarms['ok']);self.assertFalse(alarms['data']['history_available'])
        json.dumps(alarms,allow_nan=False)
        for limit in (0,1001,True,1.5,'10'):
            self.assertFalse(tools.query_metric_history(**args,limit=limit)['ok'])

    def test_latest_bad_stored_row_keeps_good_value_but_marks_unknown(self):
        for stamp,value,quality in [(NOW-timedelta(seconds=1),50,'good'),(NOW,99,'bad')]:
            self.conn.execute('INSERT INTO measurements(device_id,metric,value,unit,collected_at,quality,protocol) VALUES (?,?,?,?,?,?,?)',('motor-a','temperature',value,'℃',stamp.isoformat(timespec='microseconds'),quality,'modbus_tcp'))
        self.conn.commit()
        reading=self.tools().get_device_status('motor-a')['data']['metrics']['temperature']
        self.assertEqual(reading['measurement']['value'],50)
        self.assertEqual(reading['measurement']['quality'],'good')
        self.assertEqual(reading['status']['last_success_at'],(NOW-timedelta(seconds=1)).isoformat(timespec='microseconds'))
        self.assertEqual(reading['confidence']['state'],'unavailable')
        self.assertEqual(reading['latest_stored_record']['quality'],'bad')

    def test_invalid_stored_source_time_returns_json_error(self):
        from asyncua import ua
        from opcua_storage import initialize_opcua, save_data_value
        initialize_opcua(self.conn);session=initialize_alarms(self.conn,device_id='motor-b')
        save_data_value(self.conn,ua.DataValue(ua.Variant(85.,ua.VariantType.Double),SourceTimestamp=NOW),NOW,alarm_session=session)
        self.conn.execute("UPDATE opcua_diagnostics SET source_time='bad-date'");self.conn.commit()
        result=self.tools().get_device_status('motor-b')
        self.assertFalse(result['ok']);self.assertEqual(result['error']['code'],'invalid_stored_data')
