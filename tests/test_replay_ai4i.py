"""AI4I 2020 回放器与只读管道集成验证；CSV用例为受控夹具，不依赖网络。"""
from datetime import datetime, timezone
import tempfile
import unittest
from contextlib import closing
from pathlib import Path

from fastapi.testclient import TestClient

from api import create_app
from assistant.contracts import DEVICES, check_device, QueryError
from assistant.observations import latest_metric
from assistant.query_service import QueryService
from points import unit_of
from replay_ai4i import (
    DATASET_SHA256, DEFAULT_CSV, DEVICE_ID, FAULT_EVENT_TYPE, load_rows,
    replay_round, verify_dataset,
)
import storage

BASE = datetime(2026, 9, 20, 8, tzinfo=timezone.utc)
HEADER = ('UDI,Product ID,Type,Air temperature [K],Process temperature [K],'
          'Rotational speed [rpm],Torque [Nm],Tool wear [min],Machine failure,'
          'TWF,HDF,PWF,OSF,RNF')
METRIC_COLUMNS = ('Air temperature [K]', 'Process temperature [K]', 'Rotational speed [rpm]',
                  'Torque [Nm]', 'Tool wear [min]', 'Machine failure')


def csv_line(udi, air, process, speed, torque, wear, failure,
             twf=0, hdf=0, pwf=0, osf=0, rnf=0):
    return (f'{udi},M1,M,{air},{process},{speed},{torque},{wear},{failure},'
            f'{twf},{hdf},{pwf},{osf},{rnf}')


def write_csv(path, lines, header=HEADER, bom=True):
    text = header + '\n' + '\n'.join(lines) + '\n'
    Path(path).write_text(('\ufeff' if bom else '') + text, encoding='utf-8')
    return path


class LoadRowsTests(unittest.TestCase):
    def fixture(self, lines, header=HEADER, **window):
        with tempfile.TemporaryDirectory() as temp:
            path = write_csv(Path(temp) / 'a.csv', lines, header=header)
            return load_rows(path, **window)

    def test_exact_mapping_and_fault_labels(self):
        rows = self.fixture([
            csv_line(1, 298.15, 308.15, 1551, 42.8, 5, 0),
            csv_line(2, 300.0, 310.0, 1408, 46.3, 9, 1, hdf=1, osf=1),
        ])
        self.assertEqual(rows[0], {'air_temperature': 25.0, 'temperature': 35.0,
                                   'speed': 1551.0, 'torque': 42.8, 'tool_wear': 5.0,
                                   'running_state': 1.0, 'faults': []})
        self.assertEqual(rows[1]['running_state'], 0.0)
        self.assertEqual(rows[1]['faults'], ['散热不良（HDF）', '过应变（OSF）'])

    def test_window_selection_and_empty_window_rejected(self):
        rows = self.fixture([csv_line(1, 298.15, 308.15, 1, 1, 1, 0)] * 3, from_row=1, rows=2)
        self.assertEqual(len(rows), 2)
        with self.assertRaisesRegex(ValueError, '没有数据行'):
            self.fixture([csv_line(1, 298.15, 308.15, 1, 1, 1, 0)], from_row=9)

    def test_structural_failures_are_rejected_closed(self):
        bad_header = HEADER.replace('Torque [Nm]', 'Torque')
        with self.assertRaisesRegex(ValueError, '缺少列'):
            self.fixture([csv_line(1, 298.15, 308.15, 1, 1, 1, 0)], header=bad_header)
        for broken in (csv_line(1, 298.15, 'NaN', 1, 1, 1, 0),
                       csv_line(2, 298.15, 308.15, 'fast', 1, 1, 0),
                       csv_line(3, 298.15, 308.15, 1, 1, 1, 2),
                       csv_line(4, 298.15, 308.15, 1, 1, 1, 0, hdf=2)):
            with self.subTest(line=broken), self.assertRaises(ValueError):
                self.fixture([broken])
        with self.assertRaises(ValueError):
            self.fixture([csv_line(1, 298.15, 308.15, 1, 1, 1, 0)], rows=0)
        with self.assertRaises(ValueError):
            self.fixture([csv_line(1, 298.15, 308.15, 1, 1, 1, 0)], from_row=-1)


class FingerprintTests(unittest.TestCase):
    def test_repo_dataset_matches_registered_sha(self):
        # 仓库登记副本被改动即在此暴露；不联网。
        self.assertTrue(DEFAULT_CSV.is_file(), '数据集副本缺失，见 docs/datasets/ai4i-2020/README.md')
        self.assertEqual(verify_dataset(DEFAULT_CSV), DATASET_SHA256)

    def test_tampered_or_missing_file_refuses_replay(self):
        with tempfile.TemporaryDirectory() as temp:
            path = write_csv(Path(temp) / 'a.csv', [csv_line(1, 298.15, 308.15, 1, 1, 1, 0)])
            with self.assertRaisesRegex(ValueError, '指纹不匹配'):
                verify_dataset(path)
            with self.assertRaisesRegex(ValueError, '不存在'):
                verify_dataset(Path(temp) / 'missing.csv')


class ReplayRoundTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.path = Path(self.temp.name) / 'replay.sqlite3'
        self.conn = storage.open_database(self.path)
        self.addCleanup(self.conn.close)
        self.conn.row_factory = storage.sqlite3.Row
        storage.initialize(self.conn)
        self.stamp = BASE.isoformat(timespec='microseconds')

    def rows(self, table, order='id ASC'):
        return self.conn.execute(f'SELECT * FROM {table} ORDER BY {order}').fetchall()

    def test_round_writes_six_measurements_with_replay_honesty_fields(self):
        replay_round(self.conn, load_rows_fixture()[0], self.stamp)
        rows = self.rows('measurements')
        self.assertEqual([r['metric'] for r in rows],
                         ['air_temperature', 'temperature', 'speed', 'torque', 'tool_wear', 'running_state'])
        self.assertEqual([r['unit'] for r in rows], ['℃', '℃', 'rpm', 'Nm', 'min', ''])
        self.assertTrue(all(r['device_id'] == DEVICE_ID and r['protocol'] == 'replay'
                            and r['quality'] == 'good' and r['collected_at'] == self.stamp
                            and r['source_time'] is None for r in rows))
        self.assertEqual(self.rows('collection_events'), [])

    def test_fault_row_writes_one_dataset_event_and_no_alarm_state(self):
        replay_round(self.conn, load_rows_fixture(failure=True)[0], self.stamp)
        events = self.rows('collection_events')
        self.assertEqual(len(events), 1)
        self.assertEqual((events[0]['event_type'], events[0]['protocol']), (FAULT_EVENT_TYPE, 'replay'))
        self.assertEqual(events[0]['message'], '数据集标注故障：散热不良（HDF）')
        tables = {r[0] for r in self.conn.execute("SELECT name FROM sqlite_master WHERE type='table'")}
        self.assertNotIn('temperature_alarm_state', tables, '回放器不得启用持续告警状态')


def load_rows_fixture(failure=False):
    with tempfile.TemporaryDirectory() as temp:
        path = write_csv(Path(temp) / 'a.csv', [
            csv_line(1, 298.15, 308.15, 1551, 42.8, 5, 1 if failure else 0, hdf=1 if failure else 0)])
        return load_rows(path)


class PipelineIntegrationTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.path = Path(self.temp.name) / 'replay.sqlite3'
        self.conn = storage.open_database(self.path)
        self.addCleanup(self.conn.close)
        self.conn.row_factory = storage.sqlite3.Row
        storage.initialize(self.conn)
        self.now = BASE
        self.service = QueryService(self.path, now=lambda: self.now)
        stamps = [(BASE.replace(second=second)).isoformat(timespec='microseconds') for second in (0, 1, 2)]
        for row, stamp in zip(load_rows_mixed(), stamps):
            replay_round(self.conn, row, stamp)
        self.now = BASE.replace(second=3)  # 最后写入后1秒内检查，数据未过期

    def test_whitelist_and_units(self):
        self.assertIn('motor-c', DEVICES)
        self.assertEqual(DEVICES['motor-c']['protocol'], 'replay')
        self.assertEqual(check_device('motor-c', 'torque')['id'], 'motor-c')
        with self.assertRaises(QueryError):
            check_device('motor-c', 'current')
        self.assertEqual(unit_of('tool_wear'), 'min')
        with self.assertRaises(KeyError):
            unit_of('unknown')

    def test_get_device_status_reports_replay_metrics(self):
        status = self.service.get_device_status('motor-c')
        self.assertEqual(status['device']['protocol'], 'replay')
        self.assertEqual(sorted(status['metrics']), sorted(DEVICES['motor-c']['metrics']))
        self.assertEqual(status['metrics']['torque']['unit'], 'Nm')
        # 期望值用与回放器相同的换算计算，避免十进制舍入断言歧义。
        self.assertEqual(status['metrics']['temperature']['measurement']['value'], round(307.5 - 273.15, 1))
        self.assertEqual(status['metrics']['temperature']['confidence']['state'], 'usable')
        self.assertFalse(status['alarms']['enabled'])

    def test_latest_metric_attaches_replay_payload_with_faults(self):
        reading = self.service.latest('motor-c')
        replay = reading['replay']
        self.assertEqual(replay['mode'], 'historical_replay')
        self.assertTrue(replay['dataset']['synthetic'])
        self.assertEqual(replay['dataset']['license'], 'CC BY 4.0')
        self.assertIn('回放时刻', replay['note'])
        self.assertEqual(replay['faults_total'], 1)
        self.assertEqual(replay['faults'][0]['message'], '数据集标注故障：功率超限（PWF）')
        self.assertIsNone(reading.get('opcua'))

    def test_history_endpoint_serves_replay_metrics(self):
        client = closing(TestClient(create_app(self.path, now=lambda: self.now)))
        with client as app:
            devices = app.get('/api/devices').json()['devices']
            entry = next(item for item in devices if item['id'] == 'motor-c')
            self.assertIn('torque', entry['metrics'])
            latest = app.get('/api/devices/motor-c/latest?metric=tool_wear')
            self.assertEqual(latest.json()['measurement']['unit'], 'min')
            bad = app.get('/api/devices/motor-c/latest?metric=current')
            self.assertEqual(bad.status_code, 422)
            self.assertIn('invalid_metric', bad.text)

    def test_motor_a_behavior_unchanged(self):
        # motor-a 未写入任何数据时查询仍按原契约返回，不因白名单扩展改变。
        reading = self.service.latest('motor-a')
        self.assertIsNone(reading['measurement'])
        self.assertFalse(reading['status']['has_data'])
        self.assertIsNone(reading.get('replay'))


def load_rows_mixed():
    with tempfile.TemporaryDirectory() as temp:
        path = write_csv(Path(temp) / 'a.csv', [
            csv_line(1, 298.15, 308.15, 1551, 42.8, 5, 0),
            csv_line(2, 299.0, 309.0, 1408, 46.3, 9, 1, pwf=1),
            csv_line(3, 297.5, 307.5, 1629, 51.2, 13, 0),
        ])
        return load_rows(path)


class ServeApiWiringTests(unittest.TestCase):
    def test_assistant_service_shares_the_serve_api_database(self):
        # 回归：助手工具曾回退到默认库 data/measurements.sqlite3（不存在），
        # 看板后端 --db 与助手工具必须同库，否则所有工具查询报 database_unavailable。
        from unittest.mock import patch
        import serve_api
        with tempfile.TemporaryDirectory() as temp, \
                patch('serve_api.build_assistant_service', return_value=None) as builder, \
                patch('serve_api.uvicorn.run'), \
                patch('sys.argv', ['serve_api.py', '--db', str(Path(temp) / 'x.sqlite3'), '--port', '9999']):
            self.assertEqual(serve_api.main(), None)
        self.assertEqual(builder.call_args.kwargs.get('db_path'), str(Path(temp) / 'x.sqlite3'))


if __name__ == '__main__':
    unittest.main()
