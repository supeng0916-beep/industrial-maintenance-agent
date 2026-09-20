import hashlib
import json
from pathlib import Path
import tempfile
import unittest

from assistant.knowledge_chunks import ChunkingError, build_chunks
from assistant.knowledge_documents import DocumentError, load_documents


FRONTMATTER = """---
document_id: "doc-1"
title: "测试文档"
version: "1.0"
reviewed_on: "2026-09-18"
teaching_only: true
device_ids: ["motor-a"]
product_model: null
sources: ["source.md"]
authoring: "checked"
---
"""


class CharacterTokenizer:
    def encode(self, text, add_special_tokens=True):
        return ([101] if add_special_tokens else []) + list(range(len(text))) + (
            [102] if add_special_tokens else []
        )


def _write_manifest(tmp_path: Path, body: str, **entry_overrides) -> Path:
    document = tmp_path / "doc.md"
    document.write_text(FRONTMATTER + body, encoding="utf-8")
    entry = {
        "document_id": "doc-1",
        "path": "doc.md",
        "version": "1.0",
        "sha256": hashlib.sha256(document.read_bytes()).hexdigest(),
    }
    entry.update(entry_overrides)
    manifest = tmp_path / "manifest.json"
    manifest.write_text(json.dumps({"documents": [entry]}), encoding="utf-8")
    return manifest


class KnowledgeDocumentTests(unittest.TestCase):
    def setUp(self):
        self.temporary_directory = tempfile.TemporaryDirectory()
        self.tmp_path = Path(self.temporary_directory.name)

    def tearDown(self):
        self.temporary_directory.cleanup()

    def test_loads_only_manifest_entries_and_preserves_null_model(self):
        manifest = _write_manifest(self.tmp_path, "\n# 标题\n\n正文\n")
        (self.tmp_path / "unlisted.md").write_text(FRONTMATTER + "秘密", encoding="utf-8")

        documents = load_documents(manifest)

        self.assertEqual(len(documents), 1)
        self.assertEqual(documents[0]["source_path"], "doc.md")
        self.assertIsNone(documents[0]["metadata"]["product_model"])
        self.assertEqual(documents[0]["body"], "\n# 标题\n\n正文\n")
        self.assertEqual(documents[0]["text"][documents[0]["body_start"] :], documents[0]["body"])

    def test_rejects_untrusted_manifest_entries(self):
        for fault in ("hash", "duplicate", "escape"):
            with self.subTest(fault=fault), tempfile.TemporaryDirectory() as directory:
                tmp_path = Path(directory)
                manifest = _write_manifest(tmp_path, "正文")
                data = json.loads(manifest.read_text(encoding="utf-8"))
                if fault == "hash":
                    data["documents"][0]["sha256"] = "0" * 64
                elif fault == "duplicate":
                    data["documents"].append(dict(data["documents"][0]))
                else:
                    outside = tmp_path.parent / (tmp_path.name + "-outside.md")
                    outside.write_text(FRONTMATTER + "outside", encoding="utf-8")
                    self.addCleanup(outside.unlink, missing_ok=True)
                    data["documents"][0]["path"] = "../" + outside.name
                    data["documents"][0]["sha256"] = hashlib.sha256(outside.read_bytes()).hexdigest()
                manifest.write_text(json.dumps(data), encoding="utf-8")

                with self.assertRaises(DocumentError):
                    load_documents(manifest)

    def test_rejects_unsafe_duplicate_or_nested_frontmatter(self):
        frontmatters = [
            FRONTMATTER.replace('title: "测试文档"', 'title: !!python/object/apply:os.system ["false"]'),
            FRONTMATTER.replace('title: "测试文档"', 'title: "甲"\ntitle: "乙"'),
            FRONTMATTER.replace('authoring: "checked"', 'authoring:\n  nested: true'),
            "---\n1: value\nextra: value\n---\n",
        ]
        for frontmatter in frontmatters:
            with self.subTest(frontmatter=frontmatter), tempfile.TemporaryDirectory() as directory:
                tmp_path = Path(directory)
                document = tmp_path / "doc.md"
                document.write_text(frontmatter + "正文", encoding="utf-8")
                manifest = tmp_path / "manifest.json"
                manifest.write_text(json.dumps({"documents": [{"document_id": "doc-1", "path": "doc.md", "version": "1.0", "sha256": hashlib.sha256(document.read_bytes()).hexdigest()}]}), encoding="utf-8")

                with self.assertRaises(DocumentError):
                    load_documents(manifest)

    def test_rejects_non_markdown_path_and_unhashable_yaml_key(self):
        manifest = _write_manifest(self.tmp_path, "正文", path="doc.txt")
        (self.tmp_path / "doc.md").rename(self.tmp_path / "doc.txt")
        data = json.loads(manifest.read_text(encoding="utf-8"))
        data["documents"][0]["sha256"] = hashlib.sha256((self.tmp_path / "doc.txt").read_bytes()).hexdigest()
        manifest.write_text(json.dumps(data), encoding="utf-8")
        with self.assertRaises(DocumentError):
            load_documents(manifest)

        document = self.tmp_path / "doc.md"
        unsafe = FRONTMATTER.replace('title: "测试文档"', '? [unhashable]\n: value') + "正文"
        document.write_text(unsafe, encoding="utf-8")
        data["documents"][0].update(path="doc.md", sha256=hashlib.sha256(document.read_bytes()).hexdigest())
        manifest.write_text(json.dumps(data), encoding="utf-8")
        with self.assertRaises(DocumentError):
            load_documents(manifest)


class KnowledgeChunkTests(unittest.TestCase):
    def setUp(self):
        self.temporary_directory = tempfile.TemporaryDirectory()
        self.tmp_path = Path(self.temporary_directory.name)

    def tearDown(self):
        self.temporary_directory.cleanup()

    def test_chunks_preserve_sections_tables_code_and_exact_body_coverage(self):
        body = (
        "\n# 标题\n\n导言。\n"
        "\n## 条件与规则\n\n前提：有效。\n\n| 条件 | 限制 |\n| --- | --- |\n| 高温 | 不截断 |\n"
        "\n```python\nvalue = '## 不是标题'\n```\n"
        "\n## 后续章节\n\n尾句。\n"
    )
        documents = load_documents(_write_manifest(self.tmp_path, body))

        chunks = build_chunks(documents, CharacterTokenizer())

        self.assertEqual([chunk["section"] for chunk in chunks], ["标题", "条件与规则", "后续章节"])
        self.assertIn("| 条件 | 限制 |", chunks[1]["original_text"])
        self.assertIn("```python\nvalue = '## 不是标题'\n```", chunks[1]["original_text"])
        self.assertIn("前提：有效。", chunks[1]["embedding_text"])
        self.assertIn("不截断", chunks[1]["embedding_text"])
        self.assertNotIn("后续章节", chunks[1]["original_text"])
        self.assertEqual("".join(chunk["original_text"] for chunk in chunks), body)
        for chunk in chunks:
            self.assertEqual(documents[0]["text"][chunk["source_start"] : chunk["source_end"]], chunk["original_text"])
            self.assertEqual(chunk["token_count"], len(
            CharacterTokenizer().encode(chunk["embedding_text"], add_special_tokens=True)
            ))


    def test_chunk_ids_are_stable_and_depend_on_content_and_version(self):
        tokenizer = CharacterTokenizer()
        first = load_documents(_write_manifest(self.tmp_path, "\n# 标题\n\n正文甲\n"))
        ids_once = [chunk["chunk_id"] for chunk in build_chunks(first, tokenizer)]
        self.assertEqual(ids_once, [chunk["chunk_id"] for chunk in build_chunks(first, tokenizer)])

        changed_content = [dict(first[0], body="\n# 标题\n\n正文乙\n", text=first[0]["text"].replace("正文甲", "正文乙"))]
        changed_version = [dict(first[0], metadata=dict(first[0]["metadata"], version="2.0"))]

        self.assertNotEqual(ids_once, [chunk["chunk_id"] for chunk in build_chunks(changed_content, tokenizer)])
        self.assertNotEqual(ids_once, [chunk["chunk_id"] for chunk in build_chunks(changed_version, tokenizer)])

        changed_title = [dict(first[0], metadata=dict(first[0]["metadata"], title="另一标题"))]
        self.assertNotEqual(ids_once, [chunk["chunk_id"] for chunk in build_chunks(changed_title, tokenizer)])

    def test_identical_repeated_sections_have_distinct_ids(self):
        repeated = "\n## 重复\n\n相同正文\n\n## 重复\n\n相同正文\n"
        documents = load_documents(_write_manifest(self.tmp_path, repeated))

        chunks = build_chunks(documents, CharacterTokenizer())

        repeated_chunks = [chunk for chunk in chunks if chunk["section"] == "重复"]
        self.assertEqual(len(repeated_chunks), 2)
        self.assertNotEqual(repeated_chunks[0]["chunk_id"], repeated_chunks[1]["chunk_id"])

    def test_long_fence_is_not_closed_by_short_or_trailed_fence(self):
        body = "\n# 标题\n\n````python\n```\n## 代码内\n````\n\n## 真章节\n正文\n"
        documents = load_documents(_write_manifest(self.tmp_path, body))

        chunks = build_chunks(documents, CharacterTokenizer())

        self.assertEqual([chunk["section"] for chunk in chunks], ["标题", "真章节"])
        self.assertIn("## 代码内", chunks[0]["original_text"])

    def test_embedding_input_marks_teaching_only_scope(self):
        documents = load_documents(_write_manifest(self.tmp_path, "\n# 标题\n正文\n"))

        chunk = build_chunks(documents, CharacterTokenizer())[0]

        self.assertIn("仅教学：是", chunk["embedding_text"])

    def test_chunks_expose_source_and_content_hashes(self):
        documents = load_documents(_write_manifest(self.tmp_path, "\n# 标题\n正文\n"))

        chunk = build_chunks(documents, CharacterTokenizer())[0]

        self.assertEqual(chunk["document_sha256"], documents[0]["sha256"])
        self.assertEqual(
            chunk["content_sha256"],
            hashlib.sha256(chunk["original_text"].encode("utf-8")).hexdigest(),
        )


    def test_rejects_complete_embedding_input_over_hard_limit_without_truncating(self):
        documents = load_documents(_write_manifest(self.tmp_path, "\n# 标题\n\n" + "长" * 600 + "尾句"))

        with self.assertRaisesRegex(ChunkingError, r"doc-1.*标题.*512"):
            build_chunks(documents, CharacterTokenizer())


    def test_marks_atomic_section_above_soft_target(self):
    # Metadata/prefix contributes to the complete input length, so 240 body chars
    # crosses the 300-token target while remaining below the 512-token hard limit.
        documents = load_documents(_write_manifest(self.tmp_path, "\n# 标题\n\n" + "中" * 240))

        chunk = build_chunks(documents, CharacterTokenizer())[0]

        self.assertTrue(300 < chunk["token_count"] <= 512)
        self.assertIs(chunk["over_soft_target"], True)

    def test_title_only_preamble_merges_into_first_substantive_section(self):
        for prefix in ('\n# 标题\n\n', '\n\n', ''):
            with self.subTest(prefix=prefix):
                body=prefix+'## 空章节\n\n## 实质章节\n\n前提与规则。\n\n## 后续\n限制。\n'
                docs=load_documents(_write_manifest(self.tmp_path,body))
                chunks=build_chunks(docs,CharacterTokenizer())
                self.assertEqual([c['section'] for c in chunks],['实质章节','后续'])
                self.assertEqual(chunks[0]['original_text'],prefix+'## 空章节\n\n## 实质章节\n\n前提与规则。\n\n')
                self.assertEqual(''.join(c['original_text'] for c in chunks),body)
                self.assertEqual(chunks[0]['source_start'],docs[0]['body_start'])
                for c in chunks:
                    self.assertEqual(docs[0]['text'][c['source_start']:c['source_end']],c['original_text'])
                self.assertEqual(chunks,build_chunks(docs,CharacterTokenizer()))

    def test_title_only_document_without_body_is_explicit_error(self):
        docs=load_documents(_write_manifest(self.tmp_path,'\n# 标题\n\n## 空章节\n\n'))
        with self.assertRaisesRegex(ChunkingError,'doc-1.*substantive'):
            build_chunks(docs,CharacterTokenizer())

    def test_merged_title_counts_towards_hard_limit(self):
        body='\n# '+'长'*100+'\n\n## 规则\n\n'+'温'*340+'尾句\n'
        docs=load_documents(_write_manifest(self.tmp_path,body))
        with self.assertRaisesRegex(ChunkingError,'doc-1.*规则.*512'):
            build_chunks(docs,CharacterTokenizer())
