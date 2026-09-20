# M4.2 真实资料索引与检索基线实施计划

> **For agentic workers:** 使用执行计划和TDD技能，按职责并行；用户2026-09-18明确授权先开发再学习。现有项目非git，不创建无用git仓库，不触碰正在运行服务。

**Goal:** 真实原始资料落地、可追溯切块、真实嵌入/Chroma持久化及检索评测闭环。

**Spec:** docs/project-plan-v0.2.md 的2026-09-18修订、docs/research/2026-09-18-real-world-rag-sources.md。

## 职责和隔离

- 来源整理工作负责docs/knowledge-real/和docs/verification/m4-real-corpus/，真实下载、页级提取、来源登记与元数据。
- 原开发任务负责assistant知识库实现、依赖锁、新相关测试、索引/CLI及验收docs/verification/m4-real-rag/。
- 主学习任务负责评测问题、来源质量核对与集成复核，docs/evaluation/real-rag-v0.1.json。
- 保持旧教学语料及预览回归，不将评测问题/答案或README当正文导入。数据集说明不是厂家手册，合成工单不得标成实测。

## 数据契约

真实来源manifest沿用现有结构，必需frontmatter沿用load_documents。外部文档device_ids=[]，不映射为motor-a/b；可选字段language/source_url/publisher/source_document_id/source_pages（字符串列表）/applicability/license/source_sha256，类型须校验、元数据随chunk和结果保留。源文件保留原始URL、日期、哈希；内部知识ID不当产品型号。

## 任务

- [x] 真实文档采购与抽查：目标10～20份独立指南/文档，来源不足如实报告，去重统计。解析保持原始语言/单位/条件，记录页码、表格限制；无法解析的文件隔离而不是生成虚构替代内容。
- [x] 分块支持：先按原始文档/页/章节划分，再按段落/完整句子；必要父标题与适用条件随块保留，列表/表格关联列头与前提。单原子单元超长明确报错，不能静默truncate。保留源范围/原文片段及重复上下文区别；不能只靠覆盖率声称语义完整。新策略有版本且不覆盖旧预览。
- [x] 嵌入：中文BGE为对照，英文/中英真实资料优先试multilingual-e5-small（384维512token）或经官方核查的同等级多语言小模型。模型ID/revision、pooling、normalize、query/passage前缀、维度写入索引配置并在查询核对。使用实际权重、真实计算，不用hash/random向量作验收。模型切换新建独立索引。查询和文档一致的tokenizer/格式，禁止超长截断。
- [x] Chroma本地索引：显式cosine、默认HNSW，关闭telemetry和外部追踪，不调用在线LLM。构建新目录、完成校验才发布，失败不损旧成功产物。只根据manifest白名单导入。清单删除/版本更新通过全量新索引重建，防止陈旧块残留；查询配置不符/文件缺失/空库明确报错。
- [x] 查询CLI/接口：独立模块供后续search_maintenance_docs包装（本步不扩LLM三工具合同），输出候选正文、上下文、document_id/version/chunk_id/页码/URL及距离语义，标明候选并非确诊。top_k限制、过滤元数据拒绝不认识值。真实资料无匹配设备适用性时不借空device_ids宣称通用。
- [x] 评测输入：JSON list，case_id/question/split(dev或holdout)/answerable/expected_document_ids/expected_sections/required_evidence/forbidden_claims/category。检索命中默认按预先标注document+section证据判断，保存top5/top10真实候选；标注不适用不能算命中。answerable=false无具体目标，单独记录候选/人工相关性结果；不以总是topK等同有答案，也不无模型时宣称回答正确率。
- [x] 真实执行/报告：生成可复跑CLI、结果文件、索引清单；计实际文档/页数/片段/token、模型加载与耗时，保存失败样例。对比模型使用相同语料与问题；如果下载不可用报告原因，不假装已完成。

## 验证

先写失败测试再最小实现：元数据扩展兼容旧输入；不导入未列文件；长段切分覆盖、标题/适用范围/表格保留；超长错误；模型签名不匹配拒绝；索引重建删除旧文档；临时Chroma真实持久化与重启查询；top_k/过滤校验；距离排序含义；问题/答案不混入正文。用小文本的实际模型跑一次端到端，再对真实语料执行。必要依赖变更跑已有assistant/knowledge回归及完整Python回归一次；不触碰data和用户服务。

## 完成边界

交付真实来源、索引、只读检索及检索层证据。LLM回答、RAG助手UI、在线模型配置属于M4.3以后，本轮不宣称已实现。源库变化和中英文问题造成的失败如实保留，不为提高数字删掉难题。单独报告开发集/保留集，首次比较后保留集已被观察，下一轮需新保留题。

## 2026-09-18 完成记录

实际取得15份DOE指南/30页；固定44题评测；真实E5/BGE两套索引与CLI完成。196项Python测试通过（84.103秒），主任务另执行独立真实查询、冻结哈希与逐题计分复核。详见 `docs/verification/m4-real-rag/验收说明.md` 和 `集成复核.md`。

本计划完成指实验基线和证据交付，不表示检索质量已达可靠问答标准。E5保留集Hit@5为3/10、Hit@10为5/10；BGE为2/10、3/10。300-token目标仅软标记、复杂跨页条件仍需原文核查；同一来源系列与已观察保留集的限制均保留。未实现LLM回答或助手页面。
