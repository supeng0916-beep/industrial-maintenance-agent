"""D1 single-variable experiment: equivalent English rewrite of dev-set queries.

Read-only for the frozen case set and the existing index; writes only into a
brand-new output directory. Scoring reuses assistant.rag_evaluation.score_evidence
and assistant.rag_index.search_index so this experiment cannot drift from the
baseline scoring rules.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from assistant.rag_evaluation import load_cases, score_evidence  # noqa: E402
from assistant.rag_index import read_index, search_index  # noqa: E402

EXPERIMENT = 'query-language-dev-v1'
# Gate agreed for entering D2: dev Hit@5 above the frozen 15/24 baseline and
# Hit@10 not below 19/24 (docs/superpowers/plans/2026-09-18-remaining-development.md D1).
GATE_BASELINE = {
    'hit_at_5': 15, 'hit_at_10': 19, 'denominator': 24,
    'source': 'docs/verification/m4-real-rag/e5-evaluation.json (dev answerable)',
}
ITEM_FIELDS = {'case_id', 'original_query', 'candidate_query', 'method', 'review_notes'}


def _sha256(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def load_rewrites(path):
    data = json.loads(Path(path).read_text(encoding='utf-8'))
    items = data.get('items') if isinstance(data, dict) else data
    if not isinstance(data, dict) or data.get('experiment') != EXPERIMENT or not isinstance(items, list) or not items:
        raise ValueError(f'rewrite file must be a {EXPERIMENT} object with a nonempty items list')
    for key in ('source_cases', 'source_cases_sha256', 'bias_disclosure'):
        if not isinstance(data.get(key), str) or not data[key].strip():
            raise ValueError(f'rewrite file must record nonempty {key}')
    seen = set()
    for item in items:
        if not isinstance(item, dict) or set(item) != ITEM_FIELDS:
            raise ValueError('rewrite item must have exactly: ' + ', '.join(sorted(ITEM_FIELDS)))
        for key in sorted(ITEM_FIELDS):
            if not isinstance(item[key], str) or not item[key].strip():
                raise ValueError(f'rewrite item field {key} must be nonempty text')
        if item['case_id'] in seen:
            raise ValueError(f'duplicate rewrite case_id: {item["case_id"]}')
        seen.add(item['case_id'])
    return data


def bind_rewrites(cases, rewrite_data, cases_path):
    """Rewrites must cover exactly the dev cases, keep every original query, and
    be bound to the exact frozen case file bytes."""
    if _sha256(cases_path) != rewrite_data['source_cases_sha256']:
        raise ValueError('frozen source_cases_sha256 does not match the case file; case set drifted')
    dev = {c['case_id']: c for c in cases if c['split'] == 'dev'}
    items = rewrite_data['items']
    ids = [item['case_id'] for item in items]
    extra = sorted(set(ids) - set(dev))
    missing = sorted(set(dev) - set(ids))
    if extra or missing:
        raise ValueError(f'rewrites must cover exactly the dev split; extra={extra} missing={missing}')
    pairs = []
    for item in items:
        case = dev[item['case_id']]
        if item['original_query'] != case['question']:
            raise ValueError(f'original_query drift for {item["case_id"]}: frozen file must carry the untouched question')
        pairs.append((case, item))
    return pairs


def _variant(index, embedder, query):
    started = time.monotonic()
    result = search_index(index, query, embedder, top_k=10)
    return result, time.monotonic() - started


def _entry(case, query, index, embedder):
    result, elapsed = _variant(index, embedder, query)
    entry = {'query': query,
             'top10': [{'rank': c['rank'], 'chunk_id': c['chunk_id'], 'distance': c['distance']}
                       for c in result['candidates']],
             'elapsed_seconds': elapsed,
             'first_anchor_rank': None, 'hit_at_5': None, 'hit_at_10': None}
    if case['answerable']:
        candidates = result['candidates']
        entry['first_anchor_rank'] = next(
            (c['rank'] for c in candidates if score_evidence(case, [c])[0]), None)
        for k in (5, 10):
            entry[f'hit_at_{k}'] = any(score_evidence(case, candidates[:k]))
    return entry


def run_experiment(index, pairs, embedder, reference=None):
    """Query both variants per case. Unanswerable cases keep candidates with null hits."""
    records = []
    for case, item in pairs:
        record = {'case_id': case['case_id'], 'answerable': case['answerable'],
                  'category': case['category'],
                  'method': item['method'],
                  'original': _entry(case, case['question'], index, embedder),
                  'rewritten': _entry(case, item['candidate_query'], index, embedder)}
        if reference is not None and case['case_id'] in reference:
            record['original_matches_frozen_top10'] = (
                [c['chunk_id'] for c in record['original']['top10']] ==
                [c['chunk_id'] for c in reference[case['case_id']]['candidates_top10']])
        records.append(record)
    return records


def summarize(records):
    answerable = [r for r in records if r['answerable']]
    summary = {'cases': len(records), 'answerable': len(answerable),
               'unanswerable': len(records) - len(answerable)}
    for label in ('original', 'rewritten'):
        for k in (5, 10):
            summary[f'{label}_hit_at_{k}'] = sum(1 for r in answerable if r[label][f'hit_at_{k}'])
    for k in (5, 10):
        summary[f'improved_at_{k}'] = sorted(r['case_id'] for r in answerable
                                             if r['rewritten'][f'hit_at_{k}'] and not r['original'][f'hit_at_{k}'])
        summary[f'regressed_at_{k}'] = sorted(r['case_id'] for r in answerable
                                              if r['original'][f'hit_at_{k}'] and not r['rewritten'][f'hit_at_{k}'])
    summary['rank_changes'] = [
        {'case_id': r['case_id'], 'original': r['original']['first_anchor_rank'],
         'rewritten': r['rewritten']['first_anchor_rank']}
        for r in answerable
        if r['original']['first_anchor_rank'] != r['rewritten']['first_anchor_rank']]
    return summary


def evaluate_gate(summary, baseline=GATE_BASELINE):
    """Gate compares fractions against the frozen baseline counts and requires the
    re-run original queries to reproduce that baseline exactly."""
    total = summary['answerable']
    if total != baseline['denominator']:
        return {'pass': False, 'status': 'invalid_denominator',
                'reason': f'answerable dev count {total} != frozen denominator {baseline["denominator"]}'}
    reproduced = (summary['original_hit_at_5'] == baseline['hit_at_5'] and
                  summary['original_hit_at_10'] == baseline['hit_at_10'])
    hit5_ok = summary['rewritten_hit_at_5'] > baseline['hit_at_5']
    hit10_ok = summary['rewritten_hit_at_10'] >= baseline['hit_at_10']
    status = 'pass' if (reproduced and hit5_ok and hit10_ok) else (
        'baseline_mismatch' if not reproduced else 'fail')
    return {'pass': status == 'pass', 'status': status,
            'thresholds': {'hit_at_5': f'> {baseline["hit_at_5"]}/{baseline["denominator"]}',
                           'hit_at_10': f'>= {baseline["hit_at_10"]}/{baseline["denominator"]}'},
            'baseline_reproduced': reproduced}


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--cases', default='docs/evaluation/real-rag-v0.1.json')
    parser.add_argument('--rewrites', default='docs/evaluation/query-language-dev-v1.json')
    parser.add_argument('--index', default='docs/verification/m4-real-rag/doe-e5-final')
    parser.add_argument('--reference', default='docs/verification/m4-real-rag/e5-evaluation.json')
    parser.add_argument('--model', default='e5')
    parser.add_argument('--output', required=True,
                        help='new directory for results.json; must not already exist')
    args = parser.parse_args(argv)
    try:
        output = Path(args.output).absolute()
        if output.exists() or output.is_symlink():
            raise FileExistsError(f'output directory already exists; choose a new one: {output}')
        from assistant.rag_embeddings import LocalEmbedder
        cases = load_cases(args.cases)
        rewrite_data = load_rewrites(args.rewrites)
        pairs = bind_rewrites(cases, rewrite_data, args.cases)
        index_config, _ = read_index(args.index)
        reference = None
        if args.reference and Path(args.reference).is_file():
            loaded = json.loads(Path(args.reference).read_text(encoding='utf-8'))
            reference = {item['case']['case_id']: item for item in loaded.get('results', [])}
        embedder = LocalEmbedder(args.model)
        started = datetime.now(timezone.utc)
        records = run_experiment(args.index, pairs, embedder, reference)
        summary = summarize(records)
        gate = evaluate_gate(summary)
        payload = {
            'ok': True, 'experiment': EXPERIMENT,
            'started_at': started.isoformat(),
            'finished_at': datetime.now(timezone.utc).isoformat(),
            'fixed_inputs': {
                'cases_file': args.cases, 'cases_sha256': _sha256(args.cases),
                'rewrites_file': args.rewrites, 'rewrites_sha256': _sha256(args.rewrites),
                'index_path': str(Path(args.index).absolute()),
                'index_config_sha256': _sha256(Path(args.index) / 'index.json'),
                'index_chunks_sha256': index_config['chunks_sha256'],
                'index_chunk_count': index_config['chunk_count'],
                'model_signature': embedder.signature,
                'scoring': 'assistant.rag_evaluation.score_evidence (NFKC + casefold + whitespace, document/page/anchor)',
            },
            'gate': gate, 'summary': summary, 'results': records,
            'limitations': [
                'Rewrites were prepared by an agent that had read the failure records; this is a diagnostic reframe, not a blind translation.',
                'Manual rewrites are not an automatically deployable query translator.',
                'Unanswerable dev cases keep candidates with null hits and never enter the hit denominators.',
                'Anchor presence is not answer correctness; distances are not confidence.',
            ],
        }
        output.mkdir(parents=True)
        (output / 'results.json').write_text(
            json.dumps(payload, ensure_ascii=False, sort_keys=True, indent=1) + '\n', encoding='utf-8')
    except Exception as exc:  # surface a clean JSON error like assistant.rag
        print(json.dumps({'ok': False, 'error': {'code': type(exc).__name__, 'message': str(exc)}},
                         ensure_ascii=False))
        return 1
    print(json.dumps({'ok': True, 'output': str(output / 'results.json'),
                      'summary': {k: v for k, v in summary.items() if not k.startswith('rank')},
                      'gate': gate}, ensure_ascii=False, indent=1))
    return 0


if __name__ == '__main__':
    sys.exit(main())
