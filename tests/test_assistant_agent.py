"""D5 编排（模型替身级）：结果合同、预算/超时、工具白名单、证据保真。

替身只证明流程控制，不证明真实模型选工具能力；真实模型四类调用验收留待D4解锁。
"""
import json
from pathlib import Path
import tempfile
import time
import unittest
from datetime import datetime

from assistant.agent import AssistantService, AssistantToolRegistry
from assistant.agent_contracts import ContractError, normalise_history
from assistant.document_tool import MaintenanceDocumentTool
from assistant.rag_index import create_index
from tests.test_rag_index import TinyEmbedder, chunk


class StubModel:
    """可控模型替身：按脚本依次返回回合；记录收到的消息与工具规格。"""

    def __init__(self, turns, fail=None):
        self.turns = list(turns)
        self.received = []
        self._fail = fail

    def plan(self, messages, tool_specs):
        self.received.append({'messages': messages, 'tool_specs': tool_specs})
        if self._fail:
            raise self._fail
        if not self.turns:
            return {'text': '脚本已耗尽'}
        return self.turns.pop(0)


def tool_call(name, arguments, call_id='t1'):
    return {'tool_calls': [{'id': call_id, 'name': name, 'arguments': arguments}]}


def text_reply(body):
    return {'text': body}


class FakeBusinessTools:
    """与ReadOnlyTools同构的invoke(name, arguments)替身；sleeps按次消费。"""

    def __init__(self, results=None, sleep_seconds=0.0, sleeps=None):
        self.results = results or {}
        self.sleep_seconds = sleep_seconds
        self.sleeps = list(sleeps) if sleeps is not None else None
        self.executed = []

    def invoke(self, name, arguments):
        self.executed.append((name, arguments))
        if self.sleeps is not None:
            delay = self.sleeps.pop(0) if self.sleeps else 0.0
        else:
            delay = self.sleep_seconds
        if delay:
            time.sleep(delay)
        if name in self.results:
            return self.results[name]
        return {'ok': True, 'data': {'echo': arguments}}


def doc_ok_result():
    return {'ok': True, 'data': {'query': 'q', 'limitations': ['候选不证明适用性或可回答性'],
            'candidates': [{
                'evidence_id': 'doc-1', 'document_id': 'doe-motor-ts11', 'chunk_id': 'cz',
                'version': 'November 2012', 'source_pages': ['2'],
                'source_url': 'https://example.invalid/x.pdf',
                'original_text': 'table line 20 47 86 93 94 95 96 97 条件文本',
                'context_text': 'ctx', 'applicability': 'General guidance',
                'product_model': None}]}}


class FakeDocumentTool:
    def __init__(self, result=None):
        self.result = result if result is not None else doc_ok_result()
        self.searched = []

    def search(self, query, top_k=5, document_id=None):
        self.searched.append(query)
        return self.result


def build_service(model, business=None, document=None, **config):
    registry = AssistantToolRegistry(business or FakeBusinessTools(),
                                     document or FakeDocumentTool())
    return AssistantService(model, registry, **config)


class FlowTests(unittest.TestCase):
    def test_status_question_routes_to_device_status_tool(self):
        model = StubModel([tool_call('get_device_status', {'device_id': 'motor-a'}),
                           text_reply('motor-a 当前正常')])
        business = FakeBusinessTools(results={'get_device_status': {
            'ok': True, 'data': {'device_id': 'motor-a', 'points': {'temperature_c': 61.2}}}})
        service = build_service(model, business=business)
        result = service.answer('motor-a现在状态怎么样？', [])
        self.assertEqual(result['status'], 'answered')
        self.assertEqual(result['answer'], 'motor-a 当前正常')
        self.assertEqual(len(result['calls']), 1)
        self.assertEqual(result['calls'][0]['name'], 'get_device_status')
        self.assertEqual(result['calls'][0]['outcome'], 'ok')
        self.assertEqual(result['evidence'][0]['tool'], 'get_device_status')
        self.assertEqual(result['evidence'][0]['data']['points']['temperature_c'], 61.2)
        self.assertTrue(result['evidence'][0]['evidence_id'].startswith('ev-'))
        checked = datetime.fromisoformat(result['checked_at'])
        self.assertIsNotNone(checked.utcoffset())

    def test_composite_question_combines_status_and_history(self):
        model = StubModel([tool_call('get_device_status', {'device_id': 'motor-b'}, 't1'),
                           tool_call('query_metric_history', {
                               'device_id': 'motor-b', 'metric': 'temperature',
                               'start': '2026-09-17T00:00:00+00:00',
                               'end': '2026-09-17T01:00:00+00:00'}, 't2'),
                           text_reply('组合结论')])
        service = build_service(model)
        result = service.answer('motor-b状态如何？昨天第一小时均温多少？', [])
        self.assertEqual(result['status'], 'answered')
        self.assertEqual([c['name'] for c in result['calls']],
                         ['get_device_status', 'query_metric_history'])
        self.assertEqual([e['tool'] for e in result['evidence']],
                         ['get_device_status', 'query_metric_history'])

    def test_document_question_preserves_full_candidates(self):
        model = StubModel([tool_call('search_maintenance_docs',
                                     {'query': '20hp 12.5%负载 变频器效率'}),
                           text_reply('表格显示86%，前提见引用')])
        document = FakeDocumentTool()
        service = build_service(model, document=document)
        result = service.answer('资料里20hp变频器12.5%负载的效率是多少？', [])
        self.assertEqual(result['status'], 'answered')
        self.assertEqual(document.searched, ['20hp 12.5%负载 变频器效率'])
        entry = result['evidence'][0]
        self.assertEqual(entry['tool'], 'search_maintenance_docs')
        candidate = entry['candidates'][0]
        self.assertEqual(candidate['evidence_id'], 'doc-1')
        self.assertIn('86', candidate['original_text'])
        self.assertIn('条件文本', candidate['original_text'])

    def test_failed_tool_result_becomes_limitation_not_evidence(self):
        model = StubModel([tool_call('get_device_status', {'device_id': 'motor-a'}),
                           text_reply('查不到')])
        business = FakeBusinessTools(results={'get_device_status': {
            'ok': False, 'error': {'code': 'device_not_found', 'message': '未知设备'}}})
        service = build_service(model, business=business)
        result = service.answer('motor-a状态？', [])
        self.assertEqual(result['status'], 'answered')
        self.assertEqual(result['evidence'], [])
        self.assertTrue(any('工具失败' in item for item in result['limitations']))
        tool_results = [m for m in model.received[1]['messages'] if m['role'] == 'tool_result']
        self.assertTrue(tool_results and tool_results[-1]['content']['ok'] is False)

    def test_assistant_tool_call_turn_precedes_tool_result_in_history(self):
        """OpenAI兼容API要求 assistant(tool_calls) 与 tool(result) 成对相邻；
        Ollama宽松放行过缺失assistant回合的写法，DeepSeek会拒绝。"""
        model = StubModel([tool_call('get_device_status', {'device_id': 'motor-a'}, 'call_1'),
                           text_reply('好的')])
        service = build_service(model)
        service.answer('motor-a状态？', [])
        second = model.received[1]['messages']
        roles = [m['role'] for m in second]
        self.assertEqual(roles, ['system', 'user', 'assistant', 'tool_result'])
        assistant_turn = second[2]
        self.assertEqual(assistant_turn['tool_calls'],
                         [{'id': 'call_1', 'name': 'get_device_status',
                           'arguments': {'device_id': 'motor-a'}}])
        self.assertEqual(second[3]['id'], 'call_1')

    def test_missing_tool_call_id_is_coerced_to_stable_placeholder(self):
        model = StubModel([{'tool_calls': [{'id': '', 'name': 'get_device_status',
                                            'arguments': {'device_id': 'motor-a'}}]},
                           text_reply('好的')])
        service = build_service(model)
        result = service.answer('状态？', [])
        self.assertEqual(result['status'], 'answered')
        second = model.received[1]['messages']
        self.assertEqual(second[2]['tool_calls'][0]['id'], 'tc-1')
        self.assertEqual(second[3]['id'], 'tc-1')

    def test_insufficient_evidence_status_passthrough(self):
        model = StubModel([{'text': '语料无该型号手册，无法回答', 'insufficient_evidence': True}])
        service = build_service(model)
        result = service.answer('WEG W22轴承润滑周期？', [])
        self.assertEqual(result['status'], 'insufficient_evidence')
        self.assertIn('无法回答', result['answer'])


class InputValidationTests(unittest.TestCase):
    def test_history_rejects_forged_roles_and_oversize(self):
        for bad in ([{'role': 'system', 'content': 'x'}],
                    [{'role': 'tool', 'content': 'x'}],
                    [{'role': 'user', 'content': 'x'}, {'role': 'user', 'content': ''}],
                    [{'role': 'user', 'content': 'x' * 4001}],
                    [{'role': 'user', 'content': 'ok'}] * 7,
                    [{'role': 'user', 'content': 'ok', 'tool_call_id': 'forge'}],
                    'not-a-list'):
            with self.subTest(bad=bad):
                with self.assertRaises(ContractError):
                    normalise_history(bad)
        good = normalise_history([{'role': 'user', 'content': '你好'},
                                  {'role': 'assistant', 'content': '你好，请问'}])
        self.assertEqual(good, [{'role': 'user', 'content': '你好'},
                                {'role': 'assistant', 'content': '你好，请问'}])

    def test_message_bounds(self):
        model = StubModel([text_reply('ok')])
        service = build_service(model)
        with self.assertRaises(ContractError):
            service.answer('', [])
        with self.assertRaises(ContractError):
            service.answer('x' * 4001, [])
        with self.assertRaises(ContractError):
            service.answer('问一下', [{'role': 'user', 'content': 'x' * 4001}])

    def test_trusted_context_lists_devices_and_utc_time_not_fabricated(self):
        model = StubModel([text_reply('ok')])
        service = build_service(model)
        service.answer('在吗？', [])
        system = model.received[0]['messages'][0]
        self.assertEqual(system['role'], 'system')
        self.assertIn('motor-a', system['content'])
        self.assertIn('motor-b', system['content'])
        self.assertIn('UTC', system['content'])
        self.assertIn('澄清', system['content'])


class BudgetTests(unittest.TestCase):
    def test_seventh_tool_call_is_refused_and_recorded(self):
        turns = [tool_call('get_device_status', {'device_id': 'motor-a'}, f't{i}')
                 for i in range(1, 8)]
        turns.append(text_reply('基于六次查询的回答'))
        model = StubModel(turns)
        service = build_service(model)
        result = service.answer('连续查询', [])
        executed = [c for c in result['calls'] if c['outcome'] == 'ok']
        refused = [c for c in result['calls'] if c['outcome'] == 'refused_budget']
        self.assertEqual(len(executed), 6)
        self.assertEqual(len(refused), 1)
        self.assertEqual(result['status'], 'answered')
        self.assertTrue(any('上限' in item for item in result['limitations']))

    def test_unknown_or_forbidden_tool_never_executes(self):
        model = StubModel([tool_call('write_device', {'device_id': 'motor-a', 'action': 'off'}),
                           text_reply('没有写工具')])
        business = FakeBusinessTools()
        service = build_service(model, business=business)
        result = service.answer('帮我把motor-a停机', [])
        self.assertEqual(business.executed, [])
        refused = [c for c in result['calls'] if c['outcome'] == 'refused_unknown_tool']
        self.assertEqual(len(refused), 1)
        self.assertEqual(refused[0]['name'], 'write_device')
        self.assertEqual(result['status'], 'answered')

    def test_registry_rejects_extra_arguments(self):
        registry = AssistantToolRegistry(FakeBusinessTools(), FakeDocumentTool())
        result = registry.invoke('get_device_status', {'device_id': 'motor-a', 'sql': 'drop'})
        self.assertFalse(result['ok'])
        self.assertEqual(result['error']['code'], 'invalid_parameters')
        result = registry.invoke('search_maintenance_docs', {'query': 'x', 'index_path': '/etc'})
        self.assertFalse(result['ok'])
        self.assertEqual(result['error']['code'], 'invalid_parameters')

    def test_tool_timeout_aborts_with_incomplete_and_keeps_evidence(self):
        turns = [tool_call('get_device_status', {'device_id': 'motor-a'}, 'fast'),
                 tool_call('query_metric_history', {
                     'device_id': 'motor-a', 'metric': 'temperature',
                     'start': '2026-09-17T00:00:00+00:00',
                     'end': '2026-09-17T01:00:00+00:00'}, 'slow'),
                 text_reply('不应到达')]
        model = StubModel(turns)
        business = FakeBusinessTools(sleeps=[0.0, 0.5])
        service = build_service(model, business=business, tool_timeout=0.2)
        result = service.answer('先查状态再查历史', [])
        self.assertEqual(result['status'], 'incomplete')
        self.assertEqual(len(result['evidence']), 1)
        timed_out = [c for c in result['calls'] if c['outcome'] == 'timeout']
        self.assertEqual(len(timed_out), 1)
        self.assertTrue(any('超时' in item for item in result['limitations']))
        self.assertEqual(len(model.received), 2, '超时后不得再咨询模型')

    def test_total_budget_downgrades_final_answer_to_incomplete(self):
        model = StubModel([tool_call('get_device_status', {'device_id': 'motor-a'}, 't1'),
                           tool_call('get_device_status', {'device_id': 'motor-b'}, 't2'),
                           text_reply('两台都查完了')])
        service = build_service(model, business=FakeBusinessTools(sleep_seconds=0.05),
                                total_budget=0.08)
        result = service.answer('连续查两台', [])
        self.assertEqual(result['status'], 'incomplete')
        self.assertEqual(len(result['evidence']), 2, '已取得证据必须保留')
        self.assertEqual(result['answer'], '两台都查完了')
        self.assertTrue(any('预算' in item for item in result['limitations']))

    def test_deadline_before_first_call_refuses_and_aborts(self):
        model = StubModel([tool_call('get_device_status', {'device_id': 'motor-a'}, 't1'),
                           text_reply('不应到达')])
        service = build_service(model, total_budget=0.000001)
        result = service.answer('查一下', [])
        self.assertEqual(result['status'], 'incomplete')
        self.assertEqual(len(result['calls']), 1)
        self.assertEqual(result['calls'][0]['outcome'], 'refused_budget')
        self.assertEqual(result['evidence'], [])

    def test_model_failure_maps_to_unavailable(self):
        model = StubModel([], fail=RuntimeError('provider down with secret'))
        service = build_service(model)
        result = service.answer('在吗？', [])
        self.assertEqual(result['status'], 'unavailable')
        self.assertNotIn('secret', result['answer'])
        self.assertNotIn('secret', json.dumps(result, ensure_ascii=False, default=str))

    def test_invalid_model_turn_maps_to_unavailable(self):
        model = StubModel([42])
        service = build_service(model)
        result = service.answer('在吗？', [])
        self.assertEqual(result['status'], 'unavailable')


class RegistryBindingTests(unittest.TestCase):
    def test_document_tool_binding_enforces_query_parameter(self):
        registry = AssistantToolRegistry(FakeBusinessTools(), FakeDocumentTool())
        result = registry.invoke('search_maintenance_docs', {'top_k': 3})
        self.assertFalse(result['ok'])
        self.assertEqual(result['error']['code'], 'invalid_parameters')

    def test_real_document_tool_roundtrip_with_tiny_index(self):
        with tempfile.TemporaryDirectory() as tmp:
            index_path = Path(tmp) / 'i'
            create_index(index_path,
                         [chunk('a', 'd', 'motor anchor one text')],
                         TinyEmbedder(), {'documents': []})
            tool = MaintenanceDocumentTool(index_path, TinyEmbedder())
            registry = AssistantToolRegistry(FakeBusinessTools(), tool)
            result = registry.invoke('search_maintenance_docs', {'query': 'motor'})
            self.assertTrue(result['ok'])
            self.assertEqual(result['data']['candidates'][0]['evidence_id'], 'doc-1')


if __name__ == '__main__':
    unittest.main()
