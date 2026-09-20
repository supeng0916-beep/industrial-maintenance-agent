# 交付清单（最终自查）

逐项可勾选的最终状态。任何"否"都意味着交付不完整，如实处理后才能勾。

## 功能

- [x] Modbus四测点采集+SQLite+持续超温告警（回差/待确认/去重）
- [x] OPC UA温度（read/subscribe二选一、质量与源时间校验、断线重连与重复投递防护）
- [x] 只读API与看板（多设备、新鲜度/历史/告警如实呈现）
- [x] 四只读工具（status/history/alarms/DOE文档检索）+ 单Agent编排（预算/超时/白名单/引用校验）
- [x] 助手聊天API（严格schema、单飞、503语义）与前端助手面板（六状态、候选原文、来源链接）
- [x] 双供应商适配：DeepSeek云API（主）+本地Ollama（无网备胎），配置仅经后端环境

## 验收证据（全部真实运行、退出码与哈希留档）

- [x] 检索：D1改写诊断+D2三套题集（旧集逐题复现；新检查集首测）→ `docs/verification/m4-rag-improvement-{v1,v2}/`
- [x] 流程：四类调用云/本地双路线 → `docs/verification/m4-agent-real/`
- [x] 端到端：24场景×36次，六类阻断项0违规，人工复核24条 → `docs/verification/m4-assistant-v1/`
- [x] 前端：三检+浏览器三条实测（截图） → `docs/verification/m4-assistant-frontend/`
- [x] 回归：Python 292项（真实嵌入）+ 前端47项
- [x] 每项成绩均链接证据路径；无"测试通过"冒充检索/回答质量

## 安全与纪律

- [x] 密钥只在.env/后端环境；.gitignore覆盖.env/data/*.sqlite3/.venv；验收产物零密钥
- [x] 只读边界由程序强制（白名单+参数白名单），D9注入场景0越权
- [x] 既有题集/索引/成绩零覆盖（全部新目录新文件，冻结哈希校验）
- [x] 未宣称：文档问答可靠、一般工业可靠性、D9前"验收通过"（历史勾选记录可查）

## 文档

- [x] README（入口+助手说明）、runbook（启动/配置/排查）、demo-script（15分钟演示）
- [x] final-report（架构/三层评测/失败案例/限制）、project-plan-v0.2（全程实施记录）
- [x] 12工作包计划全部勾选并附证据路径；学习线文档在docs/learning（另线维护）

## 已知限制（不因交付而隐藏）

- [ ] 文档问答标"实验性"：小语料（15份DOE英文指南）、中文检索语言差、候选须人工核对——**保持此状态，不得宣称可靠问答**
- [ ] 观察项：拒答场景状态徽章多为answered（依赖模型自评）；citations需程序兜底；详见D9报告
- [ ] Vercel仅前端，后端部署由项目所有者自理（密钥不入库已保证）

## 上线前最后一步（项目所有者执行）

1. 确认`.env`存在且有效（本地已配DeepSeek）。
2. `git add -A && git commit`（仓库已初始化，见提交记录）后推送到GitHub（Vercel已绑定）。
3. 后端按runbook部署到可达地址，并配置前端`API_PROXY_TARGET`或Vercel rewrite。
