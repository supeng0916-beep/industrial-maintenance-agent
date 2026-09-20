"""D6 证据引用校验：模型引用的证据标识必须存在于本轮工具结果中。

程序只保证"引用的ID真实存在"；引用存在不代表语义支持（D9人工核查）。
编造的ID一律剔除并向用户说明，绝不静默保留。
"""


def collect_valid_citation_ids(evidence):
    """本轮可引用的标识：证据条目ev-N与文档候选doc-N。"""
    valid = set()
    for entry in evidence or []:
        eid = entry.get('evidence_id')
        if isinstance(eid, str):
            valid.add(eid)
        for candidate in entry.get('candidates', []) or []:
            cid = candidate.get('evidence_id')
            if isinstance(cid, str):
                valid.add(cid)
    return valid


def validate_citations(citations, evidence):
    """返回(保留的引用, 编造的引用)。非字符串项直接丢弃。"""
    valid = collect_valid_citation_ids(evidence)
    kept, fabricated = [], []
    for item in citations or []:
        if not isinstance(item, str):
            continue
        (kept if item in valid else fabricated).append(item)
    return kept, fabricated
