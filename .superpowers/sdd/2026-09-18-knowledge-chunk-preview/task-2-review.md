# Task 2 Review — M4.2 tokenizer / CLI

日期：2026-09-18

## 结论

- Spec：Task 2 实现通过本次审阅。真实 tokenizer、完整输入计数、输出内容、coverage 和失败保留原文件/旧结果符合计划；最终验收说明和持久化验收产物仍由主任务收尾。
- Quality：未发现本审阅范围内可复现的阻断或重要问题。
- Task 1 已由主审阅提出的 ID、围栏、元数据和非法 YAML 键问题不重复列入本报告；其修复后的集成回归由主任务确认。

## 审阅范围

读取计划 Task 2 及全局约束、knowledge README、assistant/knowledge_tokenizer.py、assistant/knowledge_preview.py、tests/test_knowledge_preview.py、pyproject.toml、uv.lock；同时阅读当时存在的 loader/chunker 以核对真实集成。

## 验证证据

1. `.venv/bin/python -m unittest tests.test_knowledge_preview -v`：9 tests，全部通过；真实 tokenizer 测试未跳过。验证 600 个中文字符得到 602 tokens，关闭特殊 token 后为 600，未静默截断。
2. 直接读取官方固定 revision `7999e1d3359715c523056ef9478215996d62a620` 下文件，并与实现中的 SHA256 比较：
   - `tokenizer.json`：439125 bytes，`48cea5d44424912a6fd1ea647bf4fe50b55ab8b1e5879c3275f80e339e8fae26`。
   - `tokenizer_config.json`：367 bytes，`e6f3b96db926a37d4039995fbf5ad17de158dfb8f6343d607e4dbaad18d75f5a`；`model_max_length = 512`。
   - 官方来源：https://huggingface.co/BAAI/bge-small-zh-v1.5/tree/7999e1d3359715c523056ef9478215996d62a620
3. 使用临时目录分别注入第 1、2、3 次 `os.replace` 抛出 OSError；三种情况均没有残留新输出或 staging 目录。已有成功输出不覆盖由单元测试确认。
4. 使用真实 tokenizer 生成临时预览：5 documents、25 chunks、最大 317 tokens、2 个超过 300 的块、coverage_complete=true。此为审阅时统计；后续前缀变更可能改变 token 数。
5. 逐一检查 README R01～R06 对应 9 个目标章节均唯一存在。温度恢复的前提、78℃保持/77.9℃恢复、不能把低于解释为小于等于均由真实语料测试确认。
6. `uv lock --check --offline`：通过，Resolved 42 packages。

## 实现观察

- 固定模型 revision、两个文件 hash、tokenizers 库版本；下载只取 tokenizer 资源，缓存 hash 失败时拒绝使用，不回退为字符计数。
- backend 显式禁用 truncation/padding；发布边界再次以完整 embedding_text（含特殊 tokens）核对计数和 512 上限。
- JSON 保留原文、完整输入和元数据；Markdown 用动态围栏区分原文/完整输入；coverage 校验原文切片、范围和完整正文联合覆盖。
- 成功 report 最后发布；普通写入/移动失败回滚新目录；拒绝已有目录及语料目录中的输出。
- 本次仅结构和 token 长度审阅，没有生成向量、调用 LLM 或评测检索成绩。未修改 data、docs/learning 或服务。

## 最终全链路复核（Task 1 + Task 2）

- 复读修复后的 `knowledge_documents.py`、`knowledge_chunks.py`、`tests/test_knowledge_chunks.py`。确认 ID 纳入完整 metadata、embedding_text、策略及位置；重复同名同正文块不同 ID；长围栏仅被同字符且足够长、无附带内容的围栏关闭；拒绝非 `.md` 路径和不可哈希 YAML 键；块包含 document/content SHA256 和教学前缀。
- `.venv/bin/python -m unittest tests.test_knowledge_chunks tests.test_knowledge_preview -v`：21 tests 全部通过，无跳过。
- 真实 tokenizer 临时输出再次验证：5 文档、25 块、最大 322 tokens、2 个超过 300 软目标的块，coverage_complete=true。最终实际统计替代前文修复前的 317 tokens 快照。
- Task 1 spec / quality：核心行为通过，没有发现新的阻断或重要问题；Task 2 回归通过。
- 一个非阻断错误清晰性边角已反馈主任务：`_load_metadata('1: value\nextra: value', 'fixture.md')` 会因对混合类型字段名排序抛 TypeError；建议在字段集合/排序前明确拒绝非字符串键。该情况仍失败关闭、不发布输出，但错误没有转成 DocumentError。是否修复及修复后验证由主任务收尾。

### 最终收口

已只读确认 loader 在字段集合/排序前明确拒绝非字符串键；重新执行上述混合类型字段名复现用例，结果为 `DocumentError: frontmatter keys in fixture.md must be strings`。前述非阻断边角已关闭。最终 Task 1 spec / quality 与 Task 2 回归审阅通过，本报告无待修问题；未重复无必要的全套测试。
