"""Conservative, deterministic section chunking for knowledge previews."""

from __future__ import annotations

import hashlib
import json
import re
from typing import Any, Iterable


STRATEGY = "h2-atomic-v2-merge-title-preamble"
SOFT_TARGET_TOKENS = 300
HARD_LIMIT_TOKENS = 512


class ChunkingError(ValueError):
    """Raised when a source section cannot safely fit the model input."""


_HEADING = re.compile(r"^##[ \t]+(.+?)[ \t]*#*[ \t]*(?:\n|$)")
_H1 = re.compile(r"^#[ \t]+(.+?)[ \t]*#*[ \t]*(?:\n|$)")
_FENCE = re.compile(r"^ {0,3}(`{3,}|~{3,})(.*?)(?:\n|$)")


def _h2_boundaries(body: str) -> list[tuple[int, str]]:
    boundaries: list[tuple[int, str]] = []
    offset = 0
    fence: tuple[str, int] | None = None
    for line in body.splitlines(keepends=True):
        fence_match = _FENCE.match(line)
        if fence_match:
            marker = fence_match.group(1)
            if fence is None:
                fence = (marker[0], len(marker))
            elif marker[0] == fence[0] and len(marker) >= fence[1] and not fence_match.group(2).strip():
                fence = None
        elif fence is None:
            heading = _HEADING.match(line)
            if heading:
                boundaries.append((offset, heading.group(1)))
        offset += len(line)
    return boundaries


def _preamble_section(body: str, fallback: str) -> str:
    for line in body.splitlines(keepends=True):
        match = _H1.match(line)
        if match:
            return match.group(1)
    return fallback


def _sections(body: str, title: str, document_id: str) -> Iterable[tuple[int, int, str]]:
    boundaries = _h2_boundaries(body)
    starts = [(0, _preamble_section(body, title))]
    if boundaries and boundaries[0][0] == 0:
        starts = []
    starts.extend(boundaries)
    if not starts and body:
        starts = [(0, title)]
    # Keep substantial introductions. Otherwise attach all leading title/blank
    # ranges to the first section with content, preserving one contiguous slice.
    first_content = None
    for index, (start, _) in enumerate(starts):
        end = starts[index + 1][0] if index + 1 < len(starts) else len(body)
        if any(line.strip() and not _H1.match(line) and not _HEADING.match(line)
               for line in body[start:end].splitlines(keepends=True)):
            first_content = index
            break
    if first_content is None:
        raise ChunkingError(f"{document_id} has no substantive body to chunk")
    if first_content:
        starts = [(0, starts[first_content][1]), *starts[first_content + 1:]]
    for index, (start, section) in enumerate(starts):
        end = starts[index + 1][0] if index + 1 < len(starts) else len(body)
        if start != end:
            yield start, end, section


def _embedding_text(metadata: dict[str, Any], section: str, original_text: str) -> str:
    devices = ", ".join(metadata["device_ids"])
    model = metadata["product_model"] if metadata["product_model"] is not None else "未注明"
    return (
        f"文档：{metadata['title']}\n"
        f"文档ID：{metadata['document_id']}\n"
        f"版本：{metadata['version']}\n"
        f"章节：{section}\n"
        f"适用设备：{devices}\n"
        f"产品型号：{model}\n"
        f"仅教学：{'是' if metadata['teaching_only'] else '否'}\n"
        f"正文：\n{original_text}"
    )


def _line_span(text: str, start: int, end: int) -> tuple[int, int]:
    line_start = text.count("\n", 0, start) + 1
    if end <= start:
        return line_start, line_start
    line_end = text.count("\n", 0, end - 1) + 1
    return line_start, line_end


def build_chunks(documents: list[dict[str, Any]], tokenizer: Any) -> list[dict[str, Any]]:
    """Keep substantive introductions and H2 sections; attach title-only prefixes."""

    chunks: list[dict[str, Any]] = []
    for document in documents:
        metadata = document["metadata"]
        body = document["body"]
        for relative_start, relative_end, section in _sections(body, metadata["title"], metadata["document_id"]):
            source_start = document["body_start"] + relative_start
            source_end = document["body_start"] + relative_end
            original_text = body[relative_start:relative_end]
            embedding_text = _embedding_text(metadata, section, original_text)
            token_count = len(tokenizer.encode(embedding_text, add_special_tokens=True))
            if token_count > HARD_LIMIT_TOKENS:
                raise ChunkingError(
                    f"{metadata['document_id']} section {section!r} has {token_count} tokens; "
                    f"complete embedding input exceeds hard limit {HARD_LIMIT_TOKENS}"
                )
            content_sha256 = hashlib.sha256(original_text.encode("utf-8")).hexdigest()
            digest_input = json.dumps(
                {
                    "metadata": metadata,
                    "strategy": STRATEGY,
                    "source_start": source_start,
                    "embedding_text": embedding_text,
                },
                ensure_ascii=False,
                sort_keys=True,
                separators=(",", ":"),
            ).encode("utf-8")
            chunk_id = f"{metadata['document_id']}:{hashlib.sha256(digest_input).hexdigest()[:20]}"
            source_line_start, source_line_end = _line_span(document["text"], source_start, source_end)
            chunks.append(
                {
                    "chunk_id": chunk_id,
                    "document_id": metadata["document_id"],
                    "version": metadata["version"],
                    "section": section,
                    "metadata": dict(metadata),
                    "source_path": document["source_path"],
                    "document_sha256": document["sha256"],
                    "content_sha256": content_sha256,
                    "source_start": source_start,
                    "source_end": source_end,
                    "source_line_start": source_line_start,
                    "source_line_end": source_line_end,
                    "original_text": original_text,
                    "embedding_text": embedding_text,
                    "token_count": token_count,
                    "over_soft_target": token_count > SOFT_TARGET_TOKENS,
                }
            )
    return chunks
