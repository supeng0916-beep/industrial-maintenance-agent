# M4.2 文档切块预览实施计划

> **For agentic workers:** 使用 executing-plans 按任务实现与验收；本任务在已获授权的原开发任务执行。

**Goal:** 为现有5份教学语料生成真实token计数、可追溯且不静默丢文的JSON/Markdown切块预览。

**Architecture:** 仅读manifest允许的文档，校验来源元数据与文件哈希；按章节及段落生成候选块，用BGE配套tokenizer核对完整embedding输入长度；尚不生成向量、不建Chroma、不调用LLM。

**Tech Stack:** Python3.11、当前uv环境、BAAI/bge-small-zh-v1.5配套tokenizer；只增加最少必要依赖并锁定。tokenizer下载固定到实际revision，记录文件/版本。无需下载模型权重。

**Spec:** docs/project-plan-v0.2.md 第6.4节、docs/knowledge/README.md，以及本计划的预览范围约束。用户已确认该路线并要求继续开发。

## 全局约束

- 不修改用户数据库、不操作现有采集/服务、不修改docs/learning。
- 只导入manifest列出的Markdown；不递归导入docs/evaluation及答案，来源路径不展开为新正文。
- 未知product_model保持null，不推断产品型号；文档ID、版本、章节、teaching_only和适用device_ids随片段保留。
- 初始目标完整输入约300 tokens，重叠目标40 tokens仅在确实拆分的相邻片段内按完整语义单元提供，不跨文档/章节拼接；标题、明确适用范围、前缀和特殊tokens计入实际长度。512是模型硬上限，不允许truncation=True掩盖超长。
- 对当前语料优先完整二级章节；超过300但不超过512的完整章节可作为有明确标记的原子块保留。无法安全拆分且完整输入超过512时返回带文档章节的错误，保留源文件，不悄悄截断。后续人工改写/拆分是可接受的预览结果，不凭通用字符切割假装语义安全。
- 当前阶段不实施AI概述、BM25、重排、向量库、生成模型或助手UI；不把预览完成当RAG完成。
- 非git仓库不初始化或伪造提交。

## Task 1：受限语料读取与确定性分块

**Files:** 新增assistant/knowledge_documents.py、assistant/knowledge_chunks.py（可按实际简化）；tests/test_knowledge_chunks.py。

**Interfaces:** load_documents(manifest_path)返回验证过的文档；build_chunks(documents, tokenizer)返回含原文、embedding_text、token_count、document_id、version、section、chunk_id、来源位置和适用性的片段。

- [ ] 先写并运行失败测试：未列入manifest的文件不导入，哈希不符/重复ID/路径逃逸明确失败，null型号保留；正文不能被任意YAML对象解析执行。
- [ ] 实现受限读取；使用安全解析，拒绝不支持的结构，不把metadata YAML当正文。
- [ ] 写分块测试：条件＋规则＋限制完整保留；表格带列头；代码块不拆坏；章节跨越错误不混入。普通无超长章节可以整章保留，避免不必要重叠。
- [ ] 实现确定性ID（包含文档版本与内容/切块策略摘要），同输入同配置重复执行一致，内容改变ID改变，不仅使用位置编号。
- [ ] 写并验证长度边界测试，模拟token计数仅用于单元测试，真实验收必须使用BGE tokenizer。示例断言：`assert chunk.token_count == len(tokenizer.encode(chunk.embedding_text, add_special_tokens=True))`，且`chunk.token_count <= 512`。
- [ ] 对完整输入超长明确失败，不截断、不丢尾句；保留原文字符范围以检查正文覆盖和溯源。



Interface agreement: load_documents(manifest_path) -> list of dicts {metadata: dict, source_path: str (manifest relative path), sha256: str, text: str (entire original decoded file), body_start: int (absolute character offset after frontmatter), body: str}. build_chunks(documents, tokenizer) -> list of JSON-serializable dicts {chunk_id,document_id,version,section,metadata,source_path,source_start,source_end,source_line_start,source_line_end,original_text,embedding_text,token_count,over_soft_target, ...}. source char offsets absolute into text; coverage must include every body character including heading/whitespace. tokenizer.encode(text, add_special_tokens=True) returns list[int]. Strategy constant exported STRATEGY. Document errors use ValueError subclass. No shared dependency edits; root will add PyYAML/tokenizers. Metadata safe strict loader; consider only flat supported schema with scalars/list strings, reject duplicates/arbitrary tags. Favor full H2 chapters <=512; overhard reject with doc+section, no split required in this first conservative iteration. Preserve H1 preamble as a chunk if useful, never lose it. Do not edit corpus files. Report tests/results in task-1-report.md alongside brief. No subagents.
