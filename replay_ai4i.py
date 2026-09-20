"""AI4I 2020 预测性维护数据集回放器：把历史CSV行按时间节奏写入现有SQLite管道。

诚实性合同（见 docs/superpowers/plans/2026-09-20-ai4i-replay.md）：
- 数据集为合成数据（UCI AI4I 2020，CC BY 4.0），任何展示必须带"历史回放"标注。
- collected_at 是回放时刻墙钟，不伪造原始采集时间；行序保持数据集原序。
- 故障标签直接取自数据集自身列（Machine failure/TWF/HDF/PWF/OSF/RNF），本系统不再判定。
- CSV 指纹固定，校验不过即拒绝回放。
"""

import argparse
import csv
import hashlib
import math
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

from storage import initialize, open_database

DEVICE_ID = 'motor-c'
PROTOCOL = 'replay'
DATASET_SHA256 = 'dc6630cd9b1f0f853922fad78a1b6436570d3f1ec863f1dd5c4340ac56bc8a8e'
DATASET_ROWS = 10000
DATASET_INFO = {
    'name': 'AI4I 2020 Predictive Maintenance Dataset',
    'author': 'Stephan Matzka (HTW Berlin), UCI Machine Learning Repository',
    'source': 'https://archive.ics.uci.edu/dataset/601/ai4i+2020+predictive+maintenance+dataset',
    'license': 'CC BY 4.0',
    'synthetic': True,
    'sha256': DATASET_SHA256,
    'rows_total': DATASET_ROWS,
}
DEFAULT_CSV = Path(__file__).resolve().parent / 'docs' / 'datasets' / 'ai4i-2020' / 'ai4i2020.csv'

# (CSV列名, 指标, 单位, 转换)。温度K→℃为精确换算；其余取原值。
# running_state 与 Machine failure 取反：1=正常运转，0=数据集标注故障（见计划文档映射表）。
COLUMN_MAP = (
    ('Air temperature [K]', 'air_temperature', '℃', lambda v: round(v - 273.15, 1)),
    ('Process temperature [K]', 'temperature', '℃', lambda v: round(v - 273.15, 1)),
    ('Rotational speed [rpm]', 'speed', 'rpm', lambda v: v),
    ('Torque [Nm]', 'torque', 'Nm', lambda v: v),
    ('Tool wear [min]', 'tool_wear', 'min', lambda v: v),
    ('Machine failure', 'running_state', '', lambda v: 1.0 - v),
)
FAULT_FLAGS = {'TWF': '刀具磨损故障（TWF）', 'HDF': '散热不良（HDF）',
               'PWF': '功率超限（PWF）', 'OSF': '过应变（OSF）', 'RNF': '随机故障（RNF）'}
FAULT_EVENT_TYPE = 'replay_dataset_fault'


def dataset_fingerprint(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def verify_dataset(path, expected=DATASET_SHA256):
    """指纹门禁：文件缺失或被改动即拒绝回放，防止来源不明或悄悄篡改的数据进入管道。"""
    if not Path(path).is_file():
        raise ValueError(f'数据集文件不存在：{path}；见 docs/datasets/ai4i-2020/README.md')
    actual = dataset_fingerprint(path)
    if actual != expected:
        raise ValueError(f'数据集指纹不匹配（实际 {actual}，登记 {expected}），拒绝回放；'
                         '请重新下载原文件并更新登记')
    return actual


def load_rows(path, from_row=0, rows=None):
    """解析并校验回放窗口；结构异常即整体拒绝（fail-closed），不回放半批数据。"""
    if type(from_row) is not int or from_row < 0:
        raise ValueError('from_row 必须是非负整数')
    if rows is not None and (type(rows) is not int or rows < 1):
        raise ValueError('rows 必须是正整数或留空')
    with open(path, encoding='utf-8-sig', newline='') as handle:
        reader = csv.DictReader(handle)
        header = reader.fieldnames or []
        required = [column for column, *_ in COLUMN_MAP] + list(FAULT_FLAGS)
        missing = [column for column in required if column not in header]
        if missing:
            raise ValueError('数据集缺少列：' + '、'.join(missing))
        selected = []
        for index, row in enumerate(reader):
            if index < from_row:
                continue
            if rows is not None and len(selected) >= rows:
                break
            parsed = {}
            for column, metric, _unit, convert in COLUMN_MAP:
                try:
                    raw = float(row[column])
                except (TypeError, ValueError):
                    raise ValueError(f'第{index + 1}行列“{column}”不是数值') from None
                if not math.isfinite(raw):
                    raise ValueError(f'第{index + 1}行列“{column}”不是有限数值')
                if metric == 'running_state' and raw not in (0.0, 1.0):
                    raise ValueError(f'第{index + 1}行 Machine failure 必须为0或1')
                parsed[metric] = convert(raw)
            labels = []
            for flag, name in FAULT_FLAGS.items():
                text = (row[flag] or '').strip()
                if text not in ('0', '1'):
                    raise ValueError(f'第{index + 1}行 {flag} 标签必须为0或1')
                if text == '1':
                    labels.append(name)
            parsed['faults'] = labels
            selected.append(parsed)
    if not selected:
        raise ValueError('选中的回放窗口没有数据行')
    return selected


def replay_round(conn, row, collected_at):
    """一轮写入：6条测量 +（数据集有标注时）1条故障事件。时间由调用方注入。"""
    with conn:
        for _column, metric, unit, _convert in COLUMN_MAP:
            conn.execute("""INSERT INTO measurements
                (device_id, metric, value, unit, collected_at, source_time, quality, protocol)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
                (DEVICE_ID, metric, row[metric], unit, collected_at, None, 'good', PROTOCOL))
        if row['faults']:
            conn.execute("""INSERT INTO collection_events
                (device_id, metric, occurred_at, event_type, message, protocol)
                VALUES (?, ?, ?, ?, ?, ?)""",
                (DEVICE_ID, 'temperature', collected_at, FAULT_EVENT_TYPE,
                 '数据集标注故障：' + '、'.join(row['faults']), PROTOCOL))


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--db', default='data/dashboard-demo.sqlite3', help='默认与看板共用演示库；相对路径以项目根为基准')
    parser.add_argument('--csv', default=str(DEFAULT_CSV))
    parser.add_argument('--interval', type=float, default=1.0, help='每行回放间隔秒，默认1.0')
    parser.add_argument('--from-row', type=int, default=0, help='从数据集第几行开始（0基，默认0）')
    parser.add_argument('--rows', type=int, default=None, help='最多回放多少行（默认到文件末尾）')
    parser.add_argument('--once', action='store_true', help='只回放一行即退出（冒烟测试用）')
    args = parser.parse_args()
    if not math.isfinite(args.interval) or not 0.05 <= args.interval <= 60:
        parser.error('--interval 必须在0.05～60秒之间')
    if args.from_row < 0:
        parser.error('--from-row 必须是非负整数')
    if args.rows is not None and args.rows < 1:
        parser.error('--rows 必须是正整数')
    try:
        verify_dataset(args.csv)
        rows = load_rows(args.csv, args.from_row, args.rows)
    except ValueError as exc:
        parser.exit(2, f'回放未开始：{exc}\n')
    db = Path(args.db)
    if not db.is_absolute():
        db = Path(__file__).resolve().parent / db
    conn = open_database(db)
    initialize(conn)
    window = f'第{args.from_row + 1}～{args.from_row + len(rows)}行（共{DATASET_ROWS}行）'
    print(f'历史回放设备 {DEVICE_ID}：AI4I 2020 合成数据集（CC BY 4.0），窗口{window}，'
          f'间隔{args.interval:g}秒/行。\n时间为回放时刻，非原始采集时间；故障标注来自数据集自身。Ctrl+C 停止，已写历史保留。',
          flush=True)
    try:
        for index, row in enumerate(rows):
            replay_round(conn, row, datetime.now(timezone.utc).isoformat(timespec='microseconds'))
            print(f'已回放 {index + 1}/{len(rows)} 行'
                  + ('；' + '、'.join(row['faults']) if row['faults'] else ''), flush=True)
            if args.once or index == len(rows) - 1:
                break
            time.sleep(args.interval)
    except KeyboardInterrupt:
        print('\n回放已停止；已写入的历史保留。', flush=True)
    finally:
        conn.close()
    return 0


if __name__ == '__main__':
    sys.exit(main())
