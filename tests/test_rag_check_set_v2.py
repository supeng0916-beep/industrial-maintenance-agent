"""D2 evaluation guards: frozen check-set binding, denominators, merge diagnostic, read-only run."""
import hashlib
import importlib.util
import json
from pathlib import Path
import tempfile
import unittest

from assistant.rag_evaluation import load_cases
from assistant.rag_index import create_index, read_index
from experiments.rag_check_set_v2 import (
    BASELINES, FROZEN_CASES_V1_SHA256, FROZEN_CHECK_SET_SHA256,
    baseline_status, load_d1_records, main, merge_reproduction_status,
    rrf_merge, run_cases, score_d1_records, summarize_set, validate_check_set)
from tests.test_rag_index import TinyEmbedder, chunk

ROOT = Path(__file__).resolve().parents[1]


def module_spec():
    spec = importlib.util.find_spec('experiments.rag_check_set_v2')
    assert spec is not None, 'experiments/rag_check_set_v2.py not implemented'
    return spec


def check_case(cid, question, answerable=True, category='table_condition', doc='d'):
    base = dict(case_id=cid, question=question, split='holdout', answerable=answerable,
                category=category,
                expected_document_ids=[doc] if answerable else [],
                expected_sections=['Page 1'] if answerable else [],
                required_evidence=[], forbidden_claims=[])
    if answerable:
        base['expected_evidence'] = [dict(document_id=doc, source_page='1',
                                          anchors=[question[:6]], match='any')]
    else:
        base['expected_evidence'] = []
    return base


def full_check_set():
    answerable = [check_case(f'C{i:02d}', f'anchor question {i:02d} text',
                             category=cat, doc='d')
                  for i, cat in enumerate(['table_condition'] * 4 + ['near_concept'] * 4 +
                                          ['model_mismatch'] * 4, 1)]
    unanswerable = [check_case(f'CN{i:02d}', f'live value question {i:02d}',
                               answerable=False, category=cat)
                    for i, cat in enumerate(['requires_live_tool'] * 3 +
                                            ['requires_history_tool'] * 3, 1)]
    return answerable + unanswerable


class CheckSetValidationTests(unittest.TestCase):
    def test_too_few_answerable_or_unanswerable_rejected(self):
        cases = full_check_set()
        with self.assertRaisesRegex(ValueError, 'answerable'):
            validate_check_set([c for c in cases
                                if c['answerable'] or c['category'] != 'requires_history_tool'])
        with self.assertRaisesRegex(ValueError, 'unanswerable'):
            validate_check_set([c for c in cases if c['answerable'] or c['case_id'] == 'CN01'])

    def test_missing_required_coverage_rejected(self):
        answerable = [check_case(f'C{i:02d}', f'anchor question {i:02d}', category='direct')
                      for i in range(12)]
        unanswerable = [check_case(f'CN{i:02d}', f'live value {i:02d}', answerable=False,
                                   category='requires_live_tool') for i in range(6)]
        with self.assertRaisesRegex(ValueError, 'answerable coverage'):
            validate_check_set(answerable + unanswerable)
        good = full_check_set()
        kept_answerable = [c for c in good if c['answerable']]
        live_only = [check_case(f'CN{i:02d}', f'live value {i:02d}', answerable=False,
                                category='requires_live_tool') for i in range(6)]
        with self.assertRaisesRegex(ValueError, 'unanswerable coverage'):
            validate_check_set(kept_answerable + live_only)

    def test_frozen_repo_check_set_passes_and_differs_from_v01(self):
        check_path = ROOT / 'docs/evaluation/real-rag-v0.2.json'
        cases_path = ROOT / 'docs/evaluation/real-rag-v0.1.json'
        self.assertTrue(check_path.is_file(),
                        'docs/evaluation/real-rag-v0.2.json must exist and stay frozen')
        self.assertEqual(hashlib.sha256(check_path.read_bytes()).hexdigest(),
                         FROZEN_CHECK_SET_SHA256)
        self.assertEqual(hashlib.sha256(cases_path.read_bytes()).hexdigest(),
                         FROZEN_CASES_V1_SHA256)
        cases = load_cases(check_path)
        shape = validate_check_set(cases)
        self.assertEqual(shape, {'answerable': 14, 'unanswerable': 6})
        self.assertTrue(all(c['split'] == 'holdout' for c in cases))
        old_questions = {c['question'] for c in load_cases(cases_path)}
        new_questions = {c['question'] for c in cases}
        self.assertFalse(old_questions & new_questions, 'check questions must be new')
        for case in cases:
            self.assertTrue(case['question'].strip())
            if case['answerable']:
                self.assertTrue(case['expected_evidence'])


class RunCasesTests(unittest.TestCase):
    def test_hits_denominators_and_frozen_comparison(self):
        with tempfile.TemporaryDirectory() as tmp:
            index = Path(tmp) / 'index'
            create_index(index, [chunk('a', 'd', 'motor anchor one text'),
                                 chunk('b', 'e', 'pump words only')],
                         TinyEmbedder(), {'documents': []})
            cases = [check_case('K1', 'motor anchor one text', doc='d'),
                     check_case('N1', 'live value now', answerable=False,
                                category='requires_live_tool')]
            records = run_cases(index, cases, TinyEmbedder())
            by_id = {r['case_id']: r for r in records}
            self.assertTrue(by_id['K1']['result']['hit_at_5'])
            self.assertIsNone(by_id['N1']['result']['hit_at_5'])
            summary = summarize_set(records)
            self.assertEqual(summary['answerable'], 1)
            self.assertEqual(summary['hit_at_5'], 1)
            self.assertEqual(summary['missed_at_5'], [])
            self.assertEqual(baseline_status(summary, BASELINES['dev']), 'invalid_denominator')
            grown = dict(summary, answerable=24, hit_at_5=15, hit_at_10=19)
            self.assertEqual(baseline_status(grown, BASELINES['dev']), 'reproduced')
            drifted = dict(grown, hit_at_5=14)
            self.assertEqual(baseline_status(drifted, BASELINES['dev']), 'baseline_mismatch')


class MergeDiagnosticTests(unittest.TestCase):
    def test_rrf_merge_dedupes_and_interleaves(self):
        merged = rrf_merge(['x', 'y', 'z'], ['y', 'w', 'z'])
        self.assertEqual(merged, ['y', 'z', 'x', 'w'])
        self.assertEqual(len(merged), 4)

    def test_score_d1_records_binds_cases_and_counts_hits(self):
        with tempfile.TemporaryDirectory() as tmp:
            index = Path(tmp) / 'index'
            create_index(index, [chunk('a', 'd', 'motor anchor one text'),
                                 chunk('b', 'e', 'pump words only'),
                                 chunk('c', 'f', 'fan belt words')],
                         TinyEmbedder(), {'documents': []})
            _, chunks = read_index(index)
            chunk_by_id = {c['chunk_id']: c for c in chunks}
            case = check_case('K1', 'motor anchor one text', doc='d')
            d1_record = {
                'case_id': 'K1', 'answerable': True, 'category': 'direct', 'method': 'm',
                'original': {'top10': [{'rank': 1, 'chunk_id': chunk_by_id['a']['chunk_id'],
                                        'distance': 0.1}]},
                'rewritten': {'top10': [{'rank': 1, 'chunk_id': chunk_by_id['b']['chunk_id'],
                                         'distance': 0.2},
                                        {'rank': 2, 'chunk_id': chunk_by_id['c']['chunk_id'],
                                         'distance': 0.25}]},
            }
            records, counts = score_d1_records([d1_record], chunk_by_id, {'K1': case})
            self.assertEqual(counts['answerable'], 1)
            self.assertTrue(records[0]['original']['hit_at_5'])
            self.assertFalse(records[0]['rewritten']['hit_at_5'])
            self.assertTrue(records[0]['merged']['hit_at_5'])
            self.assertEqual(records[0]['merged']['first_anchor_rank'], 1)
            with self.assertRaisesRegex(ValueError, 'not in case set'):
                score_d1_records([dict(d1_record, case_id='ZZ')], chunk_by_id, {'K1': case})

    def test_merge_reproduction_status(self):
        counts = {'original_hit_at_5': 15, 'original_hit_at_10': 19,
                  'rewritten_hit_at_5': 20, 'rewritten_hit_at_10': 23}
        self.assertEqual(merge_reproduction_status(counts), 'reproduced')
        self.assertEqual(merge_reproduction_status(dict(counts, rewritten_hit_at_10=22)),
                         'baseline_mismatch')

    def test_load_d1_records_rejects_foreign_payload(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / 'd1.json'
            path.write_text(json.dumps({'experiment': 'other', 'ok': True, 'results': []}),
                            encoding='utf-8')
            with self.assertRaisesRegex(ValueError, 'query-language-dev-v1'):
                load_d1_records(path)


class MainRunTests(unittest.TestCase):
    def write_json(self, tmp, name, payload):
        path = Path(tmp) / name
        path.write_text(json.dumps(payload, ensure_ascii=False), encoding='utf-8')
        return path

    def tiny_cases_v1(self):
        return [
            dict(check_case('R1', 'motor anchor one text', category='direct'), split='dev'),
            dict(check_case('N1', 'live value now', answerable=False,
                            category='requires_live_tool'), split='dev'),
        ]

    def test_full_run_happy_path_is_read_only_and_refuses_existing_output(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            index = root / 'index'
            create_index(index, [chunk('a', 'd', 'motor anchor one text'),
                                 chunk('b', 'e', 'pump words only')],
                         TinyEmbedder(), {'documents': []})
            before = {p.name: hashlib.sha256(p.read_bytes()).hexdigest()
                      for p in sorted(index.iterdir()) if p.is_file()}
            cases_path = self.write_json(root, 'cases.json', self.tiny_cases_v1())
            check_path = self.write_json(root, 'check.json', full_check_set())
            output = root / 'out'
            self.assertEqual(main(['--cases', str(cases_path), '--check-set', str(check_path),
                                   '--d1-results', '', '--reference', '',
                                   '--index', str(index), '--model', 'e5',
                                   '--output', str(output)],
                                  embedder_factory=lambda name: TinyEmbedder()), 0)
            payload = json.loads((output / 'results.json').read_text(encoding='utf-8'))
            self.assertTrue(payload['ok'])
            self.assertEqual(payload['experiment'], 'rag-check-set-v2')
            self.assertEqual(payload['sets']['check_set']['summary']['answerable'], 12)
            self.assertEqual(payload['sets']['check_set']['summary']['unanswerable'], 6)
            self.assertEqual(payload['sets']['check_set']['summary']['hit_at_5'], 12)
            self.assertEqual(payload['sets']['old_dev']['summary']['answerable'], 1)
            self.assertIn('first_measurement_no_threshold',
                          payload['sets']['check_set']['baseline_status'])
            self.assertFalse(payload['merge_diagnostic']['included'])
            after = {p.name: hashlib.sha256(p.read_bytes()).hexdigest()
                     for p in sorted(index.iterdir()) if p.is_file()}
            self.assertEqual(before, after)
            self.assertEqual(main(['--cases', str(cases_path), '--check-set', str(check_path),
                                   '--d1-results', '', '--reference', '',
                                   '--index', str(index), '--output', str(output)],
                                  embedder_factory=lambda name: TinyEmbedder()), 1)
            self.assertEqual(len(list(output.iterdir())), 1)

    def test_frozen_case_drift_is_refused(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            fake = root / 'docs' / 'evaluation'
            fake.mkdir(parents=True)
            cases = self.tiny_cases_v1()
            cases[0]['question'] = 'drifted question'
            cases_path = self.write_json(fake, 'real-rag-v0.1.json', cases)
            check_path = self.write_json(root, 'check.json', full_check_set())
            index = root / 'index'
            create_index(index, [chunk('a', 'd', 'motor anchor one text')],
                         TinyEmbedder(), {'documents': []})
            output = root / 'out'
            self.assertEqual(main(['--cases', str(cases_path), '--check-set', str(check_path),
                                   '--d1-results', '', '--reference', '',
                                   '--index', str(index), '--output', str(output)],
                                  embedder_factory=lambda name: TinyEmbedder()), 1)
            self.assertFalse(output.exists())


if __name__ == '__main__':
    unittest.main()
