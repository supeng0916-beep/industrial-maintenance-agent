# 运行手册（Runbook）

本文档给出从零启动到完整演示的复现步骤、故障排查与端口/路径约定。命令均以项目根目录为工作目录。所有服务只监听本机（127.0.0.1）。

## 0. 环境准备（一次性）

```bash
# Python 3.11.15（.python-version 固定）；首次安装依赖
uv sync --locked
# 前端依赖（首次）
npm --prefix frontend ci
```

助手模型（可选，不配置则助手接口返回503、监控功能不受影响）：复制 `.env.example` 为 `.env` 并填三个变量——

```bash
ASSISTANT_MODEL=deepseek-chat
ASSISTANT_BASE_URL=https://api.deepseek.com/v1
ASSISTANT_API_KEY=<你的key>   # https://platform.deepseek.com 获取；.env已被.gitignore挡住
```

- 供应商可换任何OpenAI兼容端点（智谱/其他）：改 `ASSISTANT_BASE_URL` 与模型名即可，适配器通用。
- 本地Ollama路线（无网备胎）：仅填 `ASSISTANT_MODEL=<本地模型名>` 并保持Ollama服务运行（`ollama serve`，默认11434）；不需要key。
- 密钥只放 `.env`/后端环境；浏览器与chat请求永远无法传入或覆盖。

## 1. 快速启动（推荐：一条命令看板）

```bash
uv run --locked python run_dashboard.py
```

统一启动模拟器(15030)、采集器、API(8010)、前端(5175)；共用演示库 `data/dashboard-demo.sqlite3`（不碰 `data/my-learning.sqlite3`）。要启用助手问答，改用：

```bash
uv run --locked python serve_api.py --port 8010 &   # 读取.env装配助手
API_PROXY_TARGET=http://127.0.0.1:8010 npm --prefix frontend run dev -- --port 5175
```

（或设 `ASSISTANT_MODEL` 环境变量后运行 `run_dashboard.py` 亦可；助手面板在右侧"值班终端"侧栏。）

### 1.1 数据集回放（motor-c，真实公开数据）

```bash
uv run --locked python run_dashboard.py --with-replay --replay-interval 0.5
```

额外启动 AI4I 2020 回放器（motor-c）：逐行回放 UCI 合成数据集（CC BY 4.0，10000行，SHA256 固定校验），提供温度/空气温度/转速/扭矩/刀具磨损/运行状态六指标与数据集标注故障史。**诚实边界**：时间为回放时刻非原始采集时间；数据为合成数据，页面与助手都会标注；回放停止后如实显示"已过期"。单独运行：`uv run --locked python replay_ai4i.py --db data/dashboard-demo.sqlite3 --interval 0.5 --from-row 0`。数据集登记：`docs/datasets/ai4i-2020/README.md`。

## 2. 组件职责与启动顺序

| 组件 | 命令 | 端口 | 职责 |
| --- | --- | --- | --- |
| Modbus模拟器 | `uv run --locked python simulator.py` | 15030 | 电机A四测点仿真（温度可调） |
| 采集器 | `uv run --locked python collect_temperature.py` | - | 1秒轮询写入SQLite |
| OPC UA（电机B） | `opcua_simulator.py` + `collect_opcua.py --mode read\|subscribe`（二选一） | 4840 | 温度单测点；read/subscribe互斥 |
| 数据回放器（电机C） | `uv run --locked python replay_ai4i.py`（或 run_dashboard --with-replay） | - | AI4I 2020 合成数据集历史回放 |
| API | `uv run --locked python serve_api.py --port 8010` | 8010 | 只读查询+助手chat（助手与 --db 同库） |
| 前端 | `npm --prefix frontend run dev -- --port 5175` | 5175 | 看板+助手面板 |

启动顺序：模拟器→采集器→API→（可选回放器）→前端（`run_dashboard.py` 自动处理）。OPC UA同一设备 read/subscribe 二选一，勿同时跑。

## 3. 助手与知识库

- 文档索引：`docs/verification/m4-real-rag/doe-e5-final`（E5嵌入，113块，只读）。可用 `ASSISTANT_INDEX` 覆盖路径。
- 业务库：默认 `data/` 下默认库；可用 `ASSISTANT_DB` 覆盖（演示用独立库时）。
- 只读边界：助手仅四个工具（get_device_status / query_metric_history / list_alarms / search_maintenance_docs）；无任何写操作。
- 检索质量现状：`docs/verification/m4-rag-improvement-v2/report.md`（旧开发集Hit@5=15/24、新检查集10/14；文档问答为实验性，候选须人工核对）。

## 4. 故障排查

| 症状 | 检查命令 | 恢复 |
| --- | --- | --- |
| 助手503 assistant_unavailable | `grep ASSISTANT .env`（key/模型名是否填、有无多余引号） | 修 `.env` 后重启 serve_api；DeepSeek常见401=key错或模型名不匹配 |
| 助手503 assistant_busy | （上一条仍在处理） | 稍等重试；单飞设计，不排队 |
| 前端助手"无法连接后端" | `curl -s http://127.0.0.1:8010/api/devices` | 后端未起或代理目标不符；检查API_PROXY_TARGET |
| 看板无数据 | `ls data/`、采集器终端日志 | 采集器与API须共用同一数据库；首次采集需数秒 |
| 端口占用 | `lsof -i :8010 -i :5175 -i :15030` | 换端口参数（--port/--api-port/--web-port）；**不要杀未知进程** |
| GitHub 每次推送都出现 Vercel 失败检查 | Vercel 控制台项目列表（是否同名项目带 -xxxx 后缀） | 同一仓库被重复导入成两个 Vercel 项目；删除配置错误的多余项目，保留 Root Directory=frontend 的那个；历史提交上的旧红叉不会消失，新推送起即干净 |
| 索引校验失败 | 比对 `docs/verification/m4-real-rag/final-integrity.json` 哈希 | 索引目录被改动时按M4.2流程重建到新目录，勿覆盖 |
| 数据库路径不符 | 启动日志中的db路径 | 显式传 `--db`；演示库与学习库隔离 |
| 历史查询丢首点 | 采集器写入须微秒精度ISO（现版本已如此） | `storage.history_between` 依赖统一文本比较；勿用无微秒格式手工插数据 |

## 5. 测试与验收复现

```bash
# Python全量（含真实嵌入，约80秒）
RUN_REAL_EMBEDDINGS=1 .venv/bin/python -m unittest discover -s tests
# 前端三检
npm --prefix frontend test -- --run && npm --prefix frontend run check && npm --prefix frontend run build
# 助手端到端（真实模型，24场景）
.venv/bin/python experiments/assistant_e2e.py --output <新目录>
# 四类调用真实验收
.venv/bin/python experiments/agent_real_acceptance.py --output <新目录>
```

真实模型测试需要 `.env` 有效key，会产生少量按量费用；单测默认不打真实模型（RUN_REAL_MODEL=1单独门控）。

## 6. 停止与清理

`run_dashboard.py` 用Ctrl+C整体停止；手动启动的服务各自Ctrl+C。课程结束后停止采集，避免后台写入。删除演示数据：`rm data/dashboard-demo.sqlite3`（学习库勿删）。
