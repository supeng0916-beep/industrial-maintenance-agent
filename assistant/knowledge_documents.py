"""Restricted, validated loading for the teaching knowledge corpus."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any

import yaml


class DocumentError(ValueError):
    """Raised when a manifest entry or knowledge document is invalid."""


_METADATA_FIELDS = {
    "document_id",
    "title",
    "version",
    "reviewed_on",
    "teaching_only",
    "device_ids",
    "product_model",
    "sources",
    "authoring",
}
_REQUIRED_METADATA_FIELDS = set(_METADATA_FIELDS)
_OPTIONAL_STRING_FIELDS = {
    "language", "source_url", "publisher", "source_document_id",
    "applicability", "license", "source_sha256",
}
_METADATA_FIELDS |= _OPTIONAL_STRING_FIELDS | {"source_pages"}


class _UniqueSafeLoader(yaml.SafeLoader):
    pass


def _construct_unique_mapping(loader: yaml.SafeLoader, node: yaml.MappingNode, deep: bool = False):
    mapping: dict[Any, Any] = {}
    for key_node, value_node in node.value:
        key = loader.construct_object(key_node, deep=deep)
        try:
            duplicate = key in mapping
        except TypeError as exc:
            raise DocumentError("YAML mapping keys must be scalar") from exc
        if duplicate:
            raise DocumentError(f"duplicate YAML key: {key!r}")
        try:
            mapping[key] = loader.construct_object(value_node, deep=deep)
        except TypeError as exc:
            raise DocumentError("YAML mapping keys must be scalar") from exc
    return mapping


_UniqueSafeLoader.add_constructor(
    yaml.resolver.BaseResolver.DEFAULT_MAPPING_TAG,
    _construct_unique_mapping,
)


def _load_metadata(raw: str, source_path: str) -> dict[str, Any]:
    try:
        metadata = yaml.load(raw, Loader=_UniqueSafeLoader)
    except (yaml.YAMLError, DocumentError) as exc:
        raise DocumentError(f"invalid frontmatter in {source_path}: {exc}") from exc
    if not isinstance(metadata, dict):
        raise DocumentError(f"frontmatter in {source_path} must be a mapping")
    if any(not isinstance(key, str) for key in metadata):
        raise DocumentError(f"frontmatter keys in {source_path} must be strings")
    keys = set(metadata)
    if not _REQUIRED_METADATA_FIELDS <= keys or keys - _METADATA_FIELDS:
        missing = sorted(_REQUIRED_METADATA_FIELDS - keys)
        extra = sorted(keys - _METADATA_FIELDS)
        raise DocumentError(f"unsupported frontmatter fields in {source_path}: missing={missing}, extra={extra}")

    scalar_strings = ("document_id", "title", "version", "reviewed_on", "authoring")
    for key in (*scalar_strings, *sorted(_OPTIONAL_STRING_FIELDS & keys)):
        if not isinstance(metadata[key], str) or not metadata[key]:
            raise DocumentError(f"frontmatter {key} in {source_path} must be a non-empty string")
    if type(metadata["teaching_only"]) is not bool:
        raise DocumentError(f"frontmatter teaching_only in {source_path} must be boolean")
    if metadata["product_model"] is not None and not isinstance(metadata["product_model"], str):
        raise DocumentError(f"frontmatter product_model in {source_path} must be string or null")
    for key in ("device_ids", "sources", *(["source_pages"] if "source_pages" in keys else [])):
        value = metadata[key]
        if not isinstance(value, list) or any(not isinstance(item, str) or not item for item in value):
            raise DocumentError(f"frontmatter {key} in {source_path} must be a list of strings")
    return metadata


def _split_frontmatter(text: str, source_path: str) -> tuple[dict[str, Any], int, str]:
    if not text.startswith("---\n"):
        raise DocumentError(f"missing YAML frontmatter in {source_path}")
    closing = text.find("\n---\n", 4)
    if closing < 0:
        raise DocumentError(f"unterminated YAML frontmatter in {source_path}")
    body_start = closing + len("\n---\n")
    return _load_metadata(text[4:closing], source_path), body_start, text[body_start:]


def load_documents(manifest_path: str | Path) -> list[dict[str, Any]]:
    """Load only manifest-listed Markdown files after validating identity and hashes."""

    manifest_path = Path(manifest_path)
    try:
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError) as exc:
        raise DocumentError(f"cannot read manifest {manifest_path}: {exc}") from exc
    entries = manifest.get("documents") if isinstance(manifest, dict) else None
    if not isinstance(entries, list):
        raise DocumentError("manifest documents must be a list")

    root = manifest_path.parent.resolve()
    seen_ids: set[str] = set()
    documents: list[dict[str, Any]] = []
    for index, entry in enumerate(entries):
        if not isinstance(entry, dict) or set(entry) != {"document_id", "path", "version", "sha256"}:
            raise DocumentError(f"manifest document {index} has unsupported structure")
        if any(not isinstance(entry[key], str) or not entry[key] for key in entry):
            raise DocumentError(f"manifest document {index} fields must be non-empty strings")
        document_id = entry["document_id"]
        if document_id in seen_ids:
            raise DocumentError(f"duplicate document_id: {document_id}")
        seen_ids.add(document_id)

        relative_path = Path(entry["path"])
        if relative_path.suffix != ".md":
            raise DocumentError(f"document path must have .md extension: {entry['path']}")
        resolved = (root / relative_path).resolve()
        if relative_path.is_absolute() or not resolved.is_relative_to(root):
            raise DocumentError(f"document path escapes manifest directory: {entry['path']}")
        try:
            raw = resolved.read_bytes()
            text = raw.decode("utf-8")
        except (OSError, UnicodeError) as exc:
            raise DocumentError(f"cannot read document {entry['path']}: {exc}") from exc
        actual_hash = hashlib.sha256(raw).hexdigest()
        if actual_hash != entry["sha256"]:
            raise DocumentError(f"sha256 mismatch for {entry['path']}")

        metadata, body_start, body = _split_frontmatter(text, entry["path"])
        if metadata["document_id"] != document_id or metadata["version"] != entry["version"]:
            raise DocumentError(f"manifest/frontmatter identity mismatch for {entry['path']}")
        documents.append(
            {
                "metadata": metadata,
                "source_path": entry["path"],
                "sha256": actual_hash,
                "text": text,
                "body_start": body_start,
                "body": body,
            }
        )
    return documents
