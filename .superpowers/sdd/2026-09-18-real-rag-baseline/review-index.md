# 索引、CLI 与检索评测独立审阅

日期：2026-09-18

## 范围与结论

只读审阅 `assistant/rag_index.py`、`assistant/rag.py`、`assistant/rag_evaluation.py` 与相应索引/CLI测试；参考实施计划，并检查 manifest 加载与 chunk 字段契约。未修改实现、真实语料或运行服务，临时复现均使用临时目录和明确测试用合成向量。

**当前无待解决的确定性阻塞问题。** 审阅发现一项持久化文件缺失检查问题，根代理已修复；独立复跑 10 项相关测试全部通过。此结论不替代实际权重/冻结语料正式构建与评测验收。

## 发现与修复验证

### P2：缺失 HNSW 文件时查询静默重建（已修复）

原 `read_index` 仅检查 `chroma/chroma.sqlite3`，未检查 HNSW 持久化文件。使用真实临时 Chroma 构建两个片段后删除 UUID 向量目录，`search_index` 仍返回 `ok=True` 和原候选，Chroma 自动重建缺失文件。这不符合计划要求的“文件缺失明确报错”。

根代理现已在发布清单记录 `storage_files`（排除临时 WAL/SHM），并在启动 Chroma 客户端前验证必需文件存在且路径合法。新增 `test_missing_hnsw_files_fail_before_chroma_can_repair` 验证删除 HNSW 文件后明确失败；审阅者独立复跑该测试及原测试全部通过。

## 已核对行为

- 模型签名包含完整结构比较；签名与 chunks 均有摘要，查询核对 Chroma 中记录的摘要、数量与 cosine 配置。
- cosine 距离以较小为近，结果明确说明不是置信度或可回答性；实际临时 Chroma 查询验证距离 0/1 与排序。
- 新索引目录拒绝覆盖既有路径；嵌入失败发生在目录创建前，后续构建失败清理本次新目录；重建使用新目录，无旧文档残留。
- 构建只经 manifest 白名单、文件哈希与身份验证加载文档，没有扫描目录导入评测问题或 README 的路径。
- 空设备列表与未知型号不视为通用适用；过滤器拒绝未知字段、未知值及错误类型；top_k 限制为整数 1～10。
- CLI 异常输出 JSON 错误并退出 1；评测输出使用独占创建，拒绝覆盖旧结果。
- 评测按文档、页码与规范化 anchor 匹配；any/all、多个 evidence 及上下文规范化有测试；无答案题不计检索命中，开发集/保留集分开统计，未声称 LLM 回答正确率。

## 验证记录

命令：`.venv/bin/python -m unittest tests.test_rag_index tests.test_rag_cli -v`

结果：`Ran 10 tests ... OK`。仅出现 Chroma 自身的 legacy embedding function config 弃用提示，没有测试失败。

## 非阻塞边界

Anchor 匹配是字面证据存在性检查，不代表语义充分性或全部适用条件正确；实现已明确披露此限制。页码与上下文页码进一步细分时，应保持评测 anchor 的来源页关联，避免未来跨页上下文被误算到正文页。本次没有把该潜在边界列为已复现缺陷。
