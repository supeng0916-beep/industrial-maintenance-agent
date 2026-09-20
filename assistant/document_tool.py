"""只读文档检索工具。候选是待核查证据，不构成诊断、正确性或适用性结论。

index_path 与 embedder 只在构造时注入；search() 对模型参数不开放路径，
不接受额外参数，错误沿用 {ok:false,error:{code,message}} 且不泄漏底层细节。
响应预算内只减少完整片段数量，绝不截断正文（数字表截断后不再是完整证据）。
"""
import os

from .contracts import QueryError
from .rag_index import search_index

REGISTERED_NAME = 'search_maintenance_docs'
DEFAULT_TOP_K = 5
MAX_TOP_K = 10
DEFAULT_TEXT_BUDGET = 12000
LIMITATIONS = [
    '候选不证明适用性或可回答性',
    '距离不作为置信度返回；适用型号未核实前，候选不代表适用于当前设备',
]


class MaintenanceDocumentTool:
    def __init__(self, index_path, embedder, text_budget=DEFAULT_TEXT_BUDGET):
        if not isinstance(index_path, (str, os.PathLike)) or not str(index_path).strip():
            raise ValueError('index_path must be a nonempty filesystem path')
        if not hasattr(embedder, 'embed') or not hasattr(embedder, 'signature'):
            raise ValueError('embedder must provide embed() and signature')
        if type(text_budget) is not int or text_budget < 1:
            raise ValueError('text_budget must be a positive integer')
        self._index_path = index_path
        self._embedder = embedder
        self._text_budget = text_budget
        self.name = REGISTERED_NAME

    def search(self, query, top_k=DEFAULT_TOP_K, document_id=None, **extra):
        try:
            if extra:
                raise QueryError('invalid_parameters',
                                 '不接受额外参数：' + '、'.join(sorted(extra)))
            if not isinstance(query, str) or not query.strip():
                raise QueryError('invalid_parameters', '问题必须为非空文本')
            if type(top_k) is not int or not 1 <= top_k <= MAX_TOP_K:
                raise QueryError('invalid_parameters', f'top_k必须为1～{MAX_TOP_K}的整数')
            if document_id is not None and (not isinstance(document_id, str)
                                            or not document_id.strip()):
                raise QueryError('invalid_parameters', 'document_id必须为非空文本')
            filters = None if document_id is None else {'document_id': document_id}
            result = search_index(self._index_path, query, self._embedder,
                                  top_k=top_k, filters=filters)
            return {'ok': True,
                    'data': self._within_budget(result['query'], result['candidates'])}
        except QueryError as exc:
            return {'ok': False, 'error': {'code': exc.code, 'message': exc.message}}
        except ValueError as exc:
            return {'ok': False, 'error': self._mapped_error(str(exc))}
        except Exception:
            return {'ok': False,
                    'error': {'code': 'retrieval_failed', 'message': '检索过程失败，请稍后重试'}}

    def _mapped_error(self, message):
        if 'unknown filter value' in message:
            return {'code': 'unknown_document_filter', 'message': '该document_id未在索引中收录'}
        if 'model signature mismatch' in message:
            return {'code': 'index_model_mismatch',
                    'message': '嵌入模型与索引签名不匹配，需改用匹配索引'}
        return {'code': 'index_unavailable', 'message': '文档索引不可用或校验失败'}

    def _within_budget(self, query, candidates):
        used, kept, omitted = 0, [], 0
        for rank, candidate in enumerate(candidates, 1):
            size = len(candidate['original_text']) + len(candidate.get('context_text') or '')
            # 至少返回一条完整候选；其余按整条丢弃，绝不截断正文。
            if kept and used + size > self._text_budget:
                omitted = len(candidates) - len(kept)
                break
            used += size
            kept.append(self._candidate(rank, candidate))
        data = {'query': query, 'candidates': kept, 'limitations': list(LIMITATIONS)}
        if omitted:
            data['omitted_candidates'] = omitted
            data['limitations'].append(
                f'为保持证据完整，另有{omitted}条候选因响应预算未返回；未截断任何文本')
        return data

    def _candidate(self, rank, candidate):
        metadata = candidate.get('metadata', {})
        # product_model 为空时保持缺失：不得推断为通用适用。
        return {'evidence_id': f'doc-{rank}',
                'document_id': candidate['document_id'],
                'chunk_id': candidate['chunk_id'],
                'version': candidate.get('version'),
                'section': candidate.get('section'),
                'source_pages': list(candidate.get('source_pages', [])),
                'source_url': metadata.get('source_url'),
                'original_text': candidate['original_text'],
                'context_text': candidate.get('context_text', ''),
                'applicability': metadata.get('applicability'),
                'product_model': metadata.get('product_model')}
