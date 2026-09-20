"""D7 助手API：参数边界422、未配置503不影响监控路由、忙状态可重试、合同透传。"""
import threading
import time
import unittest
from datetime import datetime, timezone
from pathlib import Path
import tempfile

from fastapi.testclient import TestClient

import api
from assistant.agent_contracts import ContractError


def contract_result(status='answered', answer='回答', **overrides):
    result = {'status': status, 'answer': answer, 'evidence': [],
              'limitations': [], 'calls': [],
              'checked_at': '2026-09-18T10:00:00+00:00'}
    result.update(overrides)
    return result


class StubService:
    def __init__(self, result=None, gate=None, delay=0.0, error=None):
        self.result = result if result is not None else contract_result()
        self.gate = gate
        self.delay = delay
        self.error = error
        self.received = []

    def answer(self, message, history=None):
        self.received.append({'message': message, 'history': history})
        if self.error is not None:
            raise self.error
        if self.delay:
            time.sleep(self.delay)
        if self.gate is not None:
            self.gate.wait()
        return self.result


class AssistantApiTests(unittest.TestCase):
    def setUp(self):
        directory = tempfile.TemporaryDirectory()
        self.addCleanup(directory.cleanup)
        self.db = Path(directory.name) / 'assistant-api.sqlite3'

    def client_with(self, service):
        client = TestClient(api.create_app(self.db, assistant_service=service))
        self.addCleanup(client.close)
        return client

    def test_valid_question_returns_service_contract(self):
        service = StubService(contract_result(evidence=[{'evidence_id': 'ev-1'}],
                                              calls=[{'name': 'get_device_status'}]))
        client = self.client_with(service)
        response = client.post('/api/assistant/chat', json={
            'message': 'motor-a现在状态？',
            'history': [{'role': 'user', 'content': '你好'},
                        {'role': 'assistant', 'content': '请问要查什么？'}]})
        self.assertEqual(response.status_code, 200)
        body = response.json()
        self.assertEqual(body['status'], 'answered')
        self.assertEqual(body['answer'], '回答')
        self.assertIn('checked_at', body)
        self.assertEqual(service.received[0]['message'], 'motor-a现在状态？')
        self.assertEqual(service.received[0]['history'],
                         [{'role': 'user', 'content': '你好'},
                          {'role': 'assistant', 'content': '请问要查什么？'}])

    def test_parameter_violations_return_422(self):
        client = self.client_with(StubService())
        bad_bodies = [
            {'message': ''},
            {'message': 'x' * 4001},
            {},
            {'message': 'ok', 'history': [{'role': 'user', 'content': 'x' * 4001}]},
            {'message': 'ok', 'history': [{'role': 'user', 'content': ''}]},
            {'message': 'ok', 'history': [{'role': 'tool', 'content': 'x'}]},
            {'message': 'ok', 'history': [{'role': 'system', 'content': 'x'}]},
            {'message': 'ok', 'history': [{'role': 'user', 'content': 'ok'}] * 7},
            {'message': 'ok', 'history': 'not-a-list'},
            {'message': 'ok', 'model': 'glm-4'},
            {'message': 'ok', 'tools': [{'name': 'write_device'}]},
            {'message': 'ok', 'tool_results': [{'data': 1}]},
            {'message': 'ok', 'base_url': 'https://example.invalid'},
            {'message': 'ok', 'history': [{'role': 'user', 'content': 'ok', 'tool_call_id': 'x'}]},
        ]
        for body in bad_bodies:
            with self.subTest(body=body):
                response = client.post('/api/assistant/chat', json=body)
                self.assertEqual(response.status_code, 422)
                self.assertEqual(response.json()['error']['code'], 'invalid_parameters')

    def test_unconfigured_service_returns_503_and_monitor_routes_unaffected(self):
        from contextlib import closing
        from storage import initialize, open_database
        with closing(open_database(self.db)) as conn:
            initialize(conn)
        client = TestClient(api.create_app(self.db))
        self.addCleanup(client.close)
        response = client.post('/api/assistant/chat', json={'message': '在吗？'})
        self.assertEqual(response.status_code, 503)
        self.assertEqual(response.json()['error']['code'], 'assistant_unavailable')
        devices = client.get('/api/devices')
        self.assertEqual(devices.status_code, 200)

    def test_insufficient_evidence_and_incomplete_are_normal_200(self):
        for status in ('insufficient_evidence', 'incomplete', 'unavailable'):
            with self.subTest(status=status):
                client = self.client_with(StubService(contract_result(status=status)))
                response = client.post('/api/assistant/chat', json={'message': '问点啥'})
                self.assertEqual(response.status_code, 200)
                self.assertEqual(response.json()['status'], status)

    def test_contract_error_maps_to_422(self):
        service = StubService(error=ContractError('invalid_message', 'message必须为非空文本'))
        client = self.client_with(service)
        response = client.post('/api/assistant/chat', json={'message': '外观正常'})
        self.assertEqual(response.status_code, 422)
        self.assertEqual(response.json()['error']['code'], 'invalid_message')

    def test_concurrent_requests_get_clear_retryable_busy_status(self):
        release = threading.Event()
        service = StubService(gate=release)
        entered = threading.Event()

        original_answer = service.answer

        def answer_with_signal(message, history=None):
            entered.set()
            return original_answer(message, history)

        service.answer = answer_with_signal
        client = self.client_with(service)
        results = {}

        def first_call():
            results['first'] = client.post('/api/assistant/chat',
                                           json={'message': '第一条'})

        worker = threading.Thread(target=first_call)
        worker.start()
        self.assertTrue(entered.wait(timeout=2), '第一条请求未进入服务')
        second = client.post('/api/assistant/chat', json={'message': '第二条'})
        self.assertEqual(second.status_code, 503)
        self.assertEqual(second.json()['error']['code'], 'assistant_busy')
        release.set()
        worker.join(timeout=5)
        self.assertIn('first', results, '第一条请求未在时限内完成')
        self.assertEqual(results['first'].status_code, 200)
        # 忙状态结束后可再次正常调用。
        third = client.post('/api/assistant/chat', json={'message': '第三条'})
        self.assertEqual(third.status_code, 200)


if __name__ == '__main__':
    unittest.main()
