"""非有限数组仍是可诊断的拒绝样本，不能中止采集或保留pending。"""
import json
import sqlite3
import unittest
from datetime import datetime, timedelta, timezone
from asyncua import ua
from fastapi.testclient import TestClient
from api import create_app
from alarms import initialize_alarms
from opcua_storage import initialize_opcua, save_data_value

class InvalidArrayTests(unittest.TestCase):
    def test_nonfinite_arrays_are_diagnosed_and_reset_pending_but_preserve_active(self):
        for values, expected in [([float('nan')], ['nan']), ([float('inf')], ['inf']),
                                 ([[float('-inf'),float('nan')]], [['-inf','nan']])]:
            for active in (False,True):
                with self.subTest(values=expected, active=active), sqlite3.connect(':memory:') as conn:
                    initialize_opcua(conn)
                    session=initialize_alarms(conn,device_id='motor-b')
                    now=datetime.now(timezone.utc)
                    count=6 if active else 1
                    for i in range(count):
                        timestamp=now+timedelta(seconds=i)
                        save_data_value(conn,ua.DataValue(ua.Variant(85.,ua.VariantType.Double),SourceTimestamp=timestamp),timestamp,
                                        alarm_session=session,monotonic_now=i)
                    timestamp=now+timedelta(seconds=count)
                    rejected=save_data_value(conn,ua.DataValue(ua.Variant(values,ua.VariantType.Double),SourceTimestamp=timestamp),timestamp,
                                             alarm_session=session,monotonic_now=count)
                    self.assertFalse(rejected['accepted'])
                    self.assertEqual(rejected['reason'],'invalid_double')
                    self.assertEqual(json.loads(rejected['value_json']),expected)
                    self.assertEqual(conn.execute('select count(*) from measurements').fetchone()[0],count)
                    self.assertEqual(conn.execute('select count(*) from opcua_diagnostics').fetchone()[0],count+1)
                    self.assertEqual(conn.execute('select event_type,message from collection_events').fetchone(),('data_validation_error','invalid_double'))
                    self.assertIsNone(conn.execute('select pending_id from temperature_alarm_state').fetchone()[0])
                    self.assertEqual(conn.execute('select count(*) from temperature_alarms where recovered_at is null').fetchone()[0],int(active))

    def test_invalid_metric_error_describes_device_capabilities(self):
        client=TestClient(create_app())
        b=client.get('/api/devices/motor-b/latest?metric=current')
        self.assertEqual(b.status_code,422)
        message=b.json()['error']['message']
        self.assertIn('temperature',message)
        self.assertNotIn('current',message)
        a=client.get('/api/devices/motor-a/latest?metric=unknown')
        self.assertIn('current',a.json()['error']['message'])
