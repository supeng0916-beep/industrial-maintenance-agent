"""D5真实模型验收：本地Ollama对固定只读夹具完成状态/历史/文档/复合四类调用。

- 业务库为脚本自建的固定夹具（不触碰用户data）；文档工具用真实E5最终索引。
- 每个场景记录完整结果合同（status/calls/evidence/citations/耗时）；失败原样保留。
- 输出写入全新目录；替身测试不能替代本验收，本验收也不推广为一般可靠性。
"""
from __future__ import annotations

import argparse
import json
import sys
import time
from contextlib import closing
from datetime import datetime, timedelta, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from storage import DEVICE_ID, METRIC, initialize, open_database, save_measurement  # noqa: E402

SCENARIOS = [
    {'id': 'status', 'question': 'motor-a现在的温度是多少？数据新鲜吗？',
     'expect_tools': ['get_device_status']},
    {'id': 'history', 'question': 'motor-a在2026-09-19T10:00:00+00:00到'
                                  '2026-09-19T11:00:00+00:00的平均温度是多少？',
     'expect_tools': ['query_metric_history']},
    {'id': 'document', 'question': '按资料，20hp变频器输出为额定12.5%时的典型效率是多少？',
     'expect_tools': ['search_maintenance_docs']},
    {'id': 'composite', 'question': '先看motor-a现在的状态，再用资料说明三角皮带拉得过紧有哪些坏处。',
     'expect_tools': ['get_device_status', 'search_maintenance_docs']},
]

FIXTURE_BASE = datetime(2026, 9, 19, 10, 0, tzinfo=timezone.utc)


def build_fixture(path):
    """固定夹具：一小时每10分钟一个温度点（61.0~64.0）。

    时间格式必须与真实采集器一致（UTC ISO、微秒精度）：storage.history_between
    依赖统一格式的文本比较，含start在内的边界才正确。
    """
    with closing(open_database(path)) as conn:
        initialize(conn)
        for index in range(7):
            value = 61.0 + index * 0.5
            collected = (FIXTURE_BASE + timedelta(minutes=10 * index)).isoformat(
                timespec='microseconds')
            save_measurement(conn, value, collected)
    return [{'collected_at': (FIXTURE_BASE + timedelta(minutes=10 * i)).isoformat(
        timespec='microseconds'), 'value': 61.0 + i * 0.5} for i in range(7)]


def run_scenario(service, scenario):
    started = time.monotonic()
    result = service.answer(scenario['question'], [])
    elapsed = time.monotonic() - started
    called = [c['name'] for c in result.get('calls', []) if c['outcome'] == 'ok']
    verdict = {
        'tools_called_ok': called,
        'expected_tools_hit': all(any(name == expected for name in called)
                                  for expected in scenario['expect_tools']),
        'no_unexpected_tools': all(name in {s for s in (
            'get_device_status', 'query_metric_history', 'list_alarms',
            'search_maintenance_docs')} for name in called),
    }
    return {'scenario': scenario['id'], 'question': scenario['question'],
            'elapsed_seconds': round(elapsed, 2), 'result': result,
            'verdict': verdict}


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--model', default='deepseek-chat')
    parser.add_argument('--index', default=str(ROOT / 'docs/verification/m4-real-rag/doe-e5-final'))
    parser.add_argument('--output', required=True,
                        help='new directory for results.json; must not already exist')
    args = parser.parse_args(argv)
    output = Path(args.output).absolute()
    if output.exists() or output.is_symlink():
        print(json.dumps({'ok': False, 'error': {
            'code': 'FileExistsError', 'message': f'output exists: {output}'}}, ensure_ascii=False))
        return 1
    import os
    from assistant.model_provider import build_assistant_service
    from assistant.settings import load_env_file
    load_env_file(ROOT / '.env')
    env = dict(os.environ)
    env['ASSISTANT_MODEL'] = args.model
    provider = ('cloud (OpenAI-compatible)' if env.get('ASSISTANT_API_KEY')
                else 'local ollama')
    output.mkdir(parents=True)
    fixture_values = build_fixture(output / 'fixture.sqlite3')

    service = build_assistant_service(
        environ=env, index_path=args.index,
        db_path=str(output / 'fixture.sqlite3'))
    records = [{'scenario': 'warmup', 'note': '预热：模型加载不记入任何场景成绩',
                'answer': service.answer('只回复两个字：在线', [])['answer']}]
    for scenario in SCENARIOS:
        records.append(run_scenario(service, scenario))
    payload = {
        'ok': True, 'acceptance': 'agent-real-four-calls',
        'executed_at': datetime.now(timezone.utc).isoformat(),
        'model': args.model, 'provider': provider,
        'index_path': args.index,
        'fixture': {'db': 'fixture.sqlite3（本目录内自建）', 'metric': METRIC,
                    'device': DEVICE_ID, 'points': fixture_values,
                    'fixture_clock_note': '数据新鲜度按真实系统时钟判定，末点为2026-09-19T11:00Z'},
        'records': records,
        'limitations': [
            '真实模型输出有随机性：单次运行不构成一般可靠性结论。',
            '本验收证明流程控制与真实工具调用，语义正确性在D9按场景集人工核查。',
        ],
    }
    (output / 'results.json').write_text(
        json.dumps(payload, ensure_ascii=False, sort_keys=True, indent=1) + '\n', encoding='utf-8')
    summary = [{'scenario': r['scenario'],
                'status': r.get('result', {}).get('status'),
                'verdict': r.get('verdict')} for r in records if r['scenario'] != 'warmup']
    print(json.dumps({'ok': True, 'output': str(output / 'results.json'),
                      'summary': summary}, ensure_ascii=False, indent=1))
    return 0


if __name__ == '__main__':
    sys.exit(main())
