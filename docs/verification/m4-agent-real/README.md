# D5真实模型验收：本地Ollama（qwen2.5:7b）四类只读工具调用

日期：2026-09-20。模型：本地Ollama 0.34.2 + qwen2.5:7b（4.7GB，Metal/M4）；LangChain适配 langchain-ollama==1.1.0。业务夹具为脚本自建（见各run目录内 `fixture.sqlite3`），不触碰用户data；文档工具用真实E5最终索引。复现：

```sh
.venv/bin/python experiments/agent_real_acceptance.py --output docs/verification/m4-agent-real/<新目录名>
```

## run-2026-09-20a（首次运行，暴露三类问题）

- **复合场景**：只调get_device_status，文档部分凭记忆作答（期望两个工具）。
- **文档场景**：模型生成的检索问句较差，top5未含表格行块；随后**编造"94%～95%"**而非声明证据不足（正确值86%）。
- **历史场景**：工具只返回6/7个点（首点10:00:00丢失）——**根因是验收夹具时间格式缺微秒**：storage.history_between 依赖统一ISO文本比较，真实采集器全部写微秒格式（collect_temperature.py、opcua_storage.py），生产数据不受影响；夹具已改为与采集器一致。该格式不变式建议在D10写入runbook（候选加固：写入时归一化，暂不动共享存储层）。

## run-2026-09-20b（修正夹具+强化可信上下文指令后）

| 场景 | 工具路由 | 状态 | 语义要点 |
| --- | --- | --- | --- |
| status | get_device_status ✓ | answered | 正确读64.0℃并主动说明数据已过期（陈旧标识） |
| history | query_metric_history ✓ | answered | 7点齐全，均温62.5℃计算正确 |
| document | search_maintenance_docs ✓ | answered | **已知短板**：表格行块已在候选doc-4（含86%原文），但7B模型未能提取报告该值，答非所问的泛化内容 |
| composite | 两工具都调 ✓ | answered | 状态+文档分别取证；V带部分引用候选（95%/98%正确） |

## run-2026-09-20c-cloud（DeepSeek首跑，暴露跨供应商协议bug）

模型deepseek-chat（云API，OpenAI兼容端点）。四场景工具路由全对，但最终回答全部`unavailable`：**编排循环此前只追加tool_result消息、未先补记模型的assistant(tool_calls)回合**——OpenAI兼容API要求两者成对相邻，Ollama宽松放行、DeepSeek严格拒绝。修复：agent.py补记assistant回合+缺失id稳定占位（`tests/test_assistant_agent.py` 新增2项回归测试）。

## run-2026-09-20d-cloud（DeepSeek，修复后：四类全通过）

| 场景 | 工具路由 | 耗时 | 语义要点 |
| --- | --- | --- | --- |
| status | get_device_status ✓ | 2.7s | 64.0℃正确；主动说明数据过期（16.4小时龄 vs 5秒阈值）、区分"有数据"与"设备健康" |
| history | query_metric_history ✓ | 2.1s | 7点齐全，均温62.5℃并展示计算（437÷7）与最小/最大值 |
| document | search_maintenance_docs ✓ | 3.7s | **表格行块doc-1命中，86%正确提取**，回读整行47/86/93/94/95/96/97，注明出处（TS11 Table 1）与"典型值"限定 |
| composite | 两工具 ✓ | 5.6s | 状态+文档分别取证，过期数据如实标注 |

## 云/本地图层对照（同夹具同索引）

| 维度 | qwen2.5:7b本地（run-b） | deepseek-chat云（run-d） |
| --- | --- | --- |
| 四类工具路由 | 全对 | 全对 |
| 表格精确取数（86%） | 失败（候选在、提取不出） | **成功**（整行回读+出处+限定） |
| 统计计算 | 均温正确但漏列首点（旧夹具） | 7点齐全+算式+极值 |
| 单场景耗时 | 12～52秒 | 2～6秒 |
| 数据新鲜度说明 | 说明过时 | 说明过时+精确数据龄 |

结论：云API路线在质量与速度上全面优于本地7B；本地路线保留为无网对照。**语义正确性仍按计划在D9按场景集人工核查，本验收不构成一般可靠性声明。**


## 结论与限制

1. **流程层（本验收范围）**：四类调用在云/本地两条路线均路由正确、无未注册工具、结果合同完整（status/answer/evidence/citations/limitations/calls/checked_at）。
2. **语义层（D9范围）**：deepseek-chat在本验收四场景语义质量显著优于本地7B，但仍须按assistant-v1场景集人工核查后才可对文档问答下结论；D8页面须呈现候选原文供人工核查。
3. citations字段模型不主动产出（程序校验就绪，编造引用会被剔除并说明）。
4. LLM输出有随机性：以上为单次运行记录，不构成一般可靠性结论。
5. 跨供应商提示：编排协议须同时满足Ollama（宽松）与OpenAI兼容API（严格的assistant/tool_calls配对）——已有回归测试钉死。
