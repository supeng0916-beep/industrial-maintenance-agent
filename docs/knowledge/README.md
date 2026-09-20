# 教学知识库语料 v0.1

当前已准备文档并实现切块预览，尚未构建向量索引、下载嵌入模型权重、启用重排或测得检索成绩。

## 导入边界

未来索引器只导入manifest.json中明确列出的5份Markdown，不能递归导入整个docs目录。README、manifest和docs/evaluation题集均不作为检索正文；来源引用仅用于追溯，不自动展开导入。AI整理正文不等于厂家原始资料。

每份文档有document_id、version、标题、适用设备、未知产品型号、核对日期及项目来源。manifest记录文件SHA256，供后续检查变更；索引器仍待实现，当前不会自动更新或删除向量。chunk_id由下述切块预览实际生成，不手工编造。文档来源路径相对项目根目录。

## 评测映射

| 题号 | 本批目标文档 | 必须保留的章节 |
| --- | --- | --- |
| R01 | temperature-alarms | 使用范围与默认规则、触发前的待确认 |
| R02 | opcua-evidence | 设备身份与数据准入、源时间和处理时间 |
| R03 | temperature-alarms | 已触发告警如何恢复、证据中断与设备隔离 |
| R04 | device-points | 整轮保存与同步测量 |
| R05 | readonly-queries | 完整统计与有限明细 |
| R06 | readonly-queries | 空结果和失败 |
| N01～N04 | evidence-boundaries作为边界参考 | 不存在适用厂家答案；缺失型号等夹具见题集 |

N02～N04夹具应在独立测试中按需提供，不把假设的A/B产品型号、E104解释或500小时周期混入正式语料。不能仅返回通用边界提示就算具体故障资料命中。

切块时每块继承文档元数据，并保留标题、前提、规则和限制之间的关系。按既有计划比较top5，必要时比较top10；BM25、AI上下文增强和重排仍属于待评测选项。

## M4.2 第一小步：切块预览

现在可生成只读的 JSON/Markdown 预览，仍未生成向量或建立索引。在项目根目录执行：

```sh
uv sync --locked
.venv/bin/python -m assistant.knowledge_preview --manifest docs/knowledge/manifest.json --output docs/verification/m4-knowledge-preview/preview-rerun --download-tokenizer
```

`--download-tokenizer` 仅首次缺少资源时需要；固定 BAAI/bge-small-zh-v1.5 revision `7999e1d3359715c523056ef9478215996d62a620`，只取 tokenizer.json 与 tokenizer_config.json 两个小文件，并校验 SHA256，不下载权重。默认缓存为项目 `.cache/knowledge-tokenizer/`。之后不带此参数即可离线执行；缺资源直接报错，不以字符数冒充 token 数。

输出目录必须是新目录；已有目录（包括旧成功预览）不会覆盖，再运行请换 `--output`。生成 `chunks.json`、`preview.md`、`report.json`；失败返回非零退出码，不发布成功报告。来源字符区间采用原文件解码文本的零基、左闭右开偏移，行号从1开始，YAML元数据不作为正文。

当前策略保留完整二级章节和有实质正文的导言；仅含一级标题/空白的前导内容合并到首个有正文的章节，来源范围仍为真实连续片段，标题、适用范围前缀、原文、特殊tokens都计入输入。300是软目标，301～512的完整章节明确标记；超过512时报出文档和章节，需人工调整原文或另行实现安全拆分。当前不拆章节、不添加40-token重叠，避免将前提与规则分开。报告校验正文覆盖，chunk_id包含版本、内容及策略信息，可重复生成。

验收结果与限制见 [M4.2预览验收说明](../verification/m4-knowledge-preview/验收说明.md)。R01～R06仅核对目标章节可定位和内容未漏；没有执行检索，不报告Hit@K。

本次实际预览：5份文档、20块、最大322 tokens，2块超过300软目标，正文覆盖全部通过。详见验收说明和真实产物。

当前修订产物位于 `docs/verification/m4-knowledge-preview/preview-v2/`；旧 `preview/` 原样保留。策略版本为 `h2-atomic-v2-merge-title-preamble`，策略变化使chunk_id更新；同版本同输入重复执行仍一致。24项受影响测试通过。
