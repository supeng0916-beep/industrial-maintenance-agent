"""GET不能把保活/新订阅重建当作新的有效测量。"""
import tempfile
import unittest
from datetime import datetime, timedelta, timezone
from pathlib import Path
from asyncua import ua
from fastapi.testclient import TestClient
from alarms import initialize_alarms
from api import create_app
from storage import open_database
from opcua_storage import initialize_opcua, save_data_value
from opcua_runtime import initialize_runtime, update_runtime


class RuntimeApiTests(unittest.TestCase):
    def setUp(self):
        self.folder = tempfile.TemporaryDirectory(); self.addCleanup(self.folder.cleanup)
        self.path = Path(self.folder.name) / 'test.sqlite3'
        self.conn = open_database(self.path); self.addCleanup(self.conn.close)
        initialize_opcua(self.conn)
        self.session = initialize_alarms(self.conn, device_id='motor-b')
        self.now = datetime(2026, 9, 17, 0, 0, tzinfo=timezone.utc)
        for index in range(6):
            at = self.now + timedelta(seconds=index)
            save_data_value(self.conn, ua.DataValue(ua.Variant(85., ua.VariantType.Double), SourceTimestamp=at), at,
                            alarm_session=self.session, monotonic_now=index)
        self.now += timedelta(seconds=5)
        self.client = TestClient(create_app(self.path, now=lambda: self.now))

    def latest(self):
        response = self.client.get('/api/devices/motor-b/latest')
        self.assertEqual(response.status_code, 200)
        return response.json()

    def start(self):
        initialize_runtime(self.conn, self.session, 'subscribe', self.now)
        update_runtime(self.conn, self.session, self.now, state='subscribed', generation=1,
                       last_notification_at=self.now, last_publish_at=self.now)

    def test_lifecycle_does_not_restore_old_alarm_or_clear_active(self):
        self.start()
        self.assertTrue(self.latest()['opcua']['eligible'])
        active = self.latest()['alarm']['active']['id']
        for state in ('reconnecting', 'stopped', 'failed'):
            update_runtime(self.conn, self.session, self.now, state=state)
            result = self.latest()
            self.assertEqual(result['opcua']['runtime']['state'], state)
            self.assertFalse(result['opcua']['eligible'])
            self.assertEqual(result['alarm']['current'], 'unknown')
            self.assertEqual(result['alarm']['active']['id'], active)
            self.assertEqual(result['opcua']['quality'], 'good')

    def test_new_generation_needs_its_own_diagnostic(self):
        self.start()
        update_runtime(self.conn, self.session, self.now, state='subscribed', generation=2,
                       last_notification_at=None, last_publish_at=self.now)
        result = self.latest()
        self.assertFalse(result['opcua']['eligible'])
        self.assertEqual(result['alarm']['current'], 'unknown')
        self.assertEqual(result['measurement']['value'], 85.)

    def test_runtime_expiration_and_keepalive_do_not_refresh_source(self):
        self.start()
        self.now += timedelta(seconds=6)
        result = self.latest()
        self.assertEqual(result['opcua']['runtime']['state'], 'unknown')
        self.assertFalse(result['opcua']['eligible'])
        update_runtime(self.conn, self.session, self.now, state='subscribed', last_publish_at=self.now)
        result = self.latest()
        self.assertEqual(result['opcua']['runtime']['state'], 'subscribed')
        self.assertFalse(result['opcua']['eligible'])
        self.assertEqual(result['opcua']['source_freshness'], 'stale')
        self.assertEqual(result['alarm']['current'], 'unknown')

    def test_legacy_runtime_absent_is_readonly_and_keeps_read_semantics(self):
        before = self.path.read_bytes()
        result = self.latest()
        self.assertTrue(result['opcua']['eligible'])
        self.assertIsNone(result['opcua'].get('runtime'))
        self.assertEqual(self.path.read_bytes(), before)
        self.assertIsNone(self.conn.execute("select 1 from sqlite_master where name='opcua_runtime'").fetchone())
        self.assertNotIn('opcua', self.client.get('/api/devices/motor-a/latest').json())

    def test_missing_source_evidence_is_not_a_communication_failure(self):
        from opcua_runtime import interrupt_runtime
        self.start()
        self.now += timedelta(seconds=2)
        interrupt_runtime(self.conn, self.session, self.now, 'source_notification_gap',
                          generation=1, state='subscribed', event_type='evidence_interruption')
        result = self.latest()
        self.assertEqual(result['opcua']['runtime']['state'], 'subscribed')
        self.assertEqual(result['opcua']['communication'], 'success')
        self.assertEqual(result['opcua']['quality'], 'good')
        self.assertFalse(result['opcua']['eligible'])
        self.assertEqual(result['alarm']['current'], 'unknown')
        self.assertIsNotNone(result['alarm']['active'])

    def test_old_runtime_cannot_claim_ownership_after_new_alarm_session(self):
        self.start()
        initialize_alarms(self.conn, device_id='motor-b')
        result = self.latest()
        self.assertEqual(result['opcua']['runtime']['state'], 'unknown')
        self.assertFalse(result['opcua']['eligible'])
        self.assertEqual(result['alarm']['current'], 'unknown')

    def test_decision_age_rejection_exposes_both_times_and_preserves_active(self):
        self.start()
        received = self.now + timedelta(seconds=6)
        source = received - timedelta(seconds=4.9)
        self.now = received + timedelta(seconds=.2)
        save_data_value(self.conn, ua.DataValue(ua.Variant(77.9, ua.VariantType.Double), SourceTimestamp=source), received,
                        alarm_session=self.session, generation=1, monotonic_now=11,
                        notification_identity=(self.session, 1, 78, 99, 0, 0), decision_clock=lambda: self.now)
        result = self.latest()
        self.assertEqual(result['measurement']['value'], 85.)
        self.assertIsNotNone(result['alarm']['active'])
        self.assertFalse(result['opcua']['eligible'])
        self.assertEqual(result['opcua']['communication'], 'success')
        diagnostic = result['opcua']['diagnostic']
        self.assertEqual(diagnostic['reason'], 'stale_at_decision')
        self.assertEqual(diagnostic['received_at'], received.isoformat(timespec='microseconds'))
        self.assertEqual(diagnostic['decision_at'], self.now.isoformat(timespec='microseconds'))
