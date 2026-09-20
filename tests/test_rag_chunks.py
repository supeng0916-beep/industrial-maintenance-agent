import hashlib
import json
import tempfile
import unittest
from pathlib import Path

from assistant.knowledge_documents import DocumentError, load_documents
from tests.test_knowledge_chunks import FRONTMATTER, CharacterTokenizer


def document(body, **metadata):
    import yaml
    meta = yaml.safe_load(FRONTMATTER.split('---')[1])
    meta.update(metadata)
    return dict(metadata=meta, body=body, body_start=7, text='prefix\n'+body,
                source_path='doc.md', sha256='a'*64)


class RagChunkTests(unittest.TestCase):
    def build(self, body, **metadata):
        from assistant.rag_chunks import build_rag_chunks
        return build_rag_chunks([document(body, **metadata)], CharacterTokenizer(),
                                format_passage=lambda text: 'passage: '+text)

    def test_sentences_preserve_contiguous_source_and_full_input_budget(self):
        body = '# Manual\n\n## Page 2\n\n### Inspection\n\n' + ('Check the bearing before startup. '*40)
        chunks = self.build(body)
        self.assertGreater(len(chunks), 2)
        self.assertEqual(''.join(c['original_text'] for c in chunks), body)
        cursor = 7
        for c in chunks:
            self.assertEqual(c['source_start'], cursor)
            cursor = c['source_end']
            self.assertEqual(c['original_text'], ('prefix\n'+body)[c['source_start']:cursor])
            self.assertTrue(c['embedding_text'].startswith('passage: '))
            self.assertEqual(c['token_count'], len(c['embedding_text'])+2)
            self.assertLessEqual(c['token_count'], 512)
        self.assertEqual(chunks[-1]['source_pages'], ['2'])
        self.assertIn('Inspection', chunks[-1]['context_text'])

    def test_table_and_list_keep_scope_and_parent_heading(self):
        body = '# Manual\n\n## Page 9\n\n### Limits\n\nApplicability: Only for dry indoor operation.\n\n' + ('Check first. '*24) + '\n\n| speed | limit |\n| --- | --- |\n| 20 | 80 |\n\n- Stop the motor.\n- Isolate power.\n'
        chunks = self.build(body, applicability='Model X only')
        for c in chunks:
            if '| speed |' in c['original_text'] or '- Stop' in c['original_text']:
                self.assertIn('Limits', c['context_text'])
                self.assertIn('Applicability: Only for dry indoor operation.', c['context_text'])
                self.assertIn('Model X only', c['context_text'])
                self.assertEqual(c['source_pages'], ['9'])
        self.assertEqual(''.join(c['original_text'] for c in chunks), body)

    def test_parent_premise_survives_subheading(self):
        chunks = self.build('## Scope\n\nFor Model X only. Use indoors.\n\n### Table\n\n| A | B |\n|---|---|\n| 1 | 2 |')
        table = chunks[-1]
        self.assertIn('For Model X only. Use indoors.', table['context_text'])
        self.assertIn('Scope', table['context_text'])

    def test_common_abbreviation_is_not_a_sentence_boundary(self):
        from assistant.rag_chunks import ChunkingError
        with self.assertRaises(ChunkingError):
            self.build('x'*380+' U.S. Department '+ 'y'*160+'.')

    def test_atomic_sentence_table_and_prefix_overflow_fail(self):
        from assistant.rag_chunks import ChunkingError, build_rag_chunks
        for body in ['x'*600, '| A | B |\n|---|---|\n|'+'x'*600+'| 1 |', '- '+'x'*600]:
            with self.subTest(body=body[:20]), self.assertRaises(ChunkingError):
                self.build(body)
        with self.assertRaises(ChunkingError):
            build_rag_chunks([document('Short.')], CharacterTokenizer(), format_passage=lambda s: 'p'*510+s)

    def test_pages_do_not_bleed_and_metadata_fallback(self):
        chunks = self.build('## Page 2\n\nFirst.\n\n## 第3页\n\nSecond.', source_pages=['2','3'])
        self.assertEqual([c['source_pages'] for c in chunks], [['2'], ['3']])
        self.assertEqual(self.build('Content.', source_pages=['A-2'])[0]['source_pages'], ['A-2'])

    def test_table_keeps_following_note_with_values(self):
        body = '## Page 1\n\nScope.\n\nTable 1. Savings\n\n```text\nHP Savings\n10 250\n```\n\nNote: Based on 8,000 hours per year at 75% load and $0.08/kWh.\n\nMore details.'
        chunks = self.build(body)
        table = next(c for c in chunks if '10 250' in c['original_text'])
        self.assertIn('8,000 hours', table['embedding_text'])
        self.assertIn('$0.08/kWh', table['embedding_text'])
        self.assertEqual(''.join(c['original_text'] for c in chunks), body)

    def test_table_keeps_asterisk_footnote_after_source_credit(self):
        chunks = self.build('## Page 1\n\nScope.\n\nTable 1. Efficiency\n\n```text\nLoad Efficiency\n75 95.2\n```\n\nSource: University\n\n*Results vary by design. This motor is atypical.\n\nOther details.')
        table = next(c for c in chunks if '75 95.2' in c['original_text'])
        self.assertIn('Results vary by design', table['embedding_text'])
        self.assertIn('This motor is atypical', table['embedding_text'])

    def test_long_bullet_splits_sentences_with_condition_repeated(self):
        body = '• Only for the specified load. '+('Check wiring. '*60)
        chunks = self.build(body)
        self.assertGreater(len(chunks), 1)
        self.assertEqual(''.join(c['original_text'] for c in chunks), body)
        self.assertTrue(all('Only for the specified load.' in c['embedding_text'] for c in chunks))

    def test_long_numeric_table_repeats_header_and_footer_per_row_group(self):
        body = '## Page 1\n\nTable 1. Efficiency\n\n```text\nLoad Efficiency\n'+ ''.join(f'{n} 95.2\n' for n in range(100))+'```\n\n*Results vary by motor design.'
        chunks = self.build(body)
        self.assertGreater(len(chunks), 1)
        self.assertEqual(''.join(c['original_text'] for c in chunks), body)
        for chunk in chunks:
            if '95.2' in chunk['original_text']:
                self.assertIn('Load Efficiency', chunk['embedding_text'])
                self.assertIn('Results vary by motor design.', chunk['embedding_text'])
                self.assertLessEqual(chunk['token_count'], 512)

    def test_table_repeats_immediate_introduction_referencing_its_number(self):
        body = '## Page 1\n\nThe efficiency of a 1,800 RPM, 100-horsepower motor appears in Table 1 below.\n\nTable 1. Motor efficiency\n\n```text\nLoad Efficiency\n75 95.2\n100 94.4\n```\n\n*Results vary.'
        table = next(c for c in self.build(body) if '75 95.2' in c['original_text'])
        self.assertIn('1,800 RPM, 100-horsepower', table['context_text'])
        source = next(s for s in table['context_sources'] if '1,800 RPM' in s['text'])
        self.assertEqual(source['source_pages'], ['1'])
        self.assertEqual(('prefix\n'+body)[source['source_start']:source['source_end']], source['text'])
        below = self.build(body.replace('in Table 1 below.', 'in the table below.'))
        self.assertTrue(any('1,800 RPM' in c['context_text'] for c in below if '75 95.2' in c['original_text']))
        unrelated = self.build(body.replace('in Table 1 below.', 'in Table 2.'))
        self.assertTrue(all('1,800 RPM' not in c['context_text'] for c in unrelated if '75 95.2' in c['original_text']))

    def test_numeric_column_labels_repeat_with_every_table_group(self):
        body = 'Table 1. Efficiency\n\n```text\nHP Load percentage\n 1.6 12.5 25\n'+''.join(f'{n} 80 90 95\n' for n in range(100))+'```\n\n*Typical values only.'
        chunks = self.build(body)
        self.assertGreater(len(chunks), 1)
        self.assertEqual(''.join(c['original_text'] for c in chunks), body)
        for chunk in chunks:
            if '80 90 95' in chunk['original_text']:
                self.assertIn('1.6 12.5 25', chunk['embedding_text'])
                self.assertIn('Typical values only.', chunk['embedding_text'])

    def test_inconsistent_numeric_rows_refuse_ambiguous_table_split(self):
        from assistant.rag_chunks import ChunkingError
        body = '```text\nLoad Efficiency\n'+('1 80 90\n2 95\n'*60)+'```'
        with self.assertRaises(ChunkingError):
            self.build(body)

    def test_explicit_scope_accumulates_multiple_paragraphs(self):
        chunks = self.build('### Scope\n\nFor Model X only.\n\nDo not operate outdoors.\n\n#### Table\n\n| A | B |\n|---|---|\n| 1 | 2 |')
        table = chunks[-1]
        self.assertIn('For Model X only.', table['context_text'])
        self.assertIn('Do not operate outdoors.', table['context_text'])

    def test_long_text_callout_splits_sentences_and_repeats_actual_title(self):
        body = '```text\nMotor Selection Guidelines\n\n'+('Check the motor before operation. '*30)+'\n```'
        chunks = self.build(body)
        self.assertGreater(len(chunks), 1)
        self.assertEqual(''.join(c['original_text'] for c in chunks), body)
        self.assertTrue(all('Motor Selection Guidelines' in c['embedding_text'] for c in chunks))

    def test_local_condition_is_not_promoted_to_whole_page_scope(self):
        chunks = self.build('## Page 1\n\nOnly for fans, use variable torque.\n\nOther text.\n\nTable 1. Any torque\n\n```text\nHP Efficiency\n10 95\n20 96\n```')
        self.assertNotIn('Only for fans', chunks[-1]['context_text'])

    def test_page_break_clears_local_inferred_torque_condition(self):
        body = '# Guide\n\n## Page 1\n\nFor fans only, use variable torque.\n\n## Page 2\n\nTable 1. Variable or constant torque\n\n```text\nHP Efficiency\n10 95\n20 96\n```'
        table = self.build(body)[-1]
        self.assertNotIn('For fans only', table['context_text'])
        self.assertEqual(table['source_pages'], ['2'])

    def test_page_break_ends_previous_page_sidebar_scope(self):
        chunks = self.build('# Manual\n\n## Page 1\n\n### Sidebar\n\nSide note.\n\n## Page 2\n\nMain text.')
        self.assertNotIn('Sidebar', chunks[-1]['context_text'])
        self.assertEqual(chunks[-1]['section'], 'Page 2')
        self.assertEqual(chunks[-1]['source_pages'], ['2'])

    def test_cross_page_repeated_scope_includes_its_origin_page(self):
        chunks = self.build('## Scope\n\n## Page 1\n\nOnly for Model X.\n\n## Page 2\n\nSecond page text.')
        last = chunks[-1]
        if 'Only for Model X.' in last['context_text']:
            self.assertIn('1', last['context_source_pages'])
            self.assertTrue(any(s['text'] == 'Only for Model X.' and s['source_pages'] == ['1'] for s in last['context_sources']))
        self.assertEqual(last['source_pages'], ['2'])
        self.assertIn('2', last['source_pages'])

    def test_external_metadata_validation_and_manifest_whitelist(self):
        import yaml
        meta = document('x')['metadata']
        meta.update(device_ids=[], teaching_only=False, language='en', publisher='Maker',
                    source_url='https://example.org/manual.pdf', source_document_id='manual',
                    source_pages=['2'], applicability='Model X', license='public', source_sha256='a'*64)
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            def load():
                raw = '---\n'+yaml.safe_dump(meta)+'---\nText.'
                (root/'doc.md').write_text(raw)
                (root/'ignored.md').write_text('not valid')
                (root/'manifest.json').write_text(json.dumps({'documents':[dict(document_id='doc-1', path='doc.md', version='1.0', sha256=hashlib.sha256(raw.encode()).hexdigest())]}))
                return load_documents(root/'manifest.json')
            self.assertEqual(load()[0]['metadata'], meta)
            for key, bad in [('language', []), ('source_pages',[2]), ('applicability',{}), ('source_sha256',42)]:
                original = meta[key]
                meta[key] = bad
                with self.subTest(key=key), self.assertRaises(DocumentError):
                    load()
                meta[key] = original
