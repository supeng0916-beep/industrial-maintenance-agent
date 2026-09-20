"""共享只读查询服务：每次调用独立连接、一个短快照、一个执行预算。"""
from contextlib import contextmanager
from datetime import datetime, timezone
from pathlib import Path
import math
import sqlite3
import time
from points import POINTS
from .contracts import DEVICES, QueryError, check_device, check_limit, time_range, utc_text
from .observations import latest_metric

class QueryService:
    def __init__(self, db_path, *, stale_after_seconds=5, timeout_seconds=5, now=None):
        if not math.isfinite(timeout_seconds) or not 0 < timeout_seconds <= 5:
            raise ValueError('查询执行预算必须大于0且不超过5秒')
        if not math.isfinite(stale_after_seconds) or stale_after_seconds <= 0:
            raise ValueError('数据过期阈值必须为正有限数')
        self.path, self.stale, self.timeout = Path(db_path), stale_after_seconds, timeout_seconds
        self.clock = now or (lambda: datetime.now(timezone.utc))

    @contextmanager
    def snapshot(self):
        deadline = time.monotonic() + self.timeout
        conn = None
        try:
            conn = sqlite3.connect(self.path.resolve().as_uri()+'?mode=ro', uri=True, timeout=min(.1,self.timeout))
            conn.row_factory = sqlite3.Row
            conn.set_progress_handler(lambda: int(time.monotonic() >= deadline), 1000)
            conn.execute('BEGIN')
            yield conn
            if time.monotonic() >= deadline:
                raise QueryError('query_timeout','只读查询超过执行时间预算',503)
        except QueryError as exc:
            if exc.code == 'invalid_time':
                raise QueryError('invalid_stored_data','数据库记录的时间字段无效',503) from None
            raise
        except (ValueError, TypeError, OverflowError):
            raise QueryError('invalid_stored_data','数据库记录的时间或结构无效',503) from None
        except sqlite3.Error as exc:
            if time.monotonic() >= deadline or getattr(exc, 'sqlite_errorcode', None) == sqlite3.SQLITE_INTERRUPT:
                raise QueryError('query_timeout','只读查询超过执行时间预算',503) from None
            raise QueryError('database_unavailable','数据库不可读或繁忙，请检查采集器及服务日志',503) from None
        finally:
            if conn is not None:
                conn.close()

    def latest(self, device_id, metric='temperature'):
        check_device(device_id,metric)
        with self.snapshot() as conn:
            return latest_metric(conn,device_id,metric,self.clock(),self.stale)

    def get_device_status(self, device_id):
        device = check_device(device_id)
        with self.snapshot() as conn:
            checked = self.clock()
            metrics = {}
            for metric in device['metrics']:
                reading = latest_metric(conn,device_id,metric,checked,self.stale)
                sample, status = reading['measurement'], reading['status']
                if sample is None: state, reason = 'no_data', '尚无有效测量记录'
                elif status['last_attempt_status'] != 'success' or sample['quality'] != 'good' or status['data_age_seconds'] is None or status['data_age_seconds'] < 0:
                    state, reason = 'unavailable', '当前证据未能核实；保留最后记录'
                elif status['is_stale']: state, reason = 'stale', '最后有效记录已过期'
                else: state, reason = 'usable', '记录在时效范围内；不代表设备健康'
                reading.update(unit=POINTS[metric].unit, confidence={'state':state,'reason':reason})
                metrics[metric] = reading
            return {'device':dict(device),'checked_at':utc_text(checked),'metrics':metrics,
                    'alarms':metrics['temperature']['alarm'],
                    'limitations':['数值为最后记录，不是连续实时物理状态；可用不等于健康。']}

    def query_metric_history(self, device_id, metric, start, end, limit=1000):
        check_device(device_id,metric)
        if metric is None: raise QueryError('invalid_metric','metric不能为空')
        first,last = time_range(start,end); check_limit(limit)
        from .ranges import metric_history
        with self.snapshot() as conn:
            result = metric_history(conn,device_id,metric,first,last,limit)
            result['checked_at'] = utc_text(self.clock())
            return result

    def list_alarms(self, device_id, start, end, status='all', limit=1000):
        check_device(device_id); first,last=time_range(start,end); check_limit(limit)
        if not isinstance(status,str) or status not in ('active','recovered','all'):
            raise QueryError('invalid_parameters','status必须为active、recovered或all')
        from .ranges import alarm_history
        with self.snapshot() as conn:
            result=alarm_history(conn,device_id,first,last,status,limit)
            result['checked_at']=utc_text(self.clock())
            return result
