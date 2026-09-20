# 总结能力交接：任意Agent可用

## 交付了什么

- [原版Skill](thread-learning-log/SKILL.md) 与 [原版脚本](thread-learning-log/scripts/append_learning_log.py)：逐字复制，哈希见export-manifest.json；没有安装到接手者的全局环境，也没有复制个人长期日志。
- 本说明：面向外部Agent和本课程项目的使用适配。原版明确针对可见Codex线程、默认写入Codex全局个人日志；不能声称它原生支持历史补写、所有Agent或HTML生成。本说明补充这些边界，原版文件未被修改。
- 普通Agent不必支持“技能安装”，读取本说明及原版方法即可按流程工作。脚本是可选的Markdown长期日志工具，不负责HTML。

## A. 项目每日总结（本项目默认）

用户要求“总结今天学习”时，按 `2026-09-18-learning-plan.md` 的每日模板，写入 `docs/learning/YYYY-MM-DD.md`，需要图/伪代码时配同名离线HTML。已有文件先读后追加/合并，保留旧知识；不要覆盖或重复追加同一记录。

1. 盘点实际可见的对话、用户回答、代码、实验结果，声明范围完整还是部分。新Agent看不到旧对话时，交接材料只能作为间接来源；不得编造逐字问答。
2. 重点提炼可复用知识：术语、概念区别、判断依据、关键代码、实际例子、常见错误。不要把大量“执行了什么命令”当学习内容。
3. 问答只保留真实问题/真实回答；总结用户理解程度时区分“回答正确”和“独立实验通过”。看不到用户原话就写“交接记录显示”，而非伪装原对话。
4. 开发实现、实测结果、教学示例、后续计划分开。196项测试通过是历史验收，不代表今天重跑；新计划接口不能当已有代码。
5. 每个代码段标明文件/用途；伪代码清楚标记；数字保留单位、条件、来源。不将错误回答当正确结论。
6. 开发进度与学习进度分别记录，列出尚未理解或未验证的点。每条重要结论能追到实际文件或当前对话。
7. HTML不依赖联网或外部CDN，可用HTML/CSS/SVG制作数据流和比较图。Markdown作为易维护源记录，HTML不能悄悄增添不同结论。

用户直接要求生成项目日总结，已经授权保存该成果，无需额外套用原Skill的“个人总日志追加确认”。若来源不足，交付标注partial的总结，不假装完整。

## B. 个人长期日志（可选）

只有用户希望把知识再汇入长期日志时才做。原Skill要求先render草稿、展示并确认，然后用脚本append，不直接编辑总日志。不要在未说明的情况下使用脚本默认的 `~/.codex/skills/thread-learning-log/learning-log.md`。

外部Agent使用项目内显式路径，例如 `docs/learning/learning-log.md`，这是本适配说明的路径约定，不是原Skill默认值。原版规则“只总结当前可见线程”仍用于长期日志，不把资料补写伪称历史对话总结。

最小载荷示例（仅展示格式，不代表真实学习已发生）：

```json
{
  "entry_id": "YYYYMMDD-rag-session-1",
  "date": "YYYY-MM-DD",
  "time_start": "unknown",
  "time_end": "unknown",
  "time_basis": "unknown",
  "category": "learning",
  "primary_tag": "@IndustrialRAG",
  "tags": ["@IndustrialRAG"],
  "context_status": "partial",
  "source": "current-agent-conversation",
  "source_locations": [],
  "reference_locations": [],
  "title": "实际学习主题",
  "sections": {
    "Summary": "本次核心结论",
    "What I Learned": "仅填写实际可见、核对过的知识",
    "Open Questions": "仍未解决的真实疑问"
  }
}
```

把实际载荷保存为 `docs/learning/entry.json` 后，从项目根目录运行：

```sh
python3 docs/handoffs/thread-learning-log/scripts/append_learning_log.py --render --input docs/learning/entry.json
```

展示草稿并得到明确确认后才执行：

```sh
python3 docs/handoffs/thread-learning-log/scripts/append_learning_log.py --append --input docs/learning/entry.json --log-path docs/learning/learning-log.md
```

使用唯一entry_id避免重复追加；写入失败保留草稿并说明没有成功保存，不擅自换到用户未知的全局目录。

## 给接手Agent的总结指令

```text
请先阅读 docs/handoffs/learning-summary-guide.md。
总结今天实际可见的学习内容：术语、概念区别、真实疑问和回答、关键代码/伪代码、实验结果、待补知识。
按项目每日总结模式保存Markdown，必要时生成可离线打开的HTML；注明上下文完整或部分。
开发成果与学习掌握程度分开，不虚构旧对话，不把计划当完成。
除非我另外要求，不追加个人长期总日志。
```
