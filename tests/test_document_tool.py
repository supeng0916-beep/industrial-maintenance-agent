"""D3 文档检索只读工具：路径不外泄、参数边界、结构化错误、完整证据、型号不补标签。"""
import inspect
import json
import os
import unittest
from pathlib import Path
import tempfile

from assistant.document_tool import REGISTERED_NAME, MaintenanceDocumentTool
from assistant.rag_index import create_index
from tests.test_rag_index import TinyEmbedder, chunk

ROOT = Path(__file__).resolve().parents[1]


def long_chunk(identifier, doc, marker, size=900):
    text = (f'{marker} table body ' + 'x' * size)
    return chunk(identifier, doc, text)


def build_index(root, chunks):
    index = Path(root) / 'index'
    create_index(index, chunks, TinyEmbedder(), {'documents': []})
    return index


class GuardTests(unittest.TestCase):
    def test_registered_name_and_signature_hides_paths(self):
        self.assertEqual(REGISTERED_NAME, 'search_maintenance_docs')
        parameters = inspect.signature(MaintenanceDocumentTool.search).parameters
        self.assertNotIn('index_path', parameters)
        self.assertNotIn('embedder', parameters)
        self.assertNotIn('kwargs', parameters)

    def test_extra_path_like_arguments_are_rejected(self):
        with tempfile.TemporaryDirectory() as tmp:
            index = build_index(tmp, [chunk('a', 'd', 'motor anchor one text')])
            tool = MaintenanceDocumentTool(index, TinyEmbedder())
            for extra in ({'index_path': '/etc/passwd'}, {'embedder': TinyEmbedder()},
                          {'sql': 'select 1'}):
                with self.subTest(extra=extra):
                    result = tool.search('motor', **extra)
                    self.assertFalse(result['ok'])
                    self.assertEqual(result['error']['code'], 'invalid_parameters')
                    self.assertNotIn('/etc/passwd', json.dumps(result, ensure_ascii=False))

    def test_empty_query_and_bad_topk_rejected(self):
        with tempfile.TemporaryDirectory() as tmp:
            index = build_index(tmp, [chunk('a', 'd', 'motor anchor one text')])
            tool = MaintenanceDocumentTool(index, TinyEmbedder())
            for query in ('', '   ', None, 42):
                with self.subTest(query=query):
                    result = tool.search(query)
                    self.assertFalse(result['ok'])
                    self.assertEqual(result['error']['code'], 'invalid_parameters')
            for top_k in (0, 11, -1, '5', True, 2.5, None):
                with self.subTest(top_k=top_k):
                    result = tool.search('motor', top_k=top_k)
                    self.assertFalse(result['ok'])
                    self.assertEqual(result['error']['code'], 'invalid_parameters')

    def test_missing_index_returns_structured_sanitized_error(self):
        with tempfile.TemporaryDirectory() as tmp:
            missing = Path(tmp) / 'no-such-index'
            tool = MaintenanceDocumentTool(missing, TinyEmbedder())
            result = tool.search('motor')
            self.assertFalse(result['ok'])
            self.assertEqual(result['error']['code'], 'index_unavailable')
            self.assertNotIn(str(tmp), result['error']['message'])
            self.assertNotIn('Traceback', result['error']['message'])

    def test_unknown_document_filter_rejected_without_leak(self):
        with tempfile.TemporaryDirectory() as tmp:
            index = build_index(tmp, [chunk('a', 'd', 'motor anchor one text')])
            tool = MaintenanceDocumentTool(index, TinyEmbedder())
            result = tool.search('motor', document_id='does-not-exist')
            self.assertFalse(result['ok'])
            self.assertEqual(result['error']['code'], 'unknown_document_filter')
            result = tool.search('motor', document_id='  ')
            self.assertEqual(result['error']['code'], 'invalid_parameters')

    def test_constructor_validates_dependencies(self):
        with self.assertRaisesRegex(ValueError, 'index'):
            MaintenanceDocumentTool('', TinyEmbedder())
        with self.assertRaisesRegex(ValueError, 'embedder'):
            MaintenanceDocumentTool('some-index', object())


class ResultShapeTests(unittest.TestCase):
    def test_candidates_shape_ids_and_no_universal_label(self):
        with tempfile.TemporaryDirectory() as tmp:
            index = build_index(tmp, [chunk('a', 'd', 'motor anchor one text'),
                                      chunk('b', 'e', 'pump words only')])
            tool = MaintenanceDocumentTool(index, TinyEmbedder())
            result = tool.search('motor', top_k=2)
            self.assertTrue(result['ok'])
            data = result['data']
            self.assertEqual(data['query'], 'motor')
            self.assertEqual(len(data['candidates']), 2)
            first = data['candidates'][0]
            self.assertEqual(first['evidence_id'], 'doc-1')
            for key in ('document_id', 'chunk_id', 'version', 'source_pages',
                        'source_url', 'original_text', 'context_text', 'applicability',
                        'product_model'):
                self.assertIn(key, first)
            self.assertEqual(data['candidates'][1]['evidence_id'], 'doc-2')
            self.assertIsNone(first['product_model'])
            serialized = json.dumps(result, ensure_ascii=False)
            self.assertNotIn('通用', serialized)
            self.assertNotIn('universally', serialized.lower())
            self.assertIn('候选不证明适用性或可回答性', ' '.join(data['limitations']))

    def test_document_filter_narrows_results(self):
        with tempfile.TemporaryDirectory() as tmp:
            index = build_index(tmp, [chunk('a', 'd', 'motor anchor one text'),
                                      chunk('b', 'e', 'pump words only')])
            tool = MaintenanceDocumentTool(index, TinyEmbedder())
            result = tool.search('motor', top_k=5, document_id='e')
            self.assertTrue(result['ok'])
            self.assertEqual([c['document_id'] for c in result['data']['candidates']], ['e'])
            self.assertEqual(result['data']['candidates'][0]['evidence_id'], 'doc-1')

    def test_evidence_ids_are_scoped_to_each_search(self):
        with tempfile.TemporaryDirectory() as tmp:
            index = build_index(tmp, [chunk('a', 'd', 'motor anchor one text'),
                                      chunk('b', 'e', 'pump words only')])
            tool = MaintenanceDocumentTool(index, TinyEmbedder())
            first = tool.search('motor', top_k=2)['data']['candidates']
            second = tool.search('pump', top_k=2)['data']['candidates']
            self.assertEqual([c['evidence_id'] for c in first], ['doc-1', 'doc-2'])
            self.assertEqual([c['evidence_id'] for c in second], ['doc-1', 'doc-2'])
            self.assertNotEqual(first[0]['chunk_id'], second[0]['chunk_id'])

    def test_budget_returns_fewer_complete_chunks_and_counts_omitted(self):
        with tempfile.TemporaryDirectory() as tmp:
            chunks = [long_chunk(f'c{i}', f'd{i}', f'motor marker {i}') for i in range(6)]
            index = build_index(tmp, chunks)
            tool = MaintenanceDocumentTool(index, TinyEmbedder(), text_budget=1000)
            result = tool.search('motor', top_k=6)
            self.assertTrue(result['ok'])
            data = result['data']
            self.assertGreaterEqual(len(data['candidates']), 1)
            self.assertLess(len(data['candidates']), 6)
            self.assertEqual(data['omitted_candidates'], 6 - len(data['candidates']))
            source_by_id = {c['chunk_id']: c for c in chunks}
            for candidate in data['candidates']:
                self.assertEqual(candidate['original_text'],
                                 source_by_id[candidate['chunk_id']]['original_text'])
                self.assertFalse(candidate['original_text'].endswith('…'))
            self.assertTrue(any('预算' in item for item in data['limitations']))


@unittest.skipUnless(os.environ.get('RUN_REAL_EMBEDDINGS') == '1',
                     'requires downloaded real model weights')
class RealE5TraceTests(unittest.TestCase):
    def test_real_query_traces_evidence_to_source_page(self):
        from assistant.rag_embeddings import LocalEmbedder
        index = ROOT / 'docs/verification/m4-real-rag/doe-e5-final'
        tool = MaintenanceDocumentTool(index, LocalEmbedder('e5'))
        result = tool.search('按典型PWM变频器效率表，20hp驱动器在12.5%负载时效率是多少？', top_k=5)
        self.assertTrue(result['ok'], result)
        candidates = result['data']['candidates']
        self.assertTrue(candidates)
        top = candidates[0]
        self.assertEqual(top['evidence_id'], 'doc-1')
        self.assertEqual(top['document_id'], 'doe-motor-ts11')
        self.assertIn('2', top['source_pages'])
        source = ROOT / 'docs/knowledge-real' / f"{top['document_id']}.md"
        self.assertTrue(source.is_file())
        self.assertIn('86', top['original_text'])
        config = json.loads((index / 'index.json').read_text(encoding='utf-8'))
        self.assertTrue(config['corpus']['documents'])


if __name__ == '__main__':
    unittest.main()
