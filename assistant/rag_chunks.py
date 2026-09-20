"""Source-preserving RAG chunks; atomic tables/lists and sentence-only splitting.

This deliberately conservative Markdown parser refuses oversized atomic material.
Page markers are ``## Page N`` or ``## 第N页``. No model truncation is allowed.
"""
from __future__ import annotations

import hashlib
import json
import re
from typing import Any, Callable

from .knowledge_chunks import ChunkingError, _line_span

STRATEGY = 'rag-page-heading-sentence-v4'
HARD_LIMIT_TOKENS = 512
SOFT_TARGET_TOKENS = 300
_HEADING = re.compile(r'^(#{1,6})[ \t]+(.+?)\s*$')
_PAGE = re.compile(r'^(?:Page\s+(\d+)|第\s*(\d+)\s*页)$', re.I)
_ATOMIC = re.compile(r'^\s*(?:\||[-*+•–]\s|\d+[.)]\s|```|~~~)', re.M)


def _paragraph_blocks(body):
    """Yield exact paragraph ranges, keeping fenced code intact."""
    start = 0
    offset = 0
    fence = None
    for line in body.splitlines(keepends=True):
        stripped = line.strip()
        marker = re.match(r'^(`{3,}|~{3,})', stripped)
        if marker:
            token = marker.group(1)
            if fence is None:
                fence = token
            elif token[0] == fence[0] and len(token) >= len(fence):
                fence = None
        if fence is None and not stripped:
            if offset + len(line) > start:
                yield start, offset + len(line)
            start = offset + len(line)
        elif fence is None and _HEADING.match(stripped):
            if offset > start:
                yield start, offset
            yield offset, offset + len(line)
            start = offset + len(line)
        offset += len(line)
    if start < len(body):
        yield start, len(body)


def _blocks(body):
    """Attach immediately following table notes before any token splitting."""
    blocks = list(_paragraph_blocks(body))
    index = 0
    while index < len(blocks):
        start, end = blocks[index]
        is_table = bool(re.match(r'^\s*(?:\||```|~~~)', body[start:end]))
        if is_table:
            following = index + 1
            while following < len(blocks):
                a, b = blocks[following]
                text = body[a:b].strip()
                if not text:
                    following += 1
                    continue
                if not re.match(r'^(?:Notes?\s*[:.]|Source\s*:|\*(?!\s)|注[：:])', text, re.I):
                    break
                end = b
                index = following
                following += 1
        yield start, end
        index += 1


def _sentences(text):
    # Only unambiguous terminal punctuation. Decimal points and abbreviations
    # lacking a whitespace/capital transition are not used as split points.
    boundary = re.compile(r'[。！？][”’」』]?\s*|[!?]["\']?\s+|\.["\']?\s+(?=[A-Z])')
    start = 0
    for match in boundary.finditer(text):
        if match.group().startswith('.') and re.search(
            r'(?:\b(?:U\.S|U\.K|e\.g|i\.e|Mr|Mrs|Dr|Prof|No|Fig)|\b[A-Z])$',
            text[:match.start()], re.I,
        ):
            continue
        yield start, match.end()
        start = match.end()
    if start < len(text):
        yield start, len(text)


def _structural_split(raw):
    """Return exact safe subranges and source ranges to repeat, or refuse.

    Numeric table recognition is intentionally narrow: at least two complete
    numeric rows. Other code fences remain atomic unless explicitly ``text``.
    """
    lines = []
    offset = 0
    for line in raw.splitlines(keepends=True):
        lines.append((offset, offset + len(line), line))
        offset += len(line)
    numeric_rows = [(a, b, len(re.findall(r'[-+]?\d[\d,.]*%?', line)))
                    for a, b, line in lines
                    if re.fullmatch(r'[\s|+\-.,%()0-9]+', line)
                    and len(re.findall(r'[-+]?\d[\d,.]*%?', line)) >= 2]
    if len(numeric_rows) >= 2:
        widths = [width for _, _, width in numeric_rows]
        if len(set(widths)) == 1:
            data_rows = numeric_rows
        elif len(numeric_rows) >= 3 and len(set(widths[1:])) == 1 and widths[0] == widths[1] - 1:
            # A leading column-label row lacks the left-hand row-key cell.
            # Keep that entire numeric label row in the repeated header.
            data_rows = numeric_rows[1:]
        else:
            return None  # Mixed row widths cannot be interpreted safely.
        middle = raw[numeric_rows[0][0]:numeric_rows[-1][1]]
        header = raw[:numeric_rows[0][0]]
        if re.fullmatch(r'[\s|+\-.,%()0-9]+', middle) and re.search(r'[A-Za-z\u4e00-\u9fff]', header.replace('```text', '')):
            starts = [0] + [a for a, _, _ in data_rows[1:]]
            ends = starts[1:] + [len(raw)]
            repeats = [(0, data_rows[0][0]), (data_rows[-1][1], len(raw))]
            return list(zip(starts, ends)), repeats
        return None
    bullet = re.match(r'^\s*(?:[-*+•–]\s|\d+[.)]\s)', raw)
    if bullet:
        # Multiple items are not silently treated as one item's continuation.
        items = list(re.finditer(r'^\s*(?:[-*+•–]\s|\d+[.)]\s)', raw, re.M))
        if len(items) != 1:
            return None
        units = list(_sentences(raw))
        if len(units) > 1:
            return units, [(0, units[0][1])]
    fence = re.match(r'^\s*```text[ \t]*\n', raw)
    if fence:
        closing = raw.rfind('```')
        if closing > fence.end():
            interior = raw[fence.end():closing]
            # A title separated by a blank line establishes a prose callout.
            title_end = re.search(r'\n[ \t]*\n', interior)
            if title_end:
                prose_start = fence.end() + title_end.end()
                prose = list(_sentences(raw[prose_start:closing]))
                if len(prose) > 1:
                    boundaries = [prose_start + b for _, b in prose[:-1]]
                    starts = [0] + boundaries
                    ends = boundaries + [len(raw)]
                    return list(zip(starts, ends)), [(0, prose_start + prose[0][1])]
    return None


def build_rag_chunks(documents: list[dict[str, Any]], tokenizer: Any, *,
                     format_passage: Callable[[str], str] = lambda text: text) -> list[dict[str, Any]]:
    chunks = []
    for document in documents:
        metadata = document['metadata']
        body = document['body']
        if not body.strip() or not any(line.strip() and not _HEADING.match(line.strip()) for line in body.splitlines()):
            raise ChunkingError(f"{metadata['document_id']} has no substantive body")
        headings = []
        pages = list(metadata.get('source_pages', []))
        premises = {}
        page_title = ''
        page_level = 0
        previous = ('', [])
        previous_range = (0, 0)
        table_introduction = None
        pending_start = 0
        current = None

        def context(extra=('', [])):
            values = [metadata['title']]
            origins = []
            sources = [dict(text=metadata['title'], source_pages=[], kind='metadata', field='title')]
            scoped = [(h[1], h[2]) for h in headings] + list(premises.values()) + [extra]
            for value, source_pages in scoped:
                if value and value not in values:
                    values.append(value)
                    origins.extend(source_pages)
                    sources.append(dict(text=value, source_pages=list(source_pages), kind='source_context'))
            if metadata.get('applicability'):
                values.append('Applicability: '+metadata['applicability'])
                sources.append(dict(text=metadata['applicability'], source_pages=[], kind='metadata', field='applicability'))
            return ('Repeated source context:\n' + '\n'.join(values),
                    list(dict.fromkeys(origins)), sources)

        def formatted(start, end, ctx):
            text = format_passage(ctx+'\nSource text:\n'+body[start:end])
            return text, len(tokenizer.encode(text, add_special_tokens=True))

        def emit(item):
            if item is None:
                return
            start, end, ctx, section, item_pages, context_pages, context_sources = item
            embedding_text, token_count = formatted(start, end, ctx)
            source_start = document['body_start'] + start
            source_end = document['body_start'] + end
            original = body[start:end]
            digest = hashlib.sha256(json.dumps([STRATEGY, metadata, source_start, embedding_text], ensure_ascii=False, sort_keys=True).encode()).hexdigest()
            line_start, line_end = _line_span(document['text'], source_start, source_end)
            chunks.append(dict(chunk_id=f"{metadata['document_id']}:{digest[:20]}",
                document_id=metadata['document_id'], version=metadata['version'],
                section=section, metadata=dict(metadata), source_path=document['source_path'],
                document_sha256=document['sha256'], content_sha256=hashlib.sha256(original.encode()).hexdigest(),
                source_start=source_start, source_end=source_end, source_line_start=line_start,
                source_line_end=line_end, original_text=original, context_text=ctx,
                source_pages=item_pages, context_source_pages=context_pages, context_sources=context_sources, embedding_text=embedding_text, token_count=token_count,
                over_soft_target=token_count > SOFT_TARGET_TOKENS, strategy=STRATEGY))

        for start, end in _blocks(body):
            raw = body[start:end]
            heading = _HEADING.match(raw.strip())
            if heading:
                emit(current)
                current = None
                table_introduction = None
                level, title = len(heading.group(1)), heading.group(2)
                page = _PAGE.match(title)
                if page:
                    pages = [page.group(1) or page.group(2)]
                    page_title, page_level = title, level
                    headings = [h for h in headings if h[0] < level]
                    premises = {}  # Inferred local conditions never cross physical pages.
                    previous = ('', [])
                else:
                    headings = [h for h in headings if h[0] < level] + [(level, title, [] if level == 1 else list(pages))]
                    premises = {depth: value for depth, value in premises.items() if depth < level}
                    previous = ('', [])
                continue
            if not raw.strip():
                if current:
                    candidate = (current[0], end, *current[2:])
                    if formatted(candidate[0], candidate[1], candidate[2])[1] <= HARD_LIMIT_TOKENS:
                        current = candidate
                        pending_start = end
                continue
            atomic = bool(_ATOMIC.search(raw))
            table_caption = re.match(r'^Table\s+(\d+)[.:]', raw.strip(), re.I)
            if not atomic:
                table_introduction = None
                if table_caption and re.search(
                    rf'\b(?:Table\s+{table_caption.group(1)}\b|table\s+below\b)', previous[0], re.I
                ):
                    intro_start, intro_end = previous_range
                    table_introduction = dict(
                        text=body[intro_start:intro_end], source_pages=list(previous[1]), kind='source_context',
                        source_start=document['body_start'] + intro_start,
                        source_end=document['body_start'] + intro_end,
                    )

            caption = previous if (previous[0].rstrip().endswith(':') or re.match(
                r'^(?:Table\s+\d|Figure\s+\d|表\s*\d|Scope:|Applicability:)', previous[0], re.I
            )) else ('', [])
            ctx, context_pages, context_sources = context(caption if atomic else ('', []))
            if atomic and table_introduction is not None:
                ctx += '\n' + table_introduction['text']
                context_sources.append(dict(table_introduction))
                context_pages = list(dict.fromkeys(context_pages + table_introduction['source_pages']))
            section = (headings[-1][1] if headings and headings[-1][0] > page_level
                       else page_title or metadata['title'])
            units = [(0, len(raw))] if atomic else list(_sentences(raw))
            if atomic and formatted(pending_start, end, ctx)[1] > HARD_LIMIT_TOKENS:
                split = _structural_split(raw)
                if split is not None:
                    units, repeat_ranges = split
                    for a, b in repeat_ranges:
                        repeated = raw[a:b]
                        if repeated.strip() and repeated.strip() not in ctx:
                            ctx += '\n' + repeated
                            context_sources.append(dict(
                                text=repeated, source_pages=list(pages), kind='source_context',
                                source_start=document['body_start'] + start + a,
                                source_end=document['body_start'] + start + b,
                            ))
                            context_pages = list(dict.fromkeys(context_pages + pages))

            for a, b in units:
                unit_end = start+b
                if current and current[2] == ctx:
                    candidate = (current[0], unit_end, ctx, section, list(pages), context_pages, context_sources)
                    if formatted(candidate[0], candidate[1], ctx)[1] <= HARD_LIMIT_TOKENS:
                        current = candidate
                        pending_start = unit_end
                        continue
                emit(current)
                current = None
                candidate = (pending_start, unit_end, ctx, section, list(pages), context_pages, context_sources)
                count = formatted(candidate[0], candidate[1], ctx)[1]
                if count > HARD_LIMIT_TOKENS:
                    raise ChunkingError(f"{metadata['document_id']} section {section!r}: atomic unit plus repeated context has {count} tokens; hard limit 512")
                current = candidate
                pending_start = unit_end
            if not atomic:
                previous = (raw.strip(), list(pages))
                previous_range = (start, end)
                depth = headings[-1][0] if headings else 0
                scope_label = r'^(?:Scope|Applicability|适用范围|前提)(?:\s*[:：]|$)'
                explicit_scope = re.match(scope_label, raw.strip(), re.I) or (
                    headings and re.match(scope_label, headings[-1][1], re.I)
                )
                if explicit_scope:
                    prior_text, prior_pages = premises.get(depth, ('', []))
                    scope_text = prior_text + ('\n\n' if prior_text else '') + raw.strip()
                    premises[depth] = (scope_text, list(dict.fromkeys(prior_pages + pages)))
            else:
                table_introduction = None
                if re.match(r'^\s*(?:\||```|~~~)', raw):
                    previous = ('', [])
        if pending_start < len(body):
            # A trailing heading/whitespace still belongs to the exact source.
            ctx, context_pages, context_sources = (current[2], current[5], current[6]) if current else context()
            start = current[0] if current else pending_start
            if formatted(start, len(body), ctx)[1] > HARD_LIMIT_TOKENS:
                raise ChunkingError(f"{metadata['document_id']}: trailing source exceeds hard limit 512")
            current = (start, len(body), ctx, headings[-1][1] if headings else metadata['title'], list(pages), context_pages, context_sources)
        emit(current)
    return chunks
