"""Generate a local, traceable chunk preview; no embedding or retrieval."""
import argparse
import json
import os
import re
from pathlib import Path
import shutil
import tempfile

from .knowledge_tokenizer import DEFAULT_CACHE, load_tokenizer


def check_coverage(documents, chunks):
    """Validate exact source slices and the union of body character offsets."""
    coverage = []
    known = {d['metadata']['document_id'] for d in documents}
    if any(c['document_id'] not in known for c in chunks):
        raise ValueError('coverage: unknown document')
    for doc in documents:
        doc_id = doc['metadata']['document_id']
        cursor = doc['body_start']
        covered = 0
        selected = sorted((c for c in chunks if c['document_id'] == doc_id), key=lambda c: c['source_start'])
        for chunk in selected:
            start, end = chunk['source_start'], chunk['source_end']
            if not doc['body_start'] <= start < end <= len(doc['text']):
                raise ValueError(f'coverage: invalid range in {doc_id}')
            if doc['text'][start:end] != chunk['original_text'] or start > cursor:
                raise ValueError(f'coverage: changed text or gap in {doc_id}')
            covered += max(0, end - cursor)
            cursor = max(cursor, end)
        if cursor != len(doc['text']):
            raise ValueError(f'coverage: missing body in {doc_id}')
        coverage.append(dict(document_id=doc_id, source_path=doc['source_path'], sha256=doc['sha256'],
                             body_characters=len(doc['body']), covered_characters=covered, complete=True))
    return coverage


def render_markdown(chunks):
    lines = ['# 文档切块预览', '', '仅结构与长度预览，未生成向量、未建立索引、未评测检索。', '']
    for chunk in chunks:
        lines.extend([f"## {chunk['document_id']} · {chunk['section']}", '',
                      f"chunk_id: `{chunk['chunk_id']}`", '',
                      f"来源：{chunk['source_path']}，行 {chunk['source_line_start']}–{chunk['source_line_end']}；字符 [{chunk['source_start']}, {chunk['source_end']})", '',
                      f"完整输入 tokens：{chunk['token_count']}；超过300软目标：{chunk['over_soft_target']}", ''])
        for title, text in [('元数据', json.dumps(chunk['metadata'], ensure_ascii=False, indent=2)),
                            ('原文（不含元数据前缀）', chunk['original_text']),
                            ('embedding_text（标题、适用范围前缀＋原文）', chunk['embedding_text'])]:
            fence = '`' * max(3, max((len(x) for x in re.findall(r'`+', text)), default=0) + 1)
            lines.extend([f'### {title}', '', fence, text, fence, ''])
    return '\n'.join(lines)


def publish_preview(output, chunks, report):
    """Reserve a new destination exclusively; publish success report last."""
    output = Path(output)
    if output.exists() or output.is_symlink():
        raise FileExistsError(f'output already exists; choose a new directory: {output}')
    output.parent.mkdir(parents=True, exist_ok=True)
    stage = Path(tempfile.mkdtemp(prefix='.knowledge-preview-', dir=output.parent))
    reserved = False
    try:
        (stage/'chunks.json').write_text(json.dumps(chunks, ensure_ascii=False, indent=2)+'\n', encoding='utf-8')
        (stage/'preview.md').write_text(render_markdown(chunks), encoding='utf-8')
        (stage/'report.json').write_text(json.dumps(report, ensure_ascii=False, indent=2)+'\n', encoding='utf-8')
        output.mkdir()  # Never replace an existing output, including a concurrent run.
        reserved = True
        for name in ('chunks.json', 'preview.md', 'report.json'):
            os.replace(stage/name, output/name)
    except BaseException:
        if reserved: shutil.rmtree(output)
        raise
    finally:
        shutil.rmtree(stage)


def generate_preview(manifest, output, tokenizer):
    from .knowledge_documents import load_documents
    from .knowledge_chunks import build_chunks, STRATEGY
    manifest, output = Path(manifest).resolve(), Path(output).resolve()
    if output.is_relative_to(manifest.parent):
        raise ValueError('output must be outside the source corpus directory')
    if output.exists():
        raise FileExistsError(f'output already exists: {output}')
    documents = load_documents(manifest)
    chunks = build_chunks(documents, tokenizer)
    coverage = check_coverage(documents, chunks)
    # Count independently at the publishing boundary, never silently truncate.
    for chunk in chunks:
        actual = len(tokenizer.encode(chunk['embedding_text'], add_special_tokens=True))
        if actual != chunk['token_count'] or actual > 512:
            raise ValueError(f"token count invalid: {chunk['chunk_id']}: {actual}")
    report = dict(ok=True, stage='chunk_preview_not_indexed',
                  strategy=STRATEGY, soft_target=300, hard_limit=512, overlap_target=40,
                  overlap_applied=False, overlap_reason='Whole sections retained; unsafe oversized sections fail explicitly.',
                  tokenizer=tokenizer.info, documents=coverage, document_count=len(documents),
                  chunk_count=len(chunks), max_token_count=max((c['token_count'] for c in chunks), default=0),
                  over_soft_target=[c['chunk_id'] for c in chunks if c['over_soft_target']],
                  coverage_complete=all(d['complete'] for d in coverage),
                  evaluation_imported=False, retrieval_evaluated=False)
    publish_preview(output, chunks, report)
    return report


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--manifest', type=Path, default=Path('docs/knowledge/manifest.json'))
    parser.add_argument('--output', type=Path, required=True, help='New directory; existing outputs are never overwritten')
    parser.add_argument('--tokenizer-cache', type=Path, default=DEFAULT_CACHE)
    parser.add_argument('--download-tokenizer', action='store_true')
    args = parser.parse_args()
    try:
        if args.output.exists() or args.output.is_symlink():
            raise FileExistsError(f'output already exists: {args.output}')
        tokenizer = load_tokenizer(args.tokenizer_cache, download=args.download_tokenizer)
        report = generate_preview(args.manifest, args.output, tokenizer)
    except (ValueError, OSError) as exc:
        print(json.dumps(dict(ok=False, error=str(exc)), ensure_ascii=False))
        return 1
    print(json.dumps(dict(ok=True, output=str(args.output), chunks=report['chunk_count'], max_tokens=report['max_token_count']), ensure_ascii=False))
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
