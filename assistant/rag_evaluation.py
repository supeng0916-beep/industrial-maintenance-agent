"""Retrieval-only evidence scoring. Questions and anchors never enter the index."""
import hashlib
import json
from pathlib import Path
import time
import unicodedata
from .rag_index import search_index, read_index


def normalize(text):
    return ' '.join(unicodedata.normalize('NFKC', text).casefold().split())


def load_cases(path):
    cases = json.loads(Path(path).read_text(encoding='utf-8'))
    if not isinstance(cases, list) or not cases:
        raise ValueError('evaluation must be a nonempty JSON list')
    seen = set()
    for case in cases:
        required = {'case_id','question','split','answerable','expected_document_ids','expected_sections','required_evidence','forbidden_claims','category'}
        if not isinstance(case,dict) or not required <= case.keys():
            raise ValueError('evaluation case missing required fields')
        for key in ('case_id','question','category'):
            if not isinstance(case[key],str) or not case[key].strip(): raise ValueError(f'invalid {key}')
        if case['case_id'] in seen or case['split'] not in ('dev','holdout') or type(case['answerable']) is not bool:
            raise ValueError('duplicate case or invalid split/answerable')
        seen.add(case['case_id'])
        for key in ('expected_document_ids','expected_sections','required_evidence','forbidden_claims'):
            if not isinstance(case[key],list) or any(not isinstance(v,str) for v in case[key]):
                raise ValueError(f'invalid {key}')
        if case['answerable'] and not case['expected_document_ids']:
            raise ValueError('answerable case must identify source documents')
        if 'expected_evidence' in case:
            if not isinstance(case['expected_evidence'],list):raise ValueError('invalid expected_evidence')
            for evidence in case['expected_evidence']:
                if not isinstance(evidence,dict) or not {'document_id','source_page','anchors','match'} <= evidence.keys():
                    raise ValueError('invalid evidence schema')
                if any(not isinstance(evidence[k],str) or not evidence[k] for k in ('document_id','source_page')):
                    raise ValueError('evidence document and page must be strings')
                if evidence['match'] not in ('any','all') or not isinstance(evidence['anchors'],list) or not evidence['anchors'] or any(not isinstance(v,str) or not v.strip() for v in evidence['anchors']):
                    raise ValueError('invalid evidence anchors/match')
            if case['answerable'] and not case['expected_evidence']:
                raise ValueError('answerable evidence list cannot be empty')
    return cases


def score_evidence(case, candidates):
    if 'expected_evidence' not in case:
        return [any(c['document_id'] in case['expected_document_ids'] and
                    (not case['expected_sections'] or c['section'] in case['expected_sections']) for c in candidates)]
    found = []
    for evidence in case['expected_evidence']:
        hit = False
        for c in candidates:
            if c['document_id'] != evidence['document_id']:
                continue
            page=evidence['source_page']
            texts=[c['original_text']] if page in c['source_pages'] else []
            if 'context_sources' in c:
                texts.extend(source['text'] for source in c['context_sources'] if page in source['source_pages'])
            elif page in c['source_pages']:
                texts.append(c.get('context_text',''))
            text = normalize('\n'.join(texts))
            matches = [normalize(anchor) in text for anchor in evidence['anchors']]
            if (all(matches) if evidence['match']=='all' else any(matches)):
                hit=True;break
        found.append(hit)
    return found


def evaluate_index(index, cases_path, embedder):
    cases=load_cases(cases_path)
    index_config,_=read_index(index)
    results=[]
    for case in cases:
        started=time.monotonic()
        result=search_index(index,case['question'],embedder,top_k=10)
        item=dict(case=case, candidates_top10=result['candidates'], candidates_top5=result['candidates'][:5],
                  elapsed_seconds=time.monotonic()-started, manual_relevance='not_reviewed',
                  answer_correctness='not_evaluated_no_LLM')
        for k in (5,10):
            evidence=score_evidence(case,result['candidates'][:k]) if case['answerable'] else None
            item[f'evidence_matches_at_{k}']=evidence
            item[f'hit_at_{k}']=any(evidence) if evidence is not None else None
            item[f'all_annotated_evidence_at_{k}']=all(evidence) if evidence else None
        results.append(item)
    summaries={}
    for split in ('dev','holdout'):
        subset=[r for r in results if r['case']['split']==split]
        answerable=[r for r in subset if r['case']['answerable']]
        summary=dict(cases=len(subset),answerable=len(answerable),unanswerable=len(subset)-len(answerable))
        for k in (5,10):
            summary[f'hit_at_{k}']=sum(r[f'hit_at_{k}'] for r in answerable)/len(answerable) if answerable else None
            summary[f'all_annotated_evidence_at_{k}']=sum(bool(r[f'all_annotated_evidence_at_{k}']) for r in answerable)/len(answerable) if answerable else None
        summaries[split]=summary
    return dict(ok=True,stage='retrieval_only',model_signature=embedder.signature,
                index_corpus=index_config['corpus'],index_chunks_sha256=index_config['chunks_sha256'],
                cases_sha256=hashlib.sha256(Path(cases_path).read_bytes()).hexdigest(),
                scoring='NFKC + casefold + whitespace; document/page/anchor evidence when annotated',
                summaries=summaries,results=results,holdout_now_observed=True,
                limitations=['Anchor presence is not a semantic answer or full applicability judgment.',
                             'No automatic no-answer threshold or answer correctness evaluation.',
                             'Both models use the same corpus/questions; model-tokenizer chunk boundaries may differ.',
                             'This holdout has now been observed; future tuning needs fresh holdout cases.'])
