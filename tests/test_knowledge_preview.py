"""Preview failures must not publish partial results or touch old results."""
import importlib
import importlib.util
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch


class PreviewTests(unittest.TestCase):
    def module(self):
        self.assertIsNotNone(importlib.util.find_spec('assistant.knowledge_preview'), 'preview not implemented')
        return importlib.import_module('assistant.knowledge_preview')

    def test_missing_tokenizer_is_error_without_fake_counts(self):
        self.module()
        from assistant.knowledge_tokenizer import load_tokenizer
        with tempfile.TemporaryDirectory() as root:
            with self.assertRaisesRegex(ValueError, 'tokenizer'):
                load_tokenizer(root)
            self.assertEqual(list(Path(root).iterdir()), [])

    def test_corrupt_cached_tokenizer_is_not_used(self):
        self.module()
        from assistant.knowledge_tokenizer import load_tokenizer, REVISION
        with tempfile.TemporaryDirectory() as root:
            cache=Path(root)/REVISION;cache.mkdir()
            (cache/'tokenizer.json').write_text('{}')
            with self.assertRaisesRegex(ValueError, 'SHA256'):
                load_tokenizer(root)
            self.assertEqual((cache/'tokenizer.json').read_text(), '{}')

    def test_publish_is_complete_and_refuses_existing_output(self):
        m=self.module()
        with tempfile.TemporaryDirectory() as root:
            out=Path(root)/'result'
            m.publish_preview(out, [], {'ok':True})
            self.assertEqual({p.name for p in out.iterdir()}, {'chunks.json','preview.md','report.json'})
            before={p.name:p.read_bytes() for p in out.iterdir()}
            with self.assertRaises(FileExistsError): m.publish_preview(out, [], {'ok':False})
            self.assertEqual(before,{p.name:p.read_bytes() for p in out.iterdir()})

    def test_write_failure_cleans_partial_new_output(self):
        m=self.module()
        with tempfile.TemporaryDirectory() as root:
            out=Path(root)/'result'
            with patch.object(m, 'render_markdown', side_effect=OSError('disk full')):
                with self.assertRaises(OSError):m.publish_preview(out, [], {'ok':True})
            self.assertFalse(out.exists())
            self.assertEqual(list(Path(root).iterdir()), [])

    def test_coverage_rejects_gap_and_changed_original(self):
        m=self.module()
        docs=[dict(metadata={'document_id':'d'},text='---正文',body_start=3,body='正文',sha256='hash',source_path='d.md')]
        chunk=dict(document_id='d',source_start=3,source_end=5,original_text='正文')
        self.assertTrue(m.check_coverage(docs,[chunk])[0]['complete'])
        with self.assertRaisesRegex(ValueError,'coverage'):m.check_coverage(docs,[])
        with self.assertRaisesRegex(ValueError,'coverage'):m.check_coverage(docs,[dict(chunk,original_text='错误')])

    def test_cli_missing_resources_fails_without_output(self):
        self.module()
        with tempfile.TemporaryDirectory() as root:
            out=Path(root)/'result'
            run=subprocess.run([sys.executable,'-m','assistant.knowledge_preview','--manifest','docs/knowledge/manifest.json','--output',str(out),'--tokenizer-cache',str(Path(root)/'empty')],capture_output=True,text=True)
            self.assertEqual(run.returncode,1,run.stderr)
            self.assertFalse(json.loads(run.stdout)['ok'])
            self.assertFalse(out.exists())


class RealTokenizerTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        from assistant.knowledge_tokenizer import load_tokenizer, DEFAULT_CACHE, REVISION
        if not (DEFAULT_CACHE/REVISION/'tokenizer.json').exists():
            raise unittest.SkipTest('real tokenizer not cached; run CLI --download-tokenizer for acceptance')
        cls.tokenizer=load_tokenizer()

    def test_official_special_tokens_and_no_truncation(self):
        self.assertEqual(self.tokenizer.encode('中文'),[101,704,3152,102])
        self.assertEqual(len(self.tokenizer.encode('温'*600)),602)
        self.assertEqual(len(self.tokenizer.encode('温'*600,add_special_tokens=False)),600)

    def test_real_corpus_full_coverage_stable_ids_and_exact_input_counts(self):
        self.assertIsNotNone(importlib.util.find_spec('assistant.knowledge_documents'),'document loader not implemented')
        from assistant.knowledge_preview import generate_preview
        with tempfile.TemporaryDirectory() as root:
            output=Path(root)/'first'; second=Path(root)/'second'
            report=generate_preview('docs/knowledge/manifest.json',output,self.tokenizer)
            generate_preview('docs/knowledge/manifest.json',second,self.tokenizer)
            self.assertTrue(report['coverage_complete'])
            self.assertEqual(report['document_count'],5)
            self.assertFalse(report['retrieval_evaluated'])
            self.assertEqual((output/'chunks.json').read_bytes(),(second/'chunks.json').read_bytes())
            chunks=json.loads((output/'chunks.json').read_text())
            self.assertGreater(len(chunks),5)
            for chunk in chunks:
                self.assertTrue(any(line.strip() and not line.startswith('#')
                                    for line in chunk['original_text'].splitlines()),
                                'title-only chunks must not occupy retrieval candidates')
            self.assertEqual(len({c['chunk_id'] for c in chunks}),len(chunks))
            for chunk in chunks:
                self.assertEqual(chunk['token_count'],len(self.tokenizer.encode(chunk['embedding_text'],add_special_tokens=True)))
                self.assertLessEqual(chunk['token_count'],512)
                self.assertIsNone(chunk['metadata']['product_model'])
            recovery=[c for c in chunks if c['section']=='已触发告警如何恢复']
            self.assertEqual(len(recovery),1)
            self.assertIn('前提：已有未解除告警',recovery[0]['original_text'])
            self.assertIn('78℃保持、77.9℃恢复',recovery[0]['original_text'])
            self.assertIn('不能将“低于”解释为“小于等于”',recovery[0]['original_text'])

    def test_oversized_real_section_fails_without_output_or_source_changes(self):
        self.assertIsNotNone(importlib.util.find_spec('assistant.knowledge_documents'),'document loader not implemented')
        import hashlib
        from assistant.knowledge_preview import generate_preview
        with tempfile.TemporaryDirectory() as root:
            corpus=Path(root)/'corpus';corpus.mkdir()
            source=Path('docs/knowledge/temperature-alarms.md').read_text()+'\n## 超长不可安全拆分规则\n\n'+'温'*600+'不能省略尾句。\n'
            (corpus/'rule.md').write_text(source)
            manifest={'corpus_id':'test','version':'0.1','reviewed_on':'2026-09-18','status':'documents_only_not_indexed','documents':[{'document_id':'temperature-alarms','path':'rule.md','version':'0.1','sha256':hashlib.sha256(source.encode()).hexdigest()}]}
            (corpus/'manifest.json').write_text(json.dumps(manifest))
            with self.assertRaisesRegex(ValueError,'512'):
                generate_preview(corpus/'manifest.json',Path(root)/'output',self.tokenizer)
            self.assertFalse((Path(root)/'output').exists())
            self.assertEqual((corpus/'rule.md').read_text(),source)
