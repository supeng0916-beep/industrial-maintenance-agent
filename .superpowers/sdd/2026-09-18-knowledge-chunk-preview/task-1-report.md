# Task 1 报告：受限语料读取与确定性分块

## 实现结果

- `assistant/knowledge_documents.py` 仅加载 manifest 明确列出的 `.md` 文件，验证路径边界、SHA-256、重复文档 ID 及 manifest/frontmatter 身份一致性。
- frontmatter 使用禁止重复键的安全 YAML loader，并严格限制为当前扁平 schema；任意标签、嵌套值、非标量键和不支持字段均返回 `DocumentError`。
- `assistant/knowledge_chunks.py` 按 H1 导言和 H2 章节生成连续原文片段，识别 Markdown 代码围栏，保留表格、代码块、空白及全部正文字符。
- 完整 embedding 输入包含文档标题、ID、版本、章节、适用设备、产品型号、教学用途和原文。token 计数调用 `tokenizer.encode(..., add_special_tokens=True)`；超过 300 标记，超过 512 返回含文档和章节的 `ChunkingError`，不截断。
- `chunk_id` 由完整 metadata、策略、来源位置和完整 embedding 输入确定；另输出 `document_sha256` 与 `content_sha256`，相同输入稳定，内容、版本、元数据或位置改变时相应改变。
- 每个片段输出绝对原文字符范围、行范围、来源路径及完整继承 metadata；当前 5 份语料共生成 25 个片段且逐文档正文覆盖完整。

## TDD 与验证

- 先观察缺失模块红灯，再实现读取及分块；初审健壮性问题也分别先加入失败测试再修复。
- `uv run python -m unittest tests.test_knowledge_chunks -v`：12 项通过。
- `uv run python -m unittest tests.test_knowledge_chunks tests.test_knowledge_preview -v`：21 项通过，包含固定 revision 的真实 BGE tokenizer 精确计数、完整覆盖、稳定 ID、超长拒绝和原子发布集成测试。
- `uv run python -m unittest discover -s tests -q`：152 项通过。

## 接口说明

- `load_documents(manifest_path)` 返回 brief 约定的 JSON 兼容文档字典列表。
- `build_chunks(documents, tokenizer)` 返回 brief 约定字段，并增加 `document_sha256`、`content_sha256`。
- 导出 `STRATEGY = "h2-atomic-v1"`、`SOFT_TARGET_TOKENS = 300`、`HARD_LIMIT_TOKENS = 512`。
