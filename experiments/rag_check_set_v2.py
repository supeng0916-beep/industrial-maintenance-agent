"""D2 evaluation: unchanged default E5 config on three case sets + merge diagnostic.

Read-only for frozen case sets and the existing index; writes only into a brand-new
output directory. This script does NOT change the deployed retrieval configuration:
- Re-runs the frozen v0.1 dev and holdout splits with the original single Chinese query
  to reproduce the published baselines (dev 15/24 @5 and 19/24 @10; holdout 3/10 @5
  and 5/10 @10).
- Runs the new frozen check set (real-rag-v0.2.json) for the first time.
- Computes a zero-model merge diagnostic for the D1 bilingual dual-query idea: RRF-fuse
  the frozen per-case top10 lists recorded in D1 results.json. Deploying that idea needs
  an automatic query translator, which is a D4 model decision, not part of this run.
Scoring reuses assistant.rag_evaluation.score_evidence and assistant.rag_index.search_index.
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

EXPERIMENT = 'rag-check-set-v2'
# Frozen inputs this evaluation is bound to (docs/verification/m4-rag-improvement-v1).
FROZEN_CASES_V1_SHA256 = 'de7004d03d8857024a2f8b4c67c709166a12961f9ec7a2213ec56754465c7a3d'
FROZEN_CHECK_SET_SHA256 = 'd09a53d5c48be1ee0e2112651a3f9eb9c94fc95b62935e21ef7f9e9decdefb3a'
BASELINES = {
    'dev': {'answerable': 24, 'hit_at_5': 15, 'hit_at_10': 19},
    'holdout': {'answerable': 10, 'hit_at_5': 3, 'hit_at_10': 5},
}
D1_REWRITTEN_BASELINE = {'answerable': 24, 'hit_at_5': 20, 'hit_at_10': 23}
CHECK_MIN_ANSWERABLE = 12
CHECK_MIN_UNANSWERABLE = 6
# The plan requires the check set to cover table conditions, near-miss concepts,
# model mismatch, and facts that must go to SQL/business tools instead of documents.
REQUIRED_ANSWERABLE_CATEGORIES = {'table_condition', 'near_concept', 'model_mismatch'}
REQUIRED_UNANSWERABLE_CATEGORIES = {'requires_live_tool', 'requires_history_tool'}
RRF_K = 60


def _sha256(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def validate_check_set(cases):
    """Structural guards for the new check set; counts and required coverage."""
    answerable = [c for c in cases if c['answerable']]
    unanswerable = [c for c in cases if not c['answerable']]
    if len(answerable) < CHECK_MIN_ANSWERABLE:
        raise ValueError(f'check set needs at least {CHECK_MIN_ANSWERABLE} answerable cases, got {len(answerable)}')
    if len(unanswerable) < CHECK_MIN_UNANSWERABLE:
        raise ValueError(f'check set needs at least {CHECK_MIN_UNANSWERABLE} unanswerable cases, got {len(unanswerable)}')
    got_answerable = {c['category'] for c in answerable}
    missing = sorted(REQUIRED_ANSWERABLE_CATEGORIES - got_answerable)
    if missing:
        raise ValueError(f'check set missing answerable coverage: {missing}')
    got_unanswerable = {c['category'] for c in unanswerable}
    missing = sorted(REQUIRED_UNANSWERABLE_CATEGORIES - got_unanswerable)
    if missing:
        raise ValueError(f'check set missing unanswerable coverage: {missing}')
    return {'answerable': len(answerable), 'unanswerable': len(unanswerable)}


def _entry(case, query, index, embedder, reference):
    started = time.monotonic()
    result = search_index(index, query, embedder, top_k=10)
    elapsed = time.monotonic() - started
    entry = {'query': query,
             'top10': [{'rank': c['rank'], 'chunk_id': c['chunk_id'], 'distance': c['distance']}
                       for c in result['candidates']],
             'elapsed_seconds': elapsed,
             'first_anchor_rank': None, 'hit_at_5': None, 'hit_at_10': None}
    candidates = result['candidates']
    if case['answerable']:
        entry['first_anchor_rank'] = next(
            (c['rank'] for c in candidates if score_evidence(case, [c])[0]), None)
        for k in (5, 10):
            entry[f'hit_at_{k}'] = any(score_evidence(case, candidates[:k]))
    if reference is not None and case['case_id'] in reference:
        frozen = [c['chunk_id'] for c in reference[case['case_id']]['candidates_top10']]
        entry['matches_frozen_top10'] = [c['chunk_id'] for c in entry['top10']] == frozen
    return entry


def run_cases(index, cases, embedder, reference=None):
    records = []
    for case in cases:
        records.append({'case_id': case['case_id'], 'answerable': case['answerable'],
                        'category': case['category'],
                        'result': _entry(case, case['question'], index, embedder, reference)})
    return records


def summarize_set(records):
    answerable = [r for r in records if r['answerable']]
    summary = {'cases': len(records), 'answerable': len(answerable),
               'unanswerable': len(records) - len(answerable)}
    for k in (5, 10):
        summary[f'hit_at_{k}'] = sum(1 for r in answerable if r['result'][f'hit_at_{k}'])
        summary[f'missed_at_{k}'] = sorted(r['case_id'] for r in answerable
                                           if not r['result'][f'hit_at_{k}'])
    return summary


def baseline_status(summary, expected):
    if summary['answerable'] != expected['answerable']:
        return 'invalid_denominator'
    reproduced = (summary['hit_at_5'] == expected['hit_at_5'] and
                  summary['hit_at_10'] == expected['hit_at_10'])
    return 'reproduced' if reproduced else 'baseline_mismatch'


def load_d1_records(path):
    data = json.loads(Path(path).read_text(encoding='utf-8'))
    if data.get('experiment') != 'query-language-dev-v1' or data.get('ok') is not True:
        raise ValueError('d1 results must be the frozen query-language-dev-v1 payload')
    records = data.get('results')
    if not isinstance(records, list) or not records:
        raise ValueError('d1 results carry no records')
    return records


def rrf_merge(ids_a, ids_b, k=RRF_K):
    """Reciprocal-rank fusion of two ranked id lists; dedupe keeps the best score,
    ties break toward the first list."""
    scores, first_seen = {}, {}
    for label, ids in (('a', ids_a), ('b', ids_b)):
        for rank, chunk_id in enumerate(ids, 1):
            scores[chunk_id] = scores.get(chunk_id, 0.0) + 1.0 / (k + rank)
            first_seen.setdefault(chunk_id, (0 if label == 'a' else 1, len(first_seen)))
    return sorted(scores, key=lambda cid: (-scores[cid], first_seen[cid]))


def _candidates_from_top10(chunk_by_id, top10):
    candidates = []
    for item in top10:
        chunk = chunk_by_id.get(item['chunk_id'])
        if chunk is None:
            raise ValueError(f'top10 chunk missing from index: {item["chunk_id"]}')
        candidates.append(dict(chunk, rank=item['rank'], distance=item['distance']))
    return candidates


def score_d1_records(d1_records, chunk_by_id, cases_by_id):
    """Score the frozen D1 top10 lists and their RRF merge with the shared scorer.

    D1 records carry no case payload, so the frozen v0.1 cases are bound by case_id.
    """
    records = []
    for record in d1_records:
        if not record.get('answerable'):
            continue
        case = cases_by_id.get(record['case_id'])
        if case is None:
            raise ValueError(f'd1 record case not in case set: {record["case_id"]}')
        original = _candidates_from_top10(chunk_by_id, record['original']['top10'])
        rewritten = _candidates_from_top10(chunk_by_id, record['rewritten']['top10'])
        merged_ids = rrf_merge([c['chunk_id'] for c in original], [c['chunk_id'] for c in rewritten])
        distances = {}
        for candidate in original + rewritten:
            cid = candidate['chunk_id']
            distances[cid] = min(distances.get(cid, candidate['distance']), candidate['distance'])
        merged = [dict(chunk_by_id[cid], rank=rank, distance=distances[cid], rrf=True)
                  for rank, cid in enumerate(merged_ids, 1)]
        entry = {'case_id': record['case_id'], 'original_top1_distance': original[0]['distance']}
        for label, candidates in (('original', original), ('rewritten', rewritten), ('merged', merged)):
            entry[label] = {
                'hit_at_5': any(score_evidence(case, candidates[:5])),
                'hit_at_10': any(score_evidence(case, candidates[:10])),
                'first_anchor_rank': next(
                    (c['rank'] for c in candidates if score_evidence(case, [c])[0]), None)}
        records.append(entry)
    counts = {'answerable': len(records)}
    for label in ('original', 'rewritten', 'merged'):
        for k in (5, 10):
            counts[f'{label}_hit_at_{k}'] = sum(1 for r in records if r[label][f'hit_at_{k}'])
    return records, counts


def merge_reproduction_status(counts):
    ok = (counts['original_hit_at_5'] == BASELINES['dev']['hit_at_5'] and
          counts['original_hit_at_10'] == BASELINES['dev']['hit_at_10'] and
          counts['rewritten_hit_at_5'] == D1_REWRITTEN_BASELINE['hit_at_5'] and
          counts['rewritten_hit_at_10'] == D1_REWRITTEN_BASELINE['hit_at_10'])
    return 'reproduced' if ok else 'baseline_mismatch'


def main(argv=None, embedder_factory=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--cases', default='docs/evaluation/real-rag-v0.1.json')
    parser.add_argument('--check-set', default='docs/evaluation/real-rag-v0.2.json')
    parser.add_argument('--d1-results', default='docs/verification/m4-rag-improvement-v1/results.json')
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
        frozen_default = (Path(args.cases).as_posix().endswith('docs/evaluation/real-rag-v0.1.json')
                          and _sha256(args.cases) != FROZEN_CASES_V1_SHA256)
        if frozen_default:
            raise ValueError('real-rag-v0.1.json drifted from its frozen sha256; refusing to run')
        check_default = (Path(args.check_set).as_posix().endswith('docs/evaluation/real-rag-v0.2.json')
                         and _sha256(args.check_set) != FROZEN_CHECK_SET_SHA256)
        if check_default:
            raise ValueError('real-rag-v0.2.json drifted from its frozen sha256; refreeze first')
        if embedder_factory is None:
            from assistant.rag_embeddings import LocalEmbedder
            embedder_factory = LocalEmbedder
        embedder = embedder_factory(args.model)
        index_config, chunks = read_index(args.index)
        index_config_sha_before = _sha256(Path(args.index) / 'index.json')
        chunk_by_id = {c['chunk_id']: c for c in chunks}
        reference = None
        if args.reference and Path(args.reference).is_file():
            loaded = json.loads(Path(args.reference).read_text(encoding='utf-8'))
            reference = {item['case']['case_id']: item for item in loaded.get('results', [])}
        cases_v1 = load_cases(args.cases)
        check_cases = load_cases(args.check_set)
        check_shape = validate_check_set(check_cases)

        started_at = datetime.now(timezone.utc)
        old_records = run_cases(args.index, cases_v1, embedder, reference)
        old_dev = [r for r in old_records if _split(cases_v1, r['case_id']) == 'dev']
        old_holdout = [r for r in old_records if _split(cases_v1, r['case_id']) == 'holdout']
        sets = {
            'old_dev': {'records': old_dev, 'summary': summarize_set(old_dev),
                        'baseline': BASELINES['dev'],
                        'baseline_status': baseline_status(summarize_set(old_dev), BASELINES['dev'])},
            'old_holdout': {'records': old_holdout, 'summary': summarize_set(old_holdout),
                            'baseline': BASELINES['holdout'],
                            'baseline_status': baseline_status(summarize_set(old_holdout), BASELINES['holdout'])},
        }
        check_records = run_cases(args.index, check_cases, embedder)
        sets['check_set'] = {'records': check_records, 'summary': summarize_set(check_records),
                             'baseline_status': 'first_measurement_no_threshold'}

        merge_payload = {'included': False, 'reason': 'no d1 results provided'}
        if args.d1_results and Path(args.d1_results).is_file():
            d1_records = load_d1_records(args.d1_results)
            merge_records, merge_counts = score_d1_records(
                d1_records, chunk_by_id, {c['case_id']: c for c in cases_v1})
            merge_payload = {'included': True, 'method': f'rrf(k={RRF_K}) on frozen D1 top10 lists',
                             'counts': merge_counts,
                             'reproduction_status': merge_reproduction_status(merge_counts),
                             'records': merge_records}

        index_config_after, _ = read_index(args.index)
        if (index_config_after['chunks_sha256'] != index_config['chunks_sha256'] or
                _sha256(Path(args.index) / 'index.json') != _sha256(Path(args.index) / 'index.json')):
            raise ValueError('index changed during the run; refusing to publish results')

        payload = {
            'ok': True, 'experiment': EXPERIMENT,
            'started_at': started_at.isoformat(),
            'finished_at': datetime.now(timezone.utc).isoformat(),
            'config': {'query_mode': 'original single query (unchanged default)',
                       'index_path': str(Path(args.index).absolute()),
                       'index_chunks_sha256': index_config['chunks_sha256'],
                       'index_chunk_count': index_config['chunk_count'],
                       'model_signature': embedder.signature,
                       'scoring': 'assistant.rag_evaluation.score_evidence (NFKC + casefold + whitespace, document/page/anchor)'},
            'fixed_inputs': {
                'cases_v1': args.cases, 'cases_v1_sha256': _sha256(args.cases),
                'check_set': args.check_set, 'check_set_sha256': _sha256(args.check_set),
                'check_set_shape': check_shape,
                'd1_results': args.d1_results,
                'd1_results_sha256': _sha256(args.d1_results) if args.d1_results and Path(args.d1_results).is_file() else None},
            'sets': {name: {'summary': data['summary'], 'baseline': data.get('baseline'),
                            'baseline_status': data['baseline_status'],
                            'records': data['records']} for name, data in sets.items()},
            'merge_diagnostic': merge_payload,
            'limitations': [
                'The check set was authored by the development agent from the corpus text; it is a fresh check set, not a blind holdout.',
                'The merge diagnostic fuses frozen D1 top10 lists; deploying dual-query retrieval needs an automatic query translator (D4 model decision) and is not deployed here.',
                'The default retrieval configuration is unchanged by this run; no rewrite, reranker, or index change is introduced.',
                'Unanswerable cases keep candidates with null hits and never enter the hit denominators.',
                'Anchor presence is not answer correctness; distances are not confidence.',
            ],
        }
        output.mkdir(parents=True)
        (output / 'results.json').write_text(
            json.dumps(payload, ensure_ascii=False, sort_keys=True, indent=1) + '\n', encoding='utf-8')
    except Exception as exc:
        print(json.dumps({'ok': False, 'error': {'code': type(exc).__name__, 'message': str(exc)}},
                         ensure_ascii=False))
        return 1
    summary_view = {name: {'summary': data['summary'], 'baseline_status': data['baseline_status']}
                    for name, data in sets.items()}
    print(json.dumps({'ok': True, 'output': str(output / 'results.json'),
                      'sets': summary_view,
                      'merge_diagnostic': {k: v for k, v in merge_payload.items() if k != 'records'}},
                     ensure_ascii=False, indent=1))
    return 0


def _split(cases, case_id):
    return next(c['split'] for c in cases if c['case_id'] == case_id)


if __name__ == '__main__':
    sys.exit(main())
