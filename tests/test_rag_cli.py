import importlib
import importlib.util
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest


class EvaluationTests(unittest.TestCase):
    def module(self):
        self.assertIsNotNone(importlib.util.find_spec('assistant.rag_evaluation'),'evaluation not implemented')
        return importlib.import_module('assistant.rag_evaluation')

    def test_evidence_requires_right_document_page_and_anchor(self):
        m=self.module()
        case=dict(expected_evidence=[dict(document_id='d',source_page='2',anchors=['20 47 86'],match='any')])
        good=dict(document_id='d',source_pages=['2'],original_text='20\n47   86',context_text='')
        for candidate in [dict(good,document_id='wrong'),dict(good,source_pages=['1']),dict(good,original_text='unrelated text')]:
            self.assertEqual(m.score_evidence(case,[candidate]),[False])
        self.assertEqual(m.score_evidence(case,[good]),[True])

    def test_multiple_evidence_and_context_normalization(self):
        m=self.module()
        case=dict(expected_evidence=[dict(document_id='d',source_page='1',anchors=['full load','75%'],match='all'),dict(document_id='e',source_page='2',anchors=['motor'],match='any')])
        candidates=[dict(document_id='d',source_pages=['1'],original_text='７５％',context_text='FULL\nLOAD')]
        self.assertEqual(m.score_evidence(case,candidates),[True,False])

    def test_invalid_eval_schema_is_rejected(self):
        m=self.module()
        with tempfile.TemporaryDirectory() as root:
            p=Path(root)/'cases.json'
            for cases in ({},[dict(case_id='x',question='q')]):
                p.write_text(json.dumps(cases))
                with self.assertRaises(ValueError):m.load_cases(p)

    def test_cli_invalid_inputs_do_not_create_index(self):
        self.assertIsNotNone(importlib.util.find_spec('assistant.rag'),'CLI not implemented')
        with tempfile.TemporaryDirectory() as root:
            out=Path(root)/'index'
            run=subprocess.run([sys.executable,'-m','assistant.rag','build','--manifest',str(Path(root)/'absent.json'),'--index',str(out),'--model','e5'],capture_output=True,text=True)
            self.assertEqual(run.returncode,1,run.stderr)
            self.assertFalse(json.loads(run.stdout)['ok'])
            self.assertFalse(out.exists())

    def test_cross_page_context_anchor_cannot_be_attributed_to_body_page(self):
        m=self.module()
        case=dict(expected_evidence=[dict(document_id='d',source_page='2',anchors=['special condition'],match='any')])
        candidate=dict(document_id='d',source_pages=['2'],original_text='Unrelated page two.',
                       context_text='special condition',context_sources=[dict(text='special condition',source_pages=['1'])])
        self.assertEqual(m.score_evidence(case,[candidate]),[False])
        case['expected_evidence'][0]['source_page']='1'
        self.assertEqual(m.score_evidence(case,[candidate]),[True])

    def test_evaluation_separates_unanswerable_and_preserves_index_identity(self):
        m=self.module()
        from tests.test_rag_index import TinyEmbedder,chunk
        from assistant.rag_index import create_index
        with tempfile.TemporaryDirectory() as root:
            index=Path(root)/'index';create_index(index,[chunk('a','d','motor')],TinyEmbedder(),{'manifest_sha256':'frozen-hash'})
            base=dict(question='motor',category='direct',expected_document_ids=['d'],expected_sections=['Page 1'],required_evidence=[],forbidden_claims=[])
            cases=[dict(base,case_id='R1',split='dev',answerable=True,expected_evidence=[dict(document_id='d',source_page='1',anchors=['motor'],match='any')]),dict(base,case_id='N1',split='holdout',answerable=False,expected_document_ids=[],expected_sections=[],expected_evidence=[])]
            path=Path(root)/'cases.json';path.write_text(json.dumps(cases))
            result=m.evaluate_index(index,path,TinyEmbedder())
            self.assertEqual(result['summaries']['dev']['hit_at_5'],1)
            self.assertIsNone(result['summaries']['holdout']['hit_at_5'])
            self.assertIsNone(result['results'][1]['hit_at_5'])
            self.assertTrue(result['holdout_now_observed'])
            self.assertIn('index_corpus',result)
            self.assertEqual(result['index_corpus']['manifest_sha256'],'frozen-hash')
