"""Local index invariants; synthetic vectors are only control-flow test fixtures."""
import importlib
import importlib.util
import json
from pathlib import Path
import tempfile
import unittest


class TinyEmbedder:
    signature={'model_id':'test-only','revision':'fixture','dimension':3,'pooling':'test','normalize':True}
    def embed(self,texts):
        return [[1.,0.,0.] if 'motor' in t.lower() else [0.,1.,0.] for t in texts]
    def format_query(self,text):return text


def chunk(identifier,doc,text):
    return dict(chunk_id=identifier,document_id=doc,version='1',section='Page 1',original_text=text,
                embedding_text=text,context_text='Safety context',source_path=doc+'.md',source_start=0,
                source_end=len(text),source_pages=['1'],token_count=10,
                metadata=dict(document_id=doc,version='1',device_ids=[],product_model=None,language='en',source_url='https://example.org/source',teaching_only=False))


class IndexTests(unittest.TestCase):
    def module(self):
        self.assertIsNotNone(importlib.util.find_spec('assistant.rag_index'),'index not implemented')
        return importlib.import_module('assistant.rag_index')

    def test_real_chroma_persist_reopen_distance_and_evidence(self):
        m=self.module()
        with tempfile.TemporaryDirectory() as root:
            out=Path(root)/'index'
            m.create_index(out,[chunk('a','one','motor maintenance'),chunk('b','two','pump care')],TinyEmbedder(),{'documents':[]})
            result=m.search_index(out,'motor',TinyEmbedder(),top_k=2)
            self.assertEqual([x['chunk_id'] for x in result['candidates']],['a','b'])
            self.assertAlmostEqual(result['candidates'][0]['distance'],0,places=5)
            self.assertAlmostEqual(result['candidates'][1]['distance'],1,places=5)
            self.assertEqual(result['candidates'][0]['source_pages'],['1'])
            self.assertEqual(result['candidates'][0]['context_text'],'Safety context')
            self.assertIn('smaller',result['distance_semantics'])

    def test_signature_missing_files_and_tampering_fail_closed(self):
        m=self.module()
        with tempfile.TemporaryDirectory() as root:
            out=Path(root)/'index';m.create_index(out,[chunk('a','one','motor')],TinyEmbedder(),{})
            wrong=TinyEmbedder();wrong.signature=dict(wrong.signature,revision='other')
            with self.assertRaisesRegex(ValueError,'signature'):m.search_index(out,'motor',wrong)
            (out/'chunks.json').write_text('[]')
            with self.assertRaisesRegex(ValueError,'integrity'):m.search_index(out,'motor',TinyEmbedder())
            (out/'index.json').unlink()
            with self.assertRaises(ValueError):m.search_index(out,'motor',TinyEmbedder())

    def test_new_rebuild_removes_old_documents_and_never_overwrites(self):
        m=self.module()
        with tempfile.TemporaryDirectory() as root:
            old=Path(root)/'old';new=Path(root)/'new'
            m.create_index(old,[chunk('a','one','motor'),chunk('b','two','pump')],TinyEmbedder(),{})
            before=(old/'index.json').read_bytes()
            with self.assertRaises(FileExistsError):m.create_index(old,[chunk('c','three','motor')],TinyEmbedder(),{})
            self.assertEqual((old/'index.json').read_bytes(),before)
            m.create_index(new,[chunk('a','one','motor')],TinyEmbedder(),{})
            self.assertEqual({x['document_id'] for x in m.search_index(new,'motor',TinyEmbedder(),top_k=10)['candidates']},{'one'})
            self.assertEqual(len(m.search_index(old,'motor',TinyEmbedder(),top_k=10)['candidates']),2)

    def test_empty_and_embedding_failure_leave_no_successful_output(self):
        m=self.module()
        with tempfile.TemporaryDirectory() as root:
            out=Path(root)/'index'
            with self.assertRaises(ValueError):m.create_index(out,[],TinyEmbedder(),{})
            class Failing(TinyEmbedder):
                def embed(self,texts):raise ValueError('embedding failed')
            with self.assertRaisesRegex(ValueError,'embedding failed'):m.create_index(out,[chunk('a','one','motor')],Failing(),{})
            self.assertFalse(out.exists())

    def test_query_topk_filters_and_unknown_applicability(self):
        m=self.module()
        with tempfile.TemporaryDirectory() as root:
            out=Path(root)/'index';m.create_index(out,[chunk('a','one','motor'),chunk('b','two','pump')],TinyEmbedder(),{})
            for k in (0,11,True,'5'):
                with self.subTest(k=k),self.assertRaises(ValueError):m.search_index(out,'motor',TinyEmbedder(),top_k=k)
            for filters in ({'sql':'select'},{'device_id':'motor-a'},{'document_id':'missing'}):
                with self.subTest(filters=filters),self.assertRaises(ValueError):m.search_index(out,'motor',TinyEmbedder(),filters=filters)
            r=m.search_index(out,'motor',TinyEmbedder(),filters={'document_id':'two'})
            self.assertEqual([x['document_id'] for x in r['candidates']],['two'])
            self.assertIsNone(r['candidates'][0]['metadata']['product_model'])
            with self.assertRaises(ValueError):m.search_index(out,'  ',TinyEmbedder())

    def test_missing_hnsw_files_fail_before_chroma_can_repair(self):
        m=self.module()
        with tempfile.TemporaryDirectory() as root:
            out=Path(root)/'index';m.create_index(out,[chunk('a','one','motor')],TinyEmbedder(),{})
            victim=next((out/'chroma').glob('*/header.bin'))
            victim.unlink()
            with self.assertRaisesRegex(ValueError,'missing.*storage'):
                m.search_index(out,'motor',TinyEmbedder())
            self.assertFalse(victim.exists())
