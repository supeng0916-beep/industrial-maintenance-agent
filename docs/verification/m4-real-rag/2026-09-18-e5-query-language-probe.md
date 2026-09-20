# E5 查询语言诊断：接手后的最小实验

日期：2026-09-18。范围：开发集 R17、R29、R34；仅查询已有最终 E5 索引，不改业务代码、语料、题集、模型或默认检索行为。没有运行完整回归，没有生成模型回答。

## 只读失败分析

已核对项目计划、交接、最终验收、失败记录、集成复核，以及 `rag_evaluation.py`、`rag_index.py`、`rag_embeddings.py` 与实际片段。

| 开发题 | 中文基线表现 | 原文与候选核查 | 当前定位 |
| --- | --- | --- | --- |
| R17 低电压与启动困难 | 标注证据不在 top10；正确文档 TS09 第2页排7 | 目标在 TS09 第1页，明确写出降压降低加速区间转矩、启动转矩不足与加速时间增加；目标段实际已入库 | 不是目标证据缺失；候选偏向启动电流等相邻主题。语言表达/排序值得检查，不能据此排除块长度等因素 |
| R29 轴承电流缓解 | 标注证据不在 top10 | TS15 第2页排1、2，已包含接地/布线等措施及轴承电流原因；标注的 shaft-grounding 在第1页 sidebar，和其他建议共处一块 | 存在部分相关证据；固定 anchor 的未命中不能解释为全部语义漏检。具体轴接地刷措施未被取回 |
| R34 100hp 年节电示例 | 目标表格排8，top5漏 | TS01 第1页目标块同时含 15,680 kWh 和 1800 RPM、TEFC、8000小时/年、75%负载等注释；top1是另一份电压不平衡效率表 | 此例表格及明确条件在块内；主要可见问题是排序混淆，不需要先重建全库 |

对应目标 chunk_id：

- R17：`doe-motor-ts09:3ff88e5bc8bb6008d1a1`
- R29：`doe-motor-ts15:c6befde2d690739f9eb4`
- R34：`doe-motor-ts01:87041a88a41c08418cab`

R03 属于原 holdout，不作为本轮三道开发诊断题。旧 holdout 已被历史工作观察，不能重新称为独立未见评测。

## 单变量探针与实际结果

假设：中文问题到英文段落的表达差异，是这些失败的影响因素之一。固定索引、模型、切块、评分和 top_k=10，仅替换查询文本为英文等义表达。英文查询不加入答案数值、目标文档ID或原题没有的具体措施。

| 题号 | 原中文目标首个排名 | 英文目标首个排名 | 中文 top10 ID顺序与保存基线一致 |
| --- | ---: | ---: | --- |
| R17 | 未进前10 | 10 | 是 |
| R29 | 未进前10 | 5 | 是 |
| R34 | 8 | 1 | 是 |

以上来自本轮真实缓存 E5 权重与 Chroma 查询，进程退出码0；共六次查询。三道选定失败题的标注命中由 Hit@5 0/3、Hit@10 1/3，变为 2/3、3/3。**这不是24题开发集成绩，也不是独立测试成绩或回答准确率。**

解释限制：英文改写由接手助手在读过原文后准备，存在选择偏差和措辞受证据影响的风险；只能作为诊断探针。一次等义改写也包含措辞变化，不能严格把变化全部归因于语言。R17仍只排第10，top5问题没有解决。不同查询的余弦距离不作为有答案概率，也不据距离整体降低宣称更可靠。

## 可复现命令

项目根目录运行以下命令，默认仅使用已缓存模型。它打印两种查询的标注证据排名和全部候选ID/距离，复用现有评分器；不下载权重、不请求API、不写报告或修改索引内容。

```sh
.venv/bin/python - <<'PY'
import json
from pathlib import Path
from assistant.rag_embeddings import LocalEmbedder
from assistant.rag_index import search_index
from assistant.rag_evaluation import score_evidence

translations = {
    'R17': 'Why can a slightly lower voltage make a motor harder to start and take longer to accelerate?',
    'R29': 'When a variable-frequency drive causes bearing currents, what design measures does the guide list to mitigate them?',
    'R34': 'In the example table for replacing old motors, what is the annual energy saving for the 100 hp row? Can it be used directly as the energy saving for our factory?',
}
baseline = json.loads(Path('docs/verification/m4-real-rag/e5-evaluation.json').read_text())
embedder = LocalEmbedder('e5')
for item in baseline['results']:
    case = item['case']
    if case['case_id'] not in translations:
        continue
    for language, query in [('zh', case['question']), ('en', translations[case['case_id']])]:
        candidates = search_index('docs/verification/m4-real-rag/doe-e5-final', query, embedder, top_k=10)['candidates']
        ranks = [c['rank'] for c in candidates if any(score_evidence(case, [c]))]
        result = dict(case_id=case['case_id'], language=language, query=query,
                      first_anchor_rank=ranks[0] if ranks else None,
                      candidates=[dict(rank=c['rank'], chunk_id=c['chunk_id'], distance=c['distance']) for c in candidates])
        if language == 'zh':
            result['baseline_ids_reproduced'] = [c['chunk_id'] for c in candidates] == [c['chunk_id'] for c in item['candidates_top10']]
        print(json.dumps(result, ensure_ascii=False))
PY
```

## 下一项最小改进实验及验收（尚未实施）

优先检验“查询英文改写”是否在完整开发集上稳定有益；暂不同时加入BM25、reranker或重切块。当前结果尚不足以更换默认查询流程。

1. 为全部24道有答案开发题准备等义英文查询，仅根据问题改写，不增加答案、型号/条件或目标文档提示；将译文及改写规则冻结，保存哈希，不根据检索排名反复修改。由于本执行者已看过部分证据，报告必须注明此局限。
2. 固定现有E5索引和全部评分规则，保存中英文每题top10、Hit@5/10、进步/退步清单、查询时间；原始中文题保留不改。对10道证据不足题也保留候选，命中仍为null，不把翻译或检索当作自动拒答。
3. 进入下一阶段的初步门槛：完整dev Hit@5高于15/24，Hit@10不低于19/24；所有退步题逐项分析；数值/单位/否定/适用条件的翻译变化为阻断项。门槛通过只表示值得继续验证，不能宣称生产可用。
4. 冻结候选方案后，由独立出题/审核过程补充新的未用于调优检查题，覆盖表格条件、相近概念、无答案；一次运行并分开报告。原holdout仅可作已观察回归集。如果不能做到独立出题，则如实标为新增检查集，不冒充独立盲测。
5. 人工改写探针不能直接成为自动翻译组件。若决定接入自动查询改写，需先确定运行方式与模型，再测超时、成本、原意保留及失败回退；现阶段没有供应商、凭据或付费调用假设。

M4.2质量改进仍未完成。M4.3模型运行方式、M4.4助手页面和M5交付继续沿用主计划。
