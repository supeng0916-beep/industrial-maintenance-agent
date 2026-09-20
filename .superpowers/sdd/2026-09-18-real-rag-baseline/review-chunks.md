# RAG 分块与评测增量独立审阅（最终 v4 通过）

日期：2026-09-18。只读审查代码与真实语料，在内存中使用缓存真实 tokenizer 预分块；没有修改源资料、实现或运行服务。

## 最终 spec / quality 结论

**冻结 v4 复核通过，前轮三项问题均已关闭，没有待处理阻断。** 审阅范围内的数据契约、源文本范围、模型完整输入预算、显式条件保留、表格重复来源与评测来源页匹配符合本轮检索基线边界。实际最终索引/评测执行由根代理验收，本结论不替代它。

最终局部测试：`.venv/bin/python -m unittest tests.test_rag_chunks -v`，**20 tests / OK**。额外用两套缓存真实 tokenizer 对 TS07、TS08、TS11 执行针对性预分块核查，六组全部通过；原文范围与重复介绍段的 source_start/source_end 同时核对精确一致。

- 多段显式 Scope：新增回归确认 `For Model X only.` 和另段 `Do not operate outdoors.` 同时跟随嵌套表格；源码改为在同一显式作用域累积段落。
- TS07 / TS08：两模型实际表块均保留 TS07 的 1,800 RPM / 100-horsepower 与 TS08 的 continuously operated / 2.5 volts 前提。引用只限紧邻介绍段明确指向同号表或 table below，带精确来源范围，并不会恢复全页条件污染。
- TS11：两模型实际表块均包含七个完整负载列标签及 no widely accepted test protocol 脚注，且上下文不含 centrifugal。实际最终语料表格未触发行拆分；强制超长 fixture 已验证数字列标签每组重复，并拒绝无法确定的混合行宽。因此原问题准确描述为拆分后备路径缺陷，不能声称实际 TS11 曾出现分行丢列头。
- `task-chunks-report.md` 已更新到 v4，明确两模型 15/15、软目标仅诊断标记及 TS12 跨页隐式前提边界，与冻结实现一致。

下文保留前轮审阅过程与历史发现，历史“待修复”不再代表当前状态。

## 初审结果

相关测试独立运行：`.venv/bin/python -m unittest tests.test_rag_chunks tests.test_knowledge_chunks tests.test_knowledge_preview tests.test_rag_index tests.test_rag_cli -v`，**52 tests / OK**。

同一 manifest（SHA256 `2a1da80dca7f618e0b39c19ed77417bc4dc45f1f5655083d10bdbef9b02e15a3`）独立预分块得到：E5 15/15、113 块、最大 512 token；BGE 15/15、131 块、最大 508 token。逐块核对完整格式化输入 token 数、原文精确范围、拼接恢复全文，以及结构化重复内容的 source_start/source_end 精确来源。

这些计数对应初审快照，若后续修复改变分块，应以新索引与最终 probe 为准。

## 已核对

- TS11 Page 2 不再带入 Page 1 centrifugal 条件；页码与重复上下文来源页分开保存。
- 普通介绍段不再提升为全页适用范围；显式 Scope/Applicability 条件跟随子标题，物理换页清理局部条件。
- 有限的结构拆分保持完整数字行、完整句子及原始范围；长表重复列头/脚注，长列表项及 text callout 重复明确介绍内容，无法安全拆分的单元报错。
- 元数据白名单、原始哈希、文档身份及路径边界校验保持有效。
- 评测增量 `context_sources` 按来源页选择文本，跨页上下文不能归到正文页；`index_corpus` 与 `index_chunks_sha256` 进入结果。两项新增回归在本次独立测试中通过。

## 已反馈待修复/复核

1. **P2：显式 Scope 多段条件只保留第一段。** `if depth not in premises and explicit_scope` 阻止后续同作用域段落累积。复现：`### Scope` 下先 `For Model X only.`，再空行 `Do not operate outdoors.`，随后 `#### Table` 与表格；表块保留第一条件，丢失第二条件。建议显式作用域段落累积，超过完整 token 限制时明确失败。
2. **P2：紧邻表标题之前的明确表前提丢失。** 真实 E5 TS07 表格块包含效率数值与脚注，但遗漏紧邻介绍段绑定 Table 1 的 1,800 RPM / 100 hp 样本条件。TS08 Page 2 同类介绍段指向 table below，连续运行及可达到 2.5 V 压降前提也未随表。应仅建立局部明确表引用关系，避免重新将这些条件污染到整页其他内容。
3. **P2：TS11 纯数字列头可能被当数据行。** 根代理先发现并已让分块代理修复，本审阅尚待最终修订后检查。必须确认每一行组重复 1.6 / 12.5 / 25 / 42 / 50 / 75 / 100 七个负载列标签。
4. 初读 `task-chunks-report.md` 仍写 v2、BGE 12/15 与所有表/列表不可拆分；已反馈更新为最终实现及实际 probe 结果。

## 语义边界

精确覆盖和 token 合规不等于每块语义完整。跨页示例说明或未显式标记的前提仍需要原文复核，例如 TS12 Page 2 表 2/3 的示例背景在 Page 1。候选应保留全文回溯路径，不应把表中示例推广为设备通用实测或已核实结论。
