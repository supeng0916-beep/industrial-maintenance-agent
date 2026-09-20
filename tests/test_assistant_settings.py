"""D4 配置合同：环境变量只从后端读取；未配置明确报错；日志不出现密钥。"""
import importlib
import inspect
import json
from pathlib import Path
import unittest

from assistant.settings import (
    ASSISTANT_API_KEY_ENV, ASSISTANT_BASE_URL_ENV, ASSISTANT_MODEL_ENV,
    ModelNotConfigured, load_settings, require_settings)

ROOT = Path(__file__).resolve().parents[1]


class LoadSettingsTests(unittest.TestCase):
    def test_missing_or_blank_model_returns_none(self):
        for environ in ({}, {ASSISTANT_MODEL_ENV: ''}, {ASSISTANT_MODEL_ENV: '   '}):
            with self.subTest(environ=environ):
                self.assertIsNone(load_settings(environ))

    def test_loads_model_with_optional_endpoint_and_key(self):
        settings = load_settings({ASSISTANT_MODEL_ENV: 'qwen2.5:7b'})
        self.assertEqual(settings.model, 'qwen2.5:7b')
        self.assertIsNone(settings.base_url)
        self.assertIsNone(settings.api_key)
        full = load_settings({ASSISTANT_MODEL_ENV: 'glm-4-flash',
                              ASSISTANT_BASE_URL_ENV: 'https://example.invalid/v1',
                              ASSISTANT_API_KEY_ENV: 'fake-key-123'})
        self.assertEqual(full.base_url, 'https://example.invalid/v1')
        self.assertEqual(full.api_key, 'fake-key-123')

    def test_blank_optional_values_become_none(self):
        settings = load_settings({ASSISTANT_MODEL_ENV: 'm',
                                  ASSISTANT_BASE_URL_ENV: ' ',
                                  ASSISTANT_API_KEY_ENV: ''})
        self.assertIsNone(settings.base_url)
        self.assertIsNone(settings.api_key)

    def test_environ_must_mapping_like_values_strings(self):
        with self.assertRaises(TypeError):
            load_settings({ASSISTANT_MODEL_ENV: 123})

    def test_require_settings_raises_clear_model_not_configured(self):
        with self.assertRaises(ModelNotConfigured) as ctx:
            require_settings({})
        self.assertIn('ASSISTANT_MODEL', str(ctx.exception))
        self.assertNotIn('密钥', json.dumps([ASSISTANT_MODEL_ENV]))


class RedactionTests(unittest.TestCase):
    SECRET = 'sk-fake-secret-value'

    def settings(self):
        return require_settings({ASSISTANT_MODEL_ENV: 'some-model',
                                 ASSISTANT_BASE_URL_ENV: 'https://example.invalid/v1',
                                 ASSISTANT_API_KEY_ENV: self.SECRET})

    def test_repr_str_and_json_never_contain_secret(self):
        settings = self.settings()
        for text in (repr(settings), str(settings), json.dumps(settings.to_log_dict())):
            self.assertNotIn(self.SECRET, text)
            self.assertIn('some-model', text)

    def test_to_log_dict_masks_endpoint_and_omits_key(self):
        settings = self.settings()
        logged = settings.to_log_dict()
        self.assertNotIn('api_key', logged)
        self.assertNotIn(self.SECRET, json.dumps(logged))
        self.assertEqual(logged['base_url_host'], 'example.invalid')
        self.assertNotIn('https://example.invalid/v1', json.dumps(logged))

    def test_actual_attribute_access_still_works_internally(self):
        settings = self.settings()
        self.assertEqual(settings.api_key, self.SECRET)


class PurityTests(unittest.TestCase):
    def test_module_does_not_import_network_libraries(self):
        source = inspect.getsource(importlib.import_module('assistant.settings'))
        for banned in ('import requests', 'import httpx', 'import socket',
                       'import openai', 'import langchain', 'from langchain'):
            self.assertNotIn(banned, source)

    def test_load_settings_never_touches_os_environ_by_default_argument(self):
        signature = inspect.signature(load_settings)
        self.assertIn('environ', signature.parameters)


class EnvExampleTests(unittest.TestCase):
    def test_env_example_lists_empty_placeholders_only(self):
        path = ROOT / '.env.example'
        self.assertTrue(path.is_file(), '.env.example must exist as the sample config')
        text = path.read_text(encoding='utf-8')
        for name in (ASSISTANT_MODEL_ENV, ASSISTANT_BASE_URL_ENV, ASSISTANT_API_KEY_ENV):
            self.assertIn(name, text)
        for line in text.splitlines():
            stripped = line.strip()
            if not stripped or stripped.startswith('#') or '=' not in line:
                continue
            name, _, value = line.partition('=')
            self.assertEqual(value.strip(), '',
                             f'{name} must stay empty in the sample; never commit real values')


class EnvFileTests(unittest.TestCase):
    def test_load_env_file_parses_quotes_and_never_overrides_existing(self):
        import tempfile
        from assistant.settings import load_env_file
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / '.env'
            path.write_text(
                '# 注释行\n'
                '\n'
                'ASSISTANT_MODEL=glm-4-flash\n'
                'ASSISTANT_API_KEY="quoted secret"\n'
                "ASSISTANT_BASE_URL='https://open.bigmodel.cn/api/paas/v4'\n"
                'ASSISTANT_MODEL=duplicate-ignored\n'
                'MALFORMED LINE WITHOUT EQUALS\n',
                encoding='utf-8')
            environ = {'ASSISTANT_MODEL': 'already-set'}
            loaded = load_env_file(path, environ)
            self.assertEqual(loaded, ['ASSISTANT_API_KEY', 'ASSISTANT_BASE_URL'])
            self.assertEqual(environ['ASSISTANT_MODEL'], 'already-set')
            self.assertEqual(environ['ASSISTANT_API_KEY'], 'quoted secret')
            self.assertEqual(environ['ASSISTANT_BASE_URL'],
                             'https://open.bigmodel.cn/api/paas/v4')

    def test_missing_env_file_is_a_noop(self):
        import tempfile
        from assistant.settings import load_env_file
        with tempfile.TemporaryDirectory() as tmp:
            self.assertEqual(load_env_file(Path(tmp) / 'nope.env', {}), [])


if __name__ == '__main__':
    unittest.main()
