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

- [x] 先写并运行失败测试：未列入manifest的文件不导入，哈希不符/重复ID/路径逃逸明确失败，null型号保留；正文不能被任意YAML对象解析执行。
- [x] 实现受限读取；使用安全解析，拒绝不支持的结构，不把metadata YAML当正文。
- [x] 写分块测试：条件＋规则＋限制完整保留；表格带列头；代码块不拆坏；章节跨越错误不混入。普通无超长章节可以整章保留，避免不必要重叠。
- [x] 实现确定性ID（包含文档版本与内容/切块策略摘要），同输入同配置重复执行一致，内容改变ID改变，不仅使用位置编号。
- [x] 写并验证长度边界测试，模拟token计数仅用于单元测试，真实验收必须使用BGE tokenizer。示例断言：`assert chunk.token_count == len(tokenizer.encode(chunk.embedding_text, add_special_tokens=True))`，且`chunk.token_count <= 512`。
- [x] 对完整输入超长明确失败，不截断、不丢尾句；保留原文字符范围以检查正文覆盖和溯源。

## Task 2：真实tokenizer与CLI预览

**Files:** 新增preview_knowledge.py（或python -m assistant.knowledge_preview），必要修改pyproject.toml/uv.lock；新增tests/test_knowledge_preview.py和docs/verification/m4-knowledge-preview/。

- [x] 从官方模型文件/文档核实tokenizer加载方法和512上限，固定下载revision；无网络或缺资源时说明错误，不退化成字符数却声称token数。
- [x] CLI输入manifest、输出目录；生成chunks.json、preview.md和report.json。输出配置、tokenizer revision、文档哈希、块数/最大长度/超过软目标块、覆盖信息；预览含来源位置与完整输入，原文与增强前缀区分。
- [x] CLI失败不得留下标记为成功的部分新产物，不覆盖原语料或旧成功产物；测试使用临时目录。
- [x] 用本项目真实5份语料执行，人工复核R01～R06目标章节能定位，温度恢复的“严格低于”和条件未遗漏；只报告结构检查，不能报告检索Hit@K。
- [x] 运行相关新测试以及assistant工具回归；如果共享依赖有重大变更再按影响扩大回归。保留命令和结果。
- [x] 更新knowledge README说明命令与结果，不声称已索引；不要修改主项目计划的里程碑完成状态。反馈文件、命令、真实tokenizer、块统计、限制以及验证证据。

## 完成记录

2026-09-18：5份文档生成25块，最大322 tokens，2块超过300软目标，正文3955字符全部覆盖。真实tokenizer固定revision；完整Python回归157项通过，最终局部knowledge回归21项通过。报告见docs/verification/m4-knowledge-preview/验收说明.md。保守整章策略对超长直接报错，本小步未实现语义拆分/重叠；无向量、索引或检索成绩。

2026-09-18 v2修订：主任务发现5个标题空块。已按授权把纯标题/空白前导合并到首个正文章节，保留实质导言；策略升v2，新preview-v2产物20块/最大322 tokens，24项受影响测试通过；旧preview未覆盖，未重复全回归。
