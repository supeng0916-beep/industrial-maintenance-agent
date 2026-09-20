"""D1 experiment guards: frozen rewrite binding, scoring denominators, read-only index."""
import hashlib
import importlib.util
import json
from pathlib import Path
import tempfile
import unittest

from assistant.rag_evaluation import load_cases
from assistant.rag_index import create_index
from experiments.rag_query_language import (
    bind_rewrites, evaluate_gate, load_rewrites, run_experiment, summarize)
from tests.test_rag_index import TinyEmbedder, chunk


def module_spec():
    spec = importlib.util.find_spec('experiments.rag_query_language')
    assert spec is not None, 'experiments/rag_query_language.py not implemented'
    return spec


def case(cid, question, answerable=True, split='dev'):
    base = dict(case_id=cid, question=question, split=split, answerable=answerable,
                category='direct',
                expected_document_ids=['d'] if answerable else [],
                expected_sections=['Page 1'] if answerable else [],
                required_evidence=[], forbidden_claims=[])
    if answerable:
        base['expected_evidence'] = [dict(document_id='d', source_page='1',
                                          anchors=[question[:6]], match='any')]
    else:
        base['expected_evidence'] = []
    return base


def rewrite(cid, query, candidate):
    return dict(case_id=cid, original_query=query, candidate_query=candidate,
                method='test method', review_notes='test notes')


def frozen_file(tmp, cases, items):
    body = dict(experiment='query-language-dev-v1', created='test',
                purpose='test', source_cases=str(Path(tmp) / 'cases.json'),
                source_cases_sha256=hashlib.sha256((Path(tmp) / 'cases.json').read_bytes()).hexdigest(),
                bias_disclosure='test disclosure', items=items)
    path = Path(tmp) / 'rewrites.json'
    path.write_text(json.dumps(body, ensure_ascii=False), encoding='utf-8')
    return path


class BindingTests(unittest.TestCase):
    def write_cases(self, tmp, cases):
        path = Path(tmp) / 'cases.json'
        path.write_text(json.dumps(cases, ensure_ascii=False), encoding='utf-8')
        return path

    def test_extra_missing_duplicate_and_nonsplit_ids_rejected(self):
        cases = [case('R1', 'anchor one'), case('R2', 'anchor two'),
                 case('N1', 'live value', answerable=False)]
        with tempfile.TemporaryDirectory() as tmp:
            cases_path = self.write_cases(tmp, cases)
            loaded = load_cases(cases_path)
            good = [rewrite('R1', 'anchor one', 'query one'),
                    rewrite('R2', 'anchor two', 'query two'),
                    rewrite('N1', 'live value', 'query three')]
            data = json.loads(frozen_file(tmp, cases, good).read_text(encoding='utf-8'))
            bind_rewrites(loaded, data, cases_path)  # exact dev coverage binds fine
            extra = data['items'] + [rewrite('R9', 'anchor two', 'rogue')]
            data['items'] = extra
            with self.assertRaisesRegex(ValueError, 'extra'):
                bind_rewrites(loaded, data, cases_path)
            missing = [item for item in good if item['case_id'] != 'R2']
            data['items'] = missing
            with self.assertRaisesRegex(ValueError, 'missing'):
                bind_rewrites(loaded, data, cases_path)
            data['items'] = good + [rewrite('R1', 'anchor one', 'again')]
            with self.assertRaisesRegex(ValueError, 'duplicate rewrite case_id'):
                load_rewrites(frozen_file(tmp, cases, data['items']))
            holdout_only = [rewrite('R1', 'anchor one', 'q'),
                            rewrite('R2', 'anchor two', 'q'),
                            rewrite('H1', 'other', 'q')]
            data['items'] = holdout_only
            with self.assertRaisesRegex(ValueError, 'extra'):
                bind_rewrites(loaded, data, cases_path)

    def test_original_query_must_stay_untouched(self):
        cases = [case('R1', 'anchor one')]
        with tempfile.TemporaryDirectory() as tmp:
            cases_path = self.write_cases(tmp, cases)
            loaded = load_cases(cases_path)
            data = json.loads(frozen_file(
                tmp, cases, [rewrite('R1', 'a slightly edited question', 'query one')])
                .read_text(encoding='utf-8'))
            with self.assertRaisesRegex(ValueError, 'original_query drift'):
                bind_rewrites(loaded, data, cases_path)

    def test_case_file_drift_is_rejected(self):
        cases = [case('R1', 'anchor one')]
        with tempfile.TemporaryDirectory() as tmp:
            cases_path = self.write_cases(tmp, cases)
            loaded = load_cases(cases_path)
            items = [rewrite('R1', 'anchor one', 'query one')]
            rewrites_path = frozen_file(tmp, cases, items)
            self.write_cases(tmp, [case('R1', 'anchor one edited')])
            data = json.loads(rewrites_path.read_text(encoding='utf-8'))
            with self.assertRaisesRegex(ValueError, 'case set drifted'):
                bind_rewrites(loaded, data, cases_path)


class DenominatorTests(unittest.TestCase):
    def records(self):
        def record(cid, answerable, o5, r5, o10, r10, o_rank, r_rank):
            def entry(hit5, hit10, rank):
                return dict(hit_at_5=hit5, hit_at_10=hit10, first_anchor_rank=rank)
            return dict(case_id=cid, answerable=answerable, category='direct', method='m',
                        original=entry(o5, o10, o_rank), rewritten=entry(r5, r10, r_rank))
        return [record('R1', True, True, False, True, True, 3, 7),
                record('R2', True, False, True, True, True, None, 2),
                record('R3', True, True, True, True, True, 4, 4),
                record('N1', False, None, None, None, None, None, None)]

    def test_unanswerable_never_enter_positive_denominator(self):
        summary = summarize(self.records())
        self.assertEqual(summary['cases'], 4)
        self.assertEqual(summary['answerable'], 3)
        self.assertEqual(summary['unanswerable'], 1)
        self.assertEqual(summary['original_hit_at_5'], 2)
        self.assertEqual(summary['rewritten_hit_at_5'], 2)
        self.assertEqual(summary['improved_at_5'], ['R2'])
        self.assertEqual(summary['regressed_at_5'], ['R1'])
        self.assertEqual(summary['rank_changes'][0],
                         {'case_id': 'R1', 'original': 3, 'rewritten': 7})


class GateTests(unittest.TestCase):
    def summary(self, o5, o10, r5, r10, total=24):
        return dict(answerable=total, original_hit_at_5=o5, original_hit_at_10=o10,
                    rewritten_hit_at_5=r5, rewritten_hit_at_10=r10)

    def test_gate_pass_fail_and_baseline_reproduction(self):
        self.assertTrue(evaluate_gate(self.summary(15, 19, 16, 19))['pass'])
        self.assertEqual(evaluate_gate(self.summary(15, 19, 16, 19))['status'], 'pass')
        self.assertFalse(evaluate_gate(self.summary(15, 19, 15, 19))['pass'])
        self.assertEqual(evaluate_gate(self.summary(15, 19, 20, 18))['status'], 'fail')
        self.assertEqual(evaluate_gate(self.summary(14, 19, 20, 19))['status'], 'baseline_mismatch')
        self.assertEqual(evaluate_gate(self.summary(15, 19, 30, 19, total=30))['status'],
                         'invalid_denominator')


class ReadOnlyRunTests(unittest.TestCase):
    def test_run_never_touches_index_and_refuses_existing_output(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            index = root / 'index'
            chunks = [chunk('a', 'd', 'anchor one text'), chunk('b', 'e', 'unrelated words')]
            create_index(index, chunks, TinyEmbedder(), {'documents': []})
            before = {p.name: hashlib.sha256(p.read_bytes()).hexdigest()
                      for p in sorted(index.iterdir()) if p.is_file()}
            cases = [case('R1', 'anchor one text'), case('N1', 'live value', answerable=False)]
            cases_path = root / 'cases.json'
            cases_path.write_text(json.dumps(cases, ensure_ascii=False), encoding='utf-8')
            items = [rewrite('R1', 'anchor one text', 'anchor one text'),
                     rewrite('N1', 'live value', 'live value translated')]
            data = json.loads(frozen_file(tmp, cases, items).read_text(encoding='utf-8'))
            pairs = bind_rewrites(load_cases(cases_path), data, cases_path)
            records = run_experiment(index, pairs, TinyEmbedder())
            self.assertEqual(len(records), 2)
            self.assertIsNone(records[1]['rewritten']['hit_at_5'])
            self.assertTrue(records[0]['original']['hit_at_5'])
            summary = summarize(records)
            self.assertEqual(summary['answerable'], 1)
            output = root / 'out'
            output.mkdir()
            import experiments.rag_query_language as m
            self.assertEqual(m.main(['--cases', str(cases_path),
                                     '--rewrites', str(frozen_file(tmp, cases, items)),
                                     '--index', str(index), '--reference', '',
                                     '--output', str(output)]), 1)
            self.assertFalse((output / 'results.json').exists())
            after = {p.name: hashlib.sha256(p.read_bytes()).hexdigest()
                     for p in sorted(index.iterdir()) if p.is_file()}
            self.assertEqual(before, after)


class FrozenRepoInputsTests(unittest.TestCase):
    ROOT = Path(__file__).resolve().parents[1]

    def test_committed_frozen_file_binds_to_committed_case_set(self):
        cases_path = self.ROOT / 'docs/evaluation/real-rag-v0.1.json'
        rewrites_path = self.ROOT / 'docs/evaluation/query-language-dev-v1.json'
        if not rewrites_path.is_file():
            self.fail('docs/evaluation/query-language-dev-v1.json must exist and stay frozen')
        data = load_rewrites(rewrites_path)
        pairs = bind_rewrites(load_cases(cases_path), data, cases_path)
        self.assertEqual(len(pairs), 29)
        answerable = [c for c, _ in pairs if c['answerable']]
        unanswerable = [c for c, _ in pairs if not c['answerable']]
        self.assertEqual(len(answerable), 24)
        self.assertEqual(len(unanswerable), 5)
        # Rewrite wording must actually differ from the original for every case.
        for _, item in pairs:
            self.assertNotEqual(item['original_query'], item['candidate_query'])


if __name__ == '__main__':
    unittest.main()
