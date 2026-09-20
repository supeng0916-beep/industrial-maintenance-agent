"""D4 模型供应商适配（离线替身级）：协议转换、工具规格、无密钥日志、惰性导入。

真实连通性测试用 RUN_REAL_MODEL=1 单独门控，与替身测试严格区分。
"""
import inspect
import json
import os
import unittest

from assistant.agent import AssistantToolRegistry, TOOL_DESCRIPTIONS
from assistant.model_provider import (
    DEFAULT_OLLAMA_BASE_URL, build_assistant_service, build_model,
    messages_to_langchain, specs_to_openai_tools)
from assistant.settings import ModelSettings
from tests.test_assistant_agent import FakeBusinessTools, FakeDocumentTool


class FakeResponse:
    def __init__(self, tool_calls=None, text=''):
        self.tool_calls = tool_calls or []
        self.content = text


class FakeChatClient:
    def __init__(self, response):
        self.response = response
        self.bound = []
        self.invoked = []

    def bind_tools(self, tools):
        self.bound.append(tools)
        self._bound_client = self
        return self

    def invoke(self, messages):
        self.invoked.append(messages)
        return self.response


def make_adapter(client):
    from assistant.model_provider import LangChainModelAdapter
    adapter = LangChainModelAdapter.__new__(LangChainModelAdapter)
    adapter._client = client
    adapter._has_tools = False
    return adapter


class SpecConversionTests(unittest.TestCase):
    def test_specs_gain_descriptions_and_property_types(self):
        registry = AssistantToolRegistry(FakeBusinessTools(), FakeDocumentTool())
        specs = registry.specs()
        by_name = {s['name']: s for s in specs}
        self.assertEqual(set(by_name), {'get_device_status', 'query_metric_history',
                                        'list_alarms', 'search_maintenance_docs'})
        for name, description in TOOL_DESCRIPTIONS.items():
            self.assertEqual(by_name[name]['description'], description)
        self.assertEqual(by_name['get_device_status']['properties']['device_id']['type'], 'string')
        self.assertEqual(by_name['query_metric_history']['properties']['limit']['type'], 'integer')
        self.assertEqual(by_name['search_maintenance_docs']['properties']['top_k']['type'], 'integer')

    def test_specs_to_openai_tools_format(self):
        registry = AssistantToolRegistry(FakeBusinessTools(), FakeDocumentTool())
        tools = specs_to_openai_tools(registry.specs())
        by_name = {t['function']['name']: t for t in tools}
        self.assertEqual(set(by_name), set(TOOL_DESCRIPTIONS))
        status = by_name['get_device_status']
        self.assertEqual(status['type'], 'function')
        self.assertEqual(status['function']['parameters']['required'], ['device_id'])
        self.assertNotIn('limit', status['function']['parameters']['properties'])
        history = by_name['query_metric_history']['function']['parameters']
        self.assertEqual(set(history['required']), {'device_id', 'metric', 'start', 'end'})
        self.assertIn('limit', history['properties'])


class MessageConversionTests(unittest.TestCase):
    def test_all_roles_convert(self):
        messages = [
            {'role': 'system', 'content': '可信上下文'},
            {'role': 'user', 'content': '问题'},
            {'role': 'assistant', 'content': '部分回答'},
            {'role': 'tool_result', 'id': 't1', 'content': {'ok': True, 'data': {'x': 1}}},
        ]
        converted = messages_to_langchain(messages)
        kinds = [type(m).__name__ for m in converted]
        self.assertEqual(kinds, ['SystemMessage', 'HumanMessage', 'AIMessage', 'ToolMessage'])
        self.assertEqual(converted[3].tool_call_id, 't1')
        self.assertIn('"ok": true', converted[3].content)


class AdapterProtocolTests(unittest.TestCase):
    def test_tool_call_response_maps_to_protocol(self):
        client = FakeChatClient(FakeResponse(tool_calls=[
            {'id': 'call_1', 'name': 'get_device_status', 'args': {'device_id': 'motor-a'}},
            {'id': '', 'name': 'list_alarms', 'args': {'device_id': 'motor-b',
                                                       'start': '2026-09-19T00:00:00+00:00',
                                                       'end': '2026-09-19T01:00:00+00:00'}},
        ]))
        turn = make_adapter(client).plan([{'role': 'user', 'content': 'q'}], [])
        self.assertIsNone(turn.get('text'))
        self.assertEqual(turn['tool_calls'][0]['name'], 'get_device_status')
        self.assertEqual(turn['tool_calls'][0]['arguments'], {'device_id': 'motor-a'})
        self.assertTrue(turn['tool_calls'][1]['id'], '缺失id时必须生成非空占位')

    def test_text_response_maps_to_protocol(self):
        client = FakeChatClient(FakeResponse(text='最终回答'))
        turn = make_adapter(client).plan([{'role': 'user', 'content': 'q'}], [])
        self.assertEqual(turn['text'], '最终回答')
        self.assertNotIn('tool_calls', turn)

    def test_tool_specs_bound_on_every_plan(self):
        client = FakeChatClient(FakeResponse(text='好'))
        registry = AssistantToolRegistry(FakeBusinessTools(), FakeDocumentTool())
        make_adapter(client).plan([{'role': 'user', 'content': 'q'}], registry.specs())
        self.assertEqual(len(client.bound), 1)
        self.assertEqual({t['function']['name'] for t in client.bound[0]}, set(TOOL_DESCRIPTIONS))


class BuildTests(unittest.TestCase):
    def test_build_model_returns_adapter_with_settings(self):
        adapter = build_model(ModelSettings(model='qwen2.5:7b'))
        self.assertEqual(adapter.model_name, 'qwen2.5:7b')

    def test_build_model_uses_configured_base_url_and_timeout(self):
        adapter = build_model(ModelSettings(model='m', base_url='http://127.0.0.1:11434'),
                              timeout_seconds=7)
        self.assertEqual(adapter.model_name, 'm')

    def test_default_base_url_is_local(self):
        self.assertTrue(DEFAULT_OLLAMA_BASE_URL.startswith('http://127.0.0.1')
                        or DEFAULT_OLLAMA_BASE_URL.startswith('http://localhost'))

    def test_module_imports_no_other_network_sdk(self):
        import assistant.model_provider as module
        source = inspect.getsource(module)
        for banned in ('import requests', 'import openai', 'import httpx'):
            self.assertNotIn(banned, source)

    def test_build_assistant_service_none_when_model_unset(self):
        self.assertIsNone(build_assistant_service(environ={}))

    def test_build_assistant_service_wires_registry_when_configured(self):
        from assistant.agent import AssistantService
        service = build_assistant_service(
            environ={'ASSISTANT_MODEL': 'qwen2.5:7b'},
            business_tools=FakeBusinessTools(), document_tool=FakeDocumentTool())
        self.assertIsInstance(service, AssistantService)
        names = {spec['name'] for spec in service._registry.specs()}
        self.assertEqual(names, set(TOOL_DESCRIPTIONS))

    def test_real_service_validation_rejected_before_model_call(self):
        service = build_assistant_service(
            environ={'ASSISTANT_MODEL': 'qwen2.5:7b'},
            business_tools=FakeBusinessTools(), document_tool=FakeDocumentTool())
        from assistant.agent_contracts import ContractError
        with self.assertRaises(ContractError):
            service.answer('', [])


@unittest.skipUnless(os.environ.get('RUN_REAL_MODEL') == '1',
                     'requires local Ollama server and pulled model')
class RealConnectionTests(unittest.TestCase):
    def test_real_minimal_connection(self):
        from assistant.settings import load_settings
        import os as real_os
        settings = load_settings({'ASSISTANT_MODEL':
                                  real_os.environ.get('ASSISTANT_MODEL', 'qwen2.5:7b')})
        adapter = build_model(settings, timeout_seconds=60)
        turn = adapter.plan([{'role': 'user', 'content': '只回复两个字：在线'}], [])
        self.assertTrue(turn.get('text'))
        self.assertNotIn('tool_calls', turn)


class CloudProviderRoutingTests(unittest.TestCase):
    SECRET = 'sk-fake-cloud-key'

    def cloud_settings(self, base_url='https://open.bigmodel.cn/api/paas/v4'):
        return ModelSettings(model='glm-4-flash', base_url=base_url, api_key=self.SECRET)

    def test_api_key_routes_to_cloud_adapter(self):
        adapter = build_model(self.cloud_settings())
        self.assertEqual(type(adapter).__name__, 'OpenAICompatibleAdapter')
        local = build_model(ModelSettings(model='qwen2.5:7b'))
        self.assertEqual(type(local).__name__, 'LangChainModelAdapter')

    def test_cloud_adapter_requires_explicit_base_url(self):
        from assistant.model_provider import ModelProviderError
        with self.assertRaisesRegex(ModelProviderError, 'ASSISTANT_BASE_URL'):
            build_model(ModelSettings(model='glm-4-flash', base_url=None,
                                      api_key=self.SECRET))

    def test_cloud_adapter_plan_protocol_with_fake_client(self):
        client = FakeChatClient(FakeResponse(tool_calls=[
            {'id': 'call_9', 'name': 'search_maintenance_docs',
             'args': {'query': '20hp 12.5% 效率'}}]))
        from assistant.model_provider import OpenAICompatibleAdapter
        adapter = OpenAICompatibleAdapter.__new__(OpenAICompatibleAdapter)
        adapter.model_name = 'glm-4-flash'
        adapter._client = client
        turn = adapter.plan([{'role': 'user', 'content': 'q'}], [])
        self.assertEqual(turn['tool_calls'][0]['name'], 'search_maintenance_docs')
        client2 = FakeChatClient(FakeResponse(text='云端回答'))
        adapter2 = OpenAICompatibleAdapter.__new__(OpenAICompatibleAdapter)
        adapter2.model_name = 'glm-4-flash'
        adapter2._client = client2
        self.assertEqual(adapter2.plan([{'role': 'user', 'content': 'q'}], []),
                         {'text': '云端回答'})

    def test_service_and_logs_never_expose_cloud_key(self):
        service = build_assistant_service(
            environ={'ASSISTANT_MODEL': 'glm-4-flash',
                     'ASSISTANT_BASE_URL': 'https://open.bigmodel.cn/api/paas/v4',
                     'ASSISTANT_API_KEY': self.SECRET},
            business_tools=FakeBusinessTools(), document_tool=FakeDocumentTool())
        self.assertIsNotNone(service)
        serialized = json.dumps({'model': service._model.model_name}, ensure_ascii=False)
        self.assertNotIn(self.SECRET, serialized)
        self.assertNotIn(self.SECRET, repr(service._model))
        self.assertNotIn(self.SECRET, str(service._model))
        self.assertEqual(service._model.model_name, 'glm-4-flash')


if __name__ == '__main__':
    unittest.main()
