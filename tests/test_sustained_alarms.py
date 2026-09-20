"""持续超限使用可控单调时间，SQLite/API保持真实。"""
from datetime import timedelta
import sqlite3
from test_alarms import AlarmFixture, BASE
from alarms import initialize_alarms
import storage

class SustainedAlarmTests(AlarmFixture):
    # 基础设施复用，旧测试在原类执行。
    def enable(self):
        self.session = initialize_alarms(self.conn)

    def at(self, mono, value=81, utc=None):
        self.now = utc or BASE + timedelta(seconds=mono)
        storage.save_measurement(self.conn, value, self.now.isoformat(timespec='microseconds'),
                                 evaluate_alarm=True, alarm_session=self.session, monotonic_now=mono)

    def test_duration_boundary_not_sample_count(self):
        self.enable()
        for t in (0, .1, .2, .3, .4, .5):
            self.at(t)
        self.assertEqual(self.alarm()['current'], 'pending')
        self.assertEqual(self.alarm()['pending']['elapsed_seconds'], .5)
        for t in (1, 2, 3, 4, 4.999):
            self.at(t)
        self.assertEqual(self.alarm()['total'], 0)
        self.at(5)
        event = self.alarm()['active']
        self.assertEqual(event['first_exceeded_at'], BASE.isoformat(timespec='microseconds'))
        self.assertEqual(event['started_at'], (BASE+timedelta(seconds=5)).isoformat(timespec='microseconds'))
        self.assertEqual(event['confirm_seconds'],5)
        self.assertEqual(event['observed_seconds'],5)
        self.assertEqual(event['max_gap_seconds'],1.5)
        self.assertNotEqual(event['first_exceeded_measurement_id'],event['trigger_measurement_id'])

    def test_reset_at_80_failure_and_gap_without_failure_event(self):
        self.enable()
        for t in range(4): self.at(t)
        self.at(4,80)
        self.assertIsNone(self.alarm()['pending'])
        self.at(5)
        self.assertEqual(self.alarm()['pending']['elapsed_seconds'],0)
        self.now += timedelta(seconds=.5)
        storage.save_failure(self.conn,self.now.isoformat(timespec='microseconds'),'offline')
        self.assertIsNone(self.alarm()['pending'])
        self.assertEqual(self.alarm()['current'],'unknown')
        self.at(6)
        self.at(7.5)  # 等于容忍边界仍连续
        self.assertEqual(self.alarm()['pending']['elapsed_seconds'],1.5)
        self.at(9.001)  # 无失败事件，gap本身重置
        self.assertEqual(self.alarm()['pending']['elapsed_seconds'],0)
        self.assertEqual(self.alarm()['total'],0)

    def test_restart_clears_pending_but_preserves_active(self):
        self.enable()
        for t in range(5): self.at(t)
        old_session=self.session
        self.enable()
        self.assertNotEqual(self.session,old_session)
        self.assertIsNone(self.alarm()['pending'])
        self.assertEqual(self.alarm()['current'],'unknown')
        self.at(5)
        self.assertEqual(self.alarm()['pending']['elapsed_seconds'],0)
        for t in range(6,11): self.at(t)
        active=self.alarm()['active']
        self.enable()
        self.assertEqual(self.alarm()['active'],active)
        self.at(11)
        self.assertEqual(self.alarm()['total'],1)
        self.at(12,78)
        self.assertIsNotNone(self.alarm()['active'])
        self.at(13,77.9)
        self.assertIsNone(self.alarm()['active'])
        for t in range(14,20): self.at(t)
        self.assertEqual(self.alarm()['total'],2)

    def test_monotonic_not_wall_clock_and_pending_api_expiry(self):
        self.enable()
        for t in range(5): self.at(t,utc=BASE+timedelta(days=t))
        self.assertEqual(self.alarm()['pending']['elapsed_seconds'],4)
        self.assertEqual(self.alarm()['total'],0)
        self.now += timedelta(seconds=1.500001)
        self.assertEqual(self.alarm()['current'],'unknown')
        self.at(5,utc=BASE-timedelta(days=1))
        self.assertEqual(self.conn.execute('SELECT count(*) FROM temperature_alarms').fetchone()[0],1)

    def test_pending_and_measurement_rollback_and_failure_reset_rollback(self):
        self.enable()
        for t in range(5): self.at(t)
        before=self.alarm()['pending']
        self.conn.execute("CREATE TRIGGER reject_trigger BEFORE INSERT ON temperature_alarms BEGIN SELECT RAISE(ABORT,'fail'); END")
        with self.assertRaises(sqlite3.IntegrityError): self.at(5)
        self.assertEqual(self.alarm()['pending'],before)
        self.assertEqual(self.conn.execute('SELECT count(*) FROM measurements').fetchone()[0],5)
        self.conn.execute('DROP TRIGGER reject_trigger')
        self.conn.execute("CREATE TRIGGER reject_reset BEFORE UPDATE ON temperature_alarm_state BEGIN SELECT RAISE(ABORT,'fail'); END")
        with self.assertRaises(sqlite3.IntegrityError): storage.save_failure(self.conn,self.now.isoformat(timespec='microseconds'),'offline')
        self.assertEqual(self.conn.execute('SELECT count(*) FROM collection_events').fetchone()[0],0)
        self.assertEqual(self.alarm()['pending'],before)
        self.conn.execute('DROP TRIGGER reject_reset')
        self.at(5)
        self.assertEqual(self.alarm()['current'],'active')

    def test_interval_incompatibility_rejected_before_schema_changes(self):
        for interval in (0,-1,float('nan'),float('inf'),4):
            with self.assertRaises(ValueError): initialize_alarms(self.conn,interval=interval)
        self.assertEqual(self.alarm()['current'],'not_enabled')


    def test_old_immediate_schema_readonly_then_writer_migration_preserves_evidence(self):
        # 构造上一版本真实列结构，禁止通过新版初始化伪装旧库。
        storage.save_measurement(self.conn,81,BASE.isoformat(timespec='microseconds'))
        self.conn.executescript('''
            CREATE TABLE temperature_alarm_state(device_id TEXT,metric TEXT,evaluated_id INTEGER,PRIMARY KEY(device_id,metric));
            INSERT INTO temperature_alarm_state VALUES ('motor-a','temperature',1);
            CREATE TABLE temperature_alarms(id INTEGER PRIMARY KEY,device_id TEXT,metric TEXT,started_at TEXT,
                trigger_measurement_id INTEGER,trigger_value REAL,trigger_above REAL,recover_below REAL,
                recovered_at TEXT,recovery_measurement_id INTEGER,recovery_value REAL);
        ''')
        with self.conn:
            self.conn.execute("INSERT INTO temperature_alarms VALUES (1,'motor-a','temperature',?,1,81,80,78,NULL,NULL,NULL)",
                              (BASE.isoformat(timespec='microseconds'),))
        before=self.path.read_bytes()
        old=self.alarm()
        self.assertEqual(old['current'],'active')
        self.assertEqual(old['rule']['confirm_seconds'],0)
        self.assertEqual(self.path.read_bytes(),before)
        self.enable()
        migrated=self.alarm()
        for key,value in old['active'].items(): self.assertEqual(migrated['active'][key],value)
        self.assertEqual(migrated['active']['confirm_seconds'],0)
        self.assertIsNone(migrated['active']['first_exceeded_at'])
        self.assertEqual(migrated['rule']['confirm_seconds'],5)
        self.assertEqual(migrated['current'],'unknown')
        self.at(1,77)
        self.assertEqual(self.alarm()['current'],'clear')
        self.at(2)
        self.assertEqual(self.alarm()['current'],'pending')
        self.assertEqual(self.alarm()['total'],1)

    def test_obsolete_session_cannot_commit_or_join_new_pending(self):
        self.enable()
        old_session=self.session
        self.at(0)
        self.enable()
        self.at(1)
        with self.assertRaises(sqlite3.OperationalError):
            storage.save_measurement(self.conn,81,BASE.isoformat(timespec='microseconds'),
                evaluate_alarm=True,alarm_session=old_session,monotonic_now=6)
        self.assertEqual(self.conn.execute('SELECT count(*) FROM measurements').fetchone()[0],2)
        self.assertEqual(self.alarm()['pending']['elapsed_seconds'],0)

    def test_obsolete_collector_failure_cannot_clear_new_session_pending(self):
        self.enable()
        old_session=self.session
        self.enable()
        self.at(0)
        self.at(1)
        before=self.alarm()['pending']
        with self.assertRaises(sqlite3.OperationalError):
            storage.save_failure(self.conn,self.now.isoformat(timespec='microseconds'),'old collector offline',alarm_session=old_session)
        self.assertEqual(self.alarm()['pending'],before)
        self.assertEqual(self.conn.execute('SELECT count(*) FROM collection_events').fetchone()[0],0)
