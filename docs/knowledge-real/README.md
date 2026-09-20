# 真实电机系统参考语料 v0.1

2026-09-18 实际取得 **15 份独立 DOE Motor Systems Tip Sheets、30 个 PDF 物理页**。全部是原始英文技术指南，不是自编品牌、合成维修工单或 AI 问答。当前来自 **1 个发布机构、1 个系列**，不是跨厂家代表性语料。每份指南保留独立编号、版次、URL、文件 SHA256 和页码；来源登记见 `source-register.json`，只允许导入 `manifest.json` 白名单中的 Markdown。

## 内容与边界

| 文档编号 | 主题 |
| --- | --- |
| doe-motor-ts01 | 高效电机购置 |
| doe-motor-ts02 | 现场效率估算 |
| doe-motor-ts03 | 电机寿命、绝缘与轴承 |
| doe-motor-ts04 | 轴对中、容差及热膨胀 |
| doe-motor-ts05 | V形带与同步带 |
| doe-motor-ts06 | 高效电机误跳闸 |
| doe-motor-ts07 | 电压不平衡 |
| doe-motor-ts08 | 厂内配电压降 |
| doe-motor-ts09 | 非设计电压运行 |
| doe-motor-ts10 | 停转与重启 |
| doe-motor-ts11 | 调速驱动部分负载效率 |
| doe-motor-ts12 | 涡流驱动替换 |
| doe-motor-ts13 | 磁耦合调速驱动 |
| doe-motor-ts14 | 变频专用电机选择 |
| doe-motor-ts15 | 电机与调速驱动不利相互作用 |

资料实际版次为2012年，**不声称是最新标准或法规**。这些是通用工程指南，不是具体制造商的型号维修手册，不提供项目 motor-a/motor-b 的真实产品身份、故障码、润滑周期或安全阈值。`teaching_only: false`仅表示来源并非本项目自编教学资料，不表示可以不经适用性核对直接操作设备。未知型号为null，device_ids为空。

## 来源与使用条件

官方目录：https://www.energy.gov/cmei/ito/motor-systems

权利说明：https://www.energy.gov/web-policies

DOE说明政府信息通常为公共领域，要求适当注明出处，同时明确第三方贡献资料可能受到版权保护。本地语料保留来源与引用，**不宣称整份PDF及每张第三方表格/插图都是开放许可，不打包对外再分发**。例如TS04表格引用Ludeca、TS11表格引用Saftronics、TS15图引用Fluke。PDF原件仅存本地核查目录；公开发布项目时应优先提供下载链接和处理脚本，并另核第三方使用条件。

## 提取方法

使用独立 bundled Python 的 pdfplumber 0.11.9，无项目依赖变更。每页以 `## Page N` 保留物理页定位，分离左侧主栏与右侧建议/资源栏，去除运行页眉、宣传页脚。表格保留对齐文本及表题/脚注，不凭模型猜合并列。保留英文原文；未添加AI概述、翻译、产品元数据推断。上下标与少数断行词有逐项可追溯转写，见验证目录的 normalize.py 与 QA.md。

图像及曲线仍以原PDF为准；抽取正文不是完整图像理解结果，不能用图标题假装读出了曲线数值。公式/表格抽检不是对所有PDF细节的完整校勘。当前页面/块引用如涉及精确公式、图示或安全操作，应回看对应PDF。

原文件：`../verification/m4-real-corpus/raw/`；原页布局文字与抽检PNG：`../verification/m4-real-corpus/pages/`。可用 acquire.py 下载（已有文件不重复），extract.py 重现正文；脚本在 `../verification/m4-real-corpus/`。运行前需相同pdfplumber版本；它不是通用PDF解析器，只针对本批模板布局。

ABB中文手册因文件/许可未完成核查，HF工业数据因领域与源页映射不适合本批，均登记为未纳入，不计入15份数量。后续可补核查合格的中文原厂资料，改善语言及来源覆盖。

这份README、来源登记及评测答案均不进入检索manifest。语料已取得和整理，不代表已建立索引或取得检索成绩。
