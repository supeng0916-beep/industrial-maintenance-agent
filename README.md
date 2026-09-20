# 工业设备智能运维：双协议监控与只读智能助手

Modbus电机A四测点、OPC UA电机B温度、SQLite存储、持续超温告警、多设备看板，以及**实验性维护助手**（LangChain单Agent编排四只读工具：设备状态/历史/告警/DOE文档检索；DeepSeek云API或本地Ollama可切换；证据引用、预算与超时、注入隔离、拒答语义齐备）。数据来自本地教学仿真，不代表工业实测或生产可靠性；文档问答为实验性，候选须人工核对。

**快速开始与故障排查见[运行手册](docs/runbook.md)**（含助手 `.env` 配置：`ASSISTANT_MODEL/BASE_URL/API_KEY`，密钥永不入库）。**项目路线与全部实施记录见[项目计划v0.2](docs/project-plan-v0.2.md)文末**；助手端到端验收见 `docs/verification/m4-assistant-v1/`（24场景×36次真实运行，阻断项0违规）。

本README保留各阶段的历史命令和验收快照，下方早期“单点/双点”等描述属于对应阶段；当前采集器为四测点版本。双协议和订阅的独立启动见[订阅验收说明](docs/verification/opcua-subscription/验收说明.md)。另保留[独立OPC UA入门实验](experiments/opcua/README.md)与[跨寄存器编码实验](experiments/register_encoding/README.md)。功能自动验证和学习者独立掌握分别验收。

## 先打开看板：一个终端即可

在项目根目录运行（第一次先安装前端依赖）：

```bash
cd /Users/yuanqi/项目/工业设备智能运维agent
npm --prefix frontend ci
uv run --locked python run_dashboard.py
```

看到“看板已就绪”后打开 **http://127.0.0.1:5175**，并保持该终端运行。脚本统一启动本地模拟器、采集器、API 和前端，端口分别为15030、8010、5175；前后端共用 `data/dashboard-demo.sqlite3`，不会改动 `data/my-learning.sqlite3`。本命令已经负责采集，不要再对演示数据库额外启动一个采集器。

- 当前模拟温度为65.3℃。先按Ctrl+C停止，再运行 `uv run --locked python run_dashboard.py --raw 728` 可改成72.8℃，原历史保留。
- Ctrl+C仅停止这次启动的四个服务及子进程；重新启动会继续追加数据。课程结束时应停止，避免后台持续采集。
- 若5175被占用，使用 `--web-port 5176`；API与模拟器也分别支持 `--api-port` 和 `--modbus-port`。启动器会同步代理配置，不必手动修改前端。它不会关闭其他项目的服务。
- 四个组件的独立日志保存在 `data/dashboard-logs/<本次启动时间>/`。任一子服务退出时会报出日志位置并清理同次服务。
- 不要默认打开5173：该端口可能属于其他项目。以启动器实际输出的本机地址为准。
- 下方四终端方式保留给断线/恢复教学实验。两种启动方式择一使用；一键模式下主动停止某个子服务会使整个启动器退出，模拟断线请使用四终端方式。


## 1. 环境与第一次实验（原命令保留）

固定 Python **3.11.15**、PyModbus **3.11.3**；实测 uv **0.12.1**。SQLite 使用 Python 标准库，无需另外安装数据库服务。`.python-version` 固定解释器，`pyproject.toml` 与 `uv.lock` 固定第三方依赖。

两个终端都先进入项目；首次安装依赖：

```bash
cd /Users/yuanqi/项目/工业设备智能运维agent
uv sync --locked
```

终端 A 启动模拟器，保持运行：

```bash
uv run --locked python simulator.py
```

终端 B 读取一次：

```bash
uv run --locked python read_temperature.py
echo $?
```

默认输出 `原始值：653`、`倍率：0.1`、`温度：65.3℃`，退出码 0。在终端 A 按 Ctrl+C，然后运行 `uv run --locked python simulator.py --raw 728`，再次读取将得到 72.8℃。停止模拟器后读取，标准输出为空、标准错误报告“通信失败”，退出码 1。原三个验收测试仍然通过。

协议约定：本机 `127.0.0.1:15020`，设备 ID 1，保持寄存器协议地址 0，数量 1，无符号 16 位整数，倍率 0.1，单位 ℃。`--raw` 范围为 0～65535。端口占用时，两边同时加 `--port 15021`，无需 sudo。

## 2. 第二次实验：持续保存与查询

终端 A 运行模拟器，终端 B 运行采集器：

```bash
uv run --locked python collect_temperature.py --db data/measurements.sqlite3 --interval 1
```

它立即尝试第一次读取，之后约每秒一次。按 Ctrl+C 停止；已提交的历史保留。只启动一个采集器，避免自己重复采集。

也可以有限采集，方便实验：

```bash
uv run --locked python collect_temperature.py --db data/measurements.sqlite3 --interval 1 --count 5
```

- `--count 5` 表示 **5 次尝试，失败也计数**；默认 0 表示持续运行。
- `--interval` 是每轮起点之间的目标间隔，默认 1 秒。若请求耗时更长，不补发追赶；它不是硬实时采集。
- `--port` 默认 15020；`--db` 默认 `data/measurements.sqlite3`，相对路径以当前目录为准，采集器自动创建父目录和表。
- 每轮创建并关闭协议连接；请求超时 2 秒、请求重试 0 次。通信失败只写事件，下个周期重新尝试。
- 有限运行全部成功退出 0，出现过通信失败退出 1；数据库异常立即停止并退出 1；参数错误退出 2；Ctrl+C 退出 130。

另开终端（或有限采集完成后）查历史：

```bash
uv run --locked python query_history.py --db data/measurements.sqlite3 --limit 5
uv run --locked python query_history.py --db data/measurements.sqlite3 --events --limit 5
```

返回 JSON 数组。默认查询 `motor-a` 的 `temperature`，可用 `--device-id`、`--metric` 筛选。`--limit` 默认 10，允许 1～1000。**最新时间在前，同时间按 ID 降序**；无匹配返回 `[]`。查询只读打开已有文件，路径错误会报错，不会新建空库。查询不会启动采集。

### 断线、恢复与重启实验

1. 终端 A 用默认 653 启动模拟器，终端 B 启动持续采集器，观察“已保存”。
2. 只停止终端 A 的模拟器，保持采集器运行。查询测量数值与时间，应保持原记录；查询 `--events`，失败事件应增加。
3. 终端 A 用 `--raw 728` 重启模拟器。无需重启采集器，下一次成功请求会保存 72.8℃。
4. 停止并重启采集器，使用同一 `--db` 路径。再次查历史，旧记录应仍在，新记录继续追加。

成功读取到与上次相同的数值也会保存，因为它是一次新的实际请求。失败时没有测量记录，既不填 0，也不把上次温度换个时间重新写入。

## 3. 一条数据是什么

```text
模拟器寄存器 → 共用读取函数 → 采集循环 → SQLite → 只读查询命令
                          成功：measurements
                          失败：collection_events
```

`measurements` 除本地记录 ID 外，含下列统一字段：

| 字段 | 本次含义 / 示例 |
| --- | --- |
| device_id | 项目设备标识 `motor-a`，区别于 Modbus 设备 ID 1 |
| metric | 测点 `temperature` |
| value / unit | 换算后温度 `65.3` / `℃` |
| collected_at | 读取完成时的采集端 UTC 时间，如 `2026-09-16T03:33:53.436742+00:00` |
| source_time | `NULL`，本 Modbus 测点没有设备源时间 |
| quality | `good`，项目根据本次读取成功生成，非设备提供的质量码 |
| protocol | `modbus_tcp` |

`collection_events` 独立记录 `device_id`、`metric`、`occurred_at`、`event_type=communication_error`、`message`、`protocol`，不带测量值。两表都有设备/指标/时间索引。

写入使用参数化 SQL。每条记录在短事务内提交，网络请求和休眠都在事务外；SQLite 锁等待最多约 2 秒。写库失败明确报错并停止，已成功提交的记录保留；失败的写入不会被宣布为“已保存”。

## 4. 关键代码阅读顺序

| 文件与入口 | 学习重点 |
| --- | --- |
| `simulator.py:25` | `ModbusDeviceContext` 在本版本会把协议地址加 1，所以数据块内部索引 1 对应协议地址 0 |
| `modbus_reader.py:9` | 共用 `read_temperature()`：请求地址 0、检查响应、乘 0.1 并保留一位小数，最终关闭连接 |
| `read_temperature.py:18` | 一次性客户端调用共用函数，原命令与输出保持兼容 |
| `collect_temperature.py:21` | 循环中成功写测量、失败写事件；`time.monotonic()` 计算间隔 |
| `collect_temperature.py:17` | `datetime.now(timezone.utc)` 生成带时区 UTC 时间；它是采集时间，不是设备源时间 |
| `storage.py:46` | `with conn` 提交/回滚单条参数化 INSERT；它不会关闭连接 |
| `collect_temperature.py:59` | `closing(...)` 在结束或异常时关闭数据库连接 |
| `storage.py:65` | 筛选设备/测点、时间降序、LIMIT 限量查询 |
| `query_history.py:25` | `mode=ro` 只读连接，独立于采集器 |

## 5. 真实验收（AI 执行，2026-09-16）

默认端口、默认 1 秒间隔的命令与完整原始输出见 [验收日志](docs/verification/2026-09-16-collection-transcript.txt)。数据库保存在本机 `data/acceptance-20260916T033353Z.sqlite3`。

| 步骤 | 实测结果 |
| --- | --- |
| 启动默认 653，持续采集 | 前两条 65.3℃；UTC 时间为 03:33:53.436742、03:33:54.440551，间隔约 1.004 秒 |
| 停止模拟器，采集器继续 | 第 3、4 次失败；测量保持 2 条，新增 2 条独立失败事件 |
| 同端口以 728 重启模拟器 | 同一个采集进程第 5～8 次成功，新增 4 条 72.8℃ |
| 有限 8 次结束 | 总计成功 6、失败 2，退出码 1（因为出现过失败） |
| 同库重启采集器，`--count 2` | 追加 2 条；旧 6 条逐字段保留，总计 8 条，退出码 0 |
| 查询 `--limit 3` | 返回 ID 8、7、6；`--events --limit 3` 返回事件 ID 2、1 |

重复自动验收：

```bash
uv run --locked python -m unittest discover -s tests -v
```

第二次增量实测 **8 个测试通过，耗时 4.399 秒**：原三个实验，加连续 UTC 记录/重启保留/限量查询、同进程断线恢复、失败尝试计数、参数与路径错误、运行期间写入失败与锁超时。测试使用临时数据库和真实进程，不修改教学数据库；耗时每次会变化。第三次增量后最新完整结果见第 8 节。

此次证据为 AI 运行所得，不代表学习者已经亲自完成实验。`docs/learning` 由主任务维护，本次未修改。

## 6. 官方参考

- [PyModbus 3.11.3 客户端](https://pymodbus.readthedocs.io/en/v3.11.3/source/client.html)与[服务端](https://pymodbus.readthedocs.io/en/v3.11.3/source/server.html)：固定版本接口。
- [v3.11.3 地址转换源码](https://github.com/pymodbus-dev/pymodbus/blob/v3.11.3/pymodbus/datastore/context.py)：内部 `address += 1`。
- [Python 3.11 sqlite3 文档](https://docs.python.org/3.11/library/sqlite3.html)：参数占位符、事务、锁等待及只读 URI。`with conn` 管理事务，连接需另行关闭。

## 7. 第三次实验：FastAPI 只读后端

新增固定依赖 **FastAPI 0.141.1、Uvicorn 0.53.0**；测试使用 **httpx2 2.13.0**（本次锁定的 Starlette TestClient 所需）。全部传递依赖也在 `uv.lock` 中固定。先运行 `uv sync --locked`。

### 启动和请求

在项目目录另开终端，只启动后端：

```bash
uv run --locked python serve_api.py --db data/measurements.sqlite3 --port 8000 --stale-after-seconds 5
```

`--db` 应与要查看的采集库一致；后端只读，绝不自动创建库或启动采集器。默认仅监听 `127.0.0.1`。修改端口时同步修改下方 URL。

```bash
curl -sS http://127.0.0.1:8000/api/devices
curl -sS http://127.0.0.1:8000/api/devices/motor-a/latest
curl -sS -G http://127.0.0.1:8000/api/devices/motor-a/history \
  --data-urlencode 'metric=temperature' \
  --data-urlencode 'from=2026-09-16T13:00:00+08:00' \
  --data-urlencode 'to=2026-09-16T14:00:00+08:00' \
  --data-urlencode 'limit=20'
```

历史例子的时间需改为数据所在时段，空时段返回空数组。使用 `--data-urlencode` 可避免时区中的 `+` 被当作空格。接口参数也可在本机 `/docs` 页面查看。

### 返回结构

| GET 接口 | JSON 顶层结构 |
| --- | --- |
| `/api/devices` | `devices` 数组，每项含 `id`、`name`、`protocol`、`metrics`、`status` |
| `/api/devices/motor-a/latest` | `device_id`、`metric`、`measurement`（原八字段及 ID，或 null）、`status` |
| `/api/devices/motor-a/history` | `device_id`、`metric`、`from`、`to`、`limit`、`order`、`points`（测量记录数组） |

`status` 在设备列表和最新值接口中使用同一规则：

| 字段 | 含义 |
| --- | --- |
| `has_data` | 是否有成功测量记录 |
| `last_attempt_status` | 数据库中最近一次采集尝试结果：`success` / `failure` / `unknown` |
| `last_attempt_at` | 上述尝试发生时间，无记录为 null |
| `last_success_at` | 最后一次成功测量的原始时间，无成功为 null |
| `last_failure_at` | 最近通信失败事件时间，无失败为 null；恢复后仍保留这一历史信息 |
| `data_age_seconds` | 本次检查时间减最后成功时间，无样本为 null |
| `is_stale` | 年龄 **大于** 阈值才为 true，恰好 5 秒不算过期；无样本为 null |
| `checked_at` | 后端计算状态时的 UTC 时间 |
| `stale_after_seconds` | 本服务配置的过期阈值，默认 5 |

比较成功与失败的**记录时间**，不比较跨表 ID，也不因为存在失败事件就判定最近尝试失败。两种记录时间恰好相同，无法确定先后，返回 unknown。时间均为带时区 UTC。

**最近尝试结果是历史观测，不是实时在线或健康证明。** 最后一次成功但已长期无更新时，仍可同时出现 `last_attempt_status=success` 和 `is_stale=true`。过期不能直接证明设备断线，也不能识别采集器是否停止；本次没有心跳机制或 `connection_status` 字段。旧测量的值、`collected_at` 和 `quality=good` 保持原样；good 只说明那次采样成功。默认假设采集端与服务系统时钟一致，负的数据年龄提示时钟/记录异常，不能解读为在线证明。

### 历史约束和错误

- `metric` 默认且仅支持 `temperature`。
- `from`、`to` 必填，必须是带时区的 ISO 日期时间；不同 offset 先转 UTC 再比较。范围是包含两端的闭区间，最长 24 小时；相同起止时刻合法。
- `limit` 默认 100，允许 1～1000。按 `collected_at ASC, id ASC` 返回范围内最早的至多 limit 条；不会暗示这是范围内全部记录。与 CLI 的最新在前排序不同。
- 复用采集器的固定微秒精度 UTC 存储格式；不支持往库中手写另一种时间格式。查询输入会规范为该格式，以使用设备/指标/时间索引。
- 所有错误均为 `{"error":{"code":"...","message":"..."}}`：未知设备 404；非法指标、日期、时间范围、条数等 422；数据库缺失、锁等待超时、表未就绪或数据库错误 503。使用 `curl -i` 查看 HTTP 状态码。
- 先启动服务而库未创建时返回明确 503；采集器后来建库后，下一次请求即可正常查询，不用重启后端。

每个请求独立用 `mode=ro` 打开 SQLite，结束时关闭。最新值和失败事件在一个短只读快照中查询；历史使用参数化 SQL 和索引，锁等待约 2 秒。请求不修改数据、不连接 Modbus、不启动采集。服务终端的 Uvicorn 日志记录 URL/状态码，数据库具体错误也记录在服务日志中。

## 8. 后端实测与教学入口

2026-09-16 完整运行 **15 项测试通过（9.276 秒）**，保留原 8 项。见 [完整测试与 HTTP 服务日志](docs/verification/2026-09-16-api-transcript.txt)。

| 真实 HTTP 验收 | 结果 |
| --- | --- |
| 临时库不存在，启动本机端口 57048 | 503，未创建数据库 |
| 创建空表后再次请求，同一服务进程 | 200，measurement=null，状态 unknown，年龄/过期均 null |
| 测试库写入旧 65.3℃ | 原时间保留，年龄 10.001339 秒，is_stale=true，最近尝试 success |
| 写入更新的失败事件，再写成功 72.8℃ | 最近结果 success → failure → success，最近失败时间仍保留 |
| 4 个线程共 12 次并发 HTTP 请求 | 全部 200，数据库文件逐字节不变 |
| 历史 limit=1 / 未知设备 / 参数错误 | 分别 200（1条）/404/422 |
| 测试连接持有独占锁 | 503；解除后恢复 200 |

HTTP 验收直接在独立临时库中注入已知记录，检验后端语义；协议真实通信另由保留的采集测试覆盖。所有临时测试库与服务进程都已清理，未使用或修改 `data/my-learning.sqlite3`，未修改 `docs/learning`。上述新后端验证由 AI 执行。你此前亲自完成的读取、采集、断线和恢复实验与本次验证分别记录。

关键阅读入口：

- `api.py` 的 `observation_status()`：成功/失败时间比较与过期严格大于判断。
- `api.py` 的 `create_app()`：统一错误处理及三个 GET 路由。
- `storage.py` 的 `open_readonly_database()`、`latest_observations()`：只读连接和一致快照。
- `storage.py` 的 `history_between()`：闭区间、排序、LIMIT 和 SQL 参数。
- `serve_api.py`：独立服务入口，无采集循环。
- `tests/test_api.py`：固定时钟验证恰好5秒、不同offset和失败恢复；`tests/test_api_http.py`：真正启动服务并发送HTTP请求。

官方参考：[FastAPI 错误处理](https://fastapi.tiangolo.com/tutorial/handling-errors/)、[服务启动](https://fastapi.tiangolo.com/deployment/manually/)、[测试说明](https://fastapi.tiangolo.com/tutorial/testing/)。独立代码审查未发现待修复项。

## 9. M1 中文温度看板：四终端运行

前端目录 `frontend`，使用 **React 19.3.0、TypeScript 7.0.2、Vite 8.3.0、ECharts 6.1.0**，精确版本及传递依赖见 `package.json` / `package-lock.json`。实测 Node **26.6.0**、npm **11.18.0**；Vite 官方要求 Node 20.19+ 或 22.12+，本项目 `engines` 已注明兼容范围。

首次安装：

```bash
cd /Users/yuanqi/项目/工业设备智能运维agent
uv sync --locked
cd frontend
npm ci
```

以下用独立演示数据库 `data/dashboard-demo.sqlite3`，避免混入已有学习记录。采集器和 API **必须指向同一个数据库**。示例端口为15030/8010/5173；占用时改端口并同步相关命令，不要停止别人的进程。

### 终端 1：模拟设备

```bash
cd /Users/yuanqi/项目/工业设备智能运维agent
uv run --locked python simulator.py --port 15030
```

### 终端 2：持续采集

```bash
cd /Users/yuanqi/项目/工业设备智能运维agent
uv run --locked python collect_temperature.py --port 15030 --db data/dashboard-demo.sqlite3 --interval 1
```

### 终端 3：只读 API

```bash
cd /Users/yuanqi/项目/工业设备智能运维agent
uv run --locked python serve_api.py --db data/dashboard-demo.sqlite3 --port 8010
```

### 终端 4：前端开发服务

```bash
cd /Users/yuanqi/项目/工业设备智能运维agent/frontend
API_PROXY_TARGET=http://127.0.0.1:8010 npm run dev -- --port 5173
```

打开 [本机温度看板](http://127.0.0.1:5173)。Vite 将 `/api` 代理给 `API_PROXY_TARGET`；未设置时默认 `http://127.0.0.1:8000`，也可写入 `frontend/.env.local` 后重启 Vite。代理端口是后端端口，不是 Modbus 端口。无需修改后端 CORS。生产构建只生成静态文件，正式托管时仍需同源API代理；本次未部署。

### 页面如何表达状态

- 先读设备列表选择 `motor-a`，然后获取最新值和最近10分钟历史。整轮请求成功后才替换页面快照；每轮结束2秒后再开始下一轮，不重叠。
- 页面明确显示初次加载、无样本（—）、数据未过期/过期、最近采集失败、接口请求失败。后端状态是检查时的状态，数据年龄标为“查询时”。
- 请求失败保留最后温度、原时间与曲线，同时显示“当前状态未能核实”和前端最后获取成功时间。距离前端最后获取成功超过6秒也显示待核实，不能把旧绿色状态无限保留。网络请求8秒超时，卸载页面会取消请求和定时器，迟到响应不会覆盖新状态。
- 最近成功不代表在线；过期不等于断线；good不代表设备健康。前端不推断采集器是否存活。
- 原采集UTC时间在页面转为浏览器本地时间；不会因刷新改变原时间。
- 曲线用真实时间坐标、真实样本，单点可见，固定值Y轴留出空间，不补0或生成插值样本。默认每秒采集时，相邻记录超过 **1.5秒**即断开连线；空标记只是绘图分隔，不是数据库测量。这个保守显示阈值不是断线诊断；改变采集间隔后需相应调整 `model.ts` 中的阈值。
- 历史请求以服务端 `checked_at` 为窗口终点，跨度10分钟、升序、limit1000，覆盖默认每秒采集约600条。达到1000条会明确提示可能截断；更高采样频率尚未做分页。

### 你可以亲自复现

1. 四个服务启动后，确认页面显示65.3℃和新增曲线点。
2. 只停止终端1，观察最近尝试失败、稍后数据过期。温度和原采集时间应保留。
3. 终端1改用 `uv run --locked python simulator.py --port 15030 --raw 728`，观察页面更新为72.8℃，长缺口两端不连线。
4. 只停止终端3，观察页面提示“接口请求失败/当前状态未能核实”；用同一命令重启，页面恢复且历史保留。
5. 再开一个浏览器页面并刷新，观察采集器仍约每秒一次；页面只读，不创建采集任务。

### 验证命令与教学代码

```bash
# 项目根目录：原有17项后端、Modbus和独立OPC UA测试
uv run --locked python -m unittest discover -s tests -v

# frontend目录
npm test
npm run check
npm run build
node scripts/verify-dashboard.mjs
```

浏览器验收脚本启动独立空闲端口、临时SQLite库和自己的服务，最终关闭进程并删除临时库。默认调用 macOS 的 `/Applications/Google Chrome.app/Contents/MacOS/Google Chrome`；其他位置用 `CHROME_PATH` 指定。脚本只创建自己的无头浏览器，不操作用户已有窗口或服务。

- `frontend/src/useDashboard.ts:14`：三个只读接口与10分钟时间窗口。
- `frontend/src/poll.ts:2`：无重叠轮询、超时和卸载取消。
- `frontend/src/App.tsx:11`：接口状态未核实与保留历史快照。
- `frontend/src/model.ts:23`：曲线缺口分隔；`TemperatureChart.tsx:20`：ECharts时间轴和固定值范围。
- `frontend/vite.config.ts`：本机API代理。

官方依据：[Vite安装要求](https://vite.dev/guide/)、[开发代理配置](https://vite.dev/config/server-options.html#server-proxy)、[React Effect清理](https://react.dev/reference/react/useEffect)、[ECharts图表尺寸与销毁](https://echarts.apache.org/handbook/en/concepts/chart-size/)。

### M1 功能验收结果（AI执行，2026-09-16）

完整原始结果见 [浏览器验收报告](docs/verification/dashboard/report.txt) 和 [服务日志](docs/verification/dashboard/process-logs.txt)；[桌面截图](docs/verification/dashboard/desktop.png)、[窄屏截图](docs/verification/dashboard/narrow.png)、[后端不可用截图](docs/verification/dashboard/api-unavailable.png)。

实测环境：macOS Apple Silicon、Node26.6.0、Chrome152.0.7977.76；最终一轮使用独立端口62270/62271/62272和临时数据库。

| M1验收项 | 实际结果 |
| --- | --- |
| 653原始值贯通数据库与页面 | 页面65.3℃，原时间本地显示，真实曲线加载；通过 |
| 温度变化与显示延迟 | 改728并重启模拟器，页面72.8℃；从启动模拟器（含启动耗时）到页面显示 **1613ms**，本次小于5秒；通过 |
| 停止模拟器后保留历史且标记异常 | 测量保持11条；页面原值65.3和采集时间不变，显示最近失败和数据过期；通过 |
| 后端重启历史保留 | 停后端时未核实提示明确，同库重启后原17条逐字段保留、页面恢复；通过 |
| 第二页面/刷新不增加采集频率 | 单页4.2秒新增5条，双页含刷新约4.2秒新增4条，相邻记录仍约1秒；通过 |
| 学习者独立解释每一步 | 本次不代为声称完成；由主学习任务继续操作、讲解与修改练习 |

桌面1440px和窄屏390px已真实渲染并检查，窄屏无横向溢出。未捕获JavaScript异常0，正常阶段console.error为0；主动停后端期间有2条预期网络错误。原17项Python测试通过（13.141秒）；前端6项状态/时间转换/轮询测试通过，TypeScript检查与生产构建通过。构建有单个约731KB压缩前JS包的体积提醒（gzip约243KB，主要含图表库），本地教学可用，本次未做部署体积优化。

局限：仅单设备温度；非实时工业监控；轮询刷新和后台标签页节流会影响延迟，1613ms仅是本次本机实测；曲线缺口阈值针对默认1秒采集，高频历史超过1000条只提示截断；没有设备在线检测、告警或生产认证。所有测试进程已清理，未动用户学习数据库和学习笔记，独立OPC UA实验保持原样。

## 温度回差告警（M2 第一小步）

新版采集器对新温度执行教学规则：大于80℃触发，已报警时小于78℃恢复，等于阈值保持。连续高温只保留一次告警；失败或过期显示当前未知，不能解除告警。页面增加告警状态和最近20条证据，GET接口保持只读。

旧库需由新版采集器启动后启用规则，不回放历史测量。正在运行的旧进程不会自动加载新Python代码。独立练习命令、验收结果及关键代码位置见[告警验收说明](docs/verification/alarms/验收说明.md)。这一步尚不包含持续超限和多测点。

### 持续超限确认（M2 下一小步，当前新版规则）

新版采集器将首次触发改为：>80℃观测连续至少5秒；≤80℃、失败、样本长间隙、采集器重启都重新累计。已报警仍需新温度<78℃恢复。默认1秒采集允许相邻有效样本最多间隔1.5秒；页面只读显示后端已累计时长。旧即时告警保留原语义，GET不迁移。详见[持续告警验收说明与独立练习命令](docs/verification/sustained-alarms/验收说明.md)。

### 温度＋电流（M2 下一小步，2026-09-17）

新版模拟器提供holding地址0温度、地址1电流，新采集器一次读两个寄存器；`[653,123]`对应65.3℃、1.23A。同轮两条测量和温度告警同事务，失败整轮回滚。电流仅观测，页面可切换独立单位的历史曲线。启动器新增 `--current-raw`（默认123）。旧单次温度CLI保留，新采集器必须搭配双寄存器模拟器。

见[点位表](docs/protocols/点位表.md)和[双测点验收说明、API契约与独立练习命令](docs/verification/two-points/验收说明.md)。未扩展转速、运行状态或电流告警，不代表整个M2完成。

### 转速＋运行状态（M2 下一小步，2026-09-17）

当前新版一次读取四个保持寄存器，新增地址2转速（rpm）和地址3运行状态。**正式状态枚举仅0＝停止、1＝运行；此前教学“2＝故障”仅为示例，未采用。** 2/7属于数据校验失败，不是通信失败；本项目选择整轮拒存四测量，失败证据保留原始值，取消温度pending并保留active及旧测量时间。页面区分当前未知与最后有效运行记录，运行状态历史用记录表。

新增启动参数 `--speed-raw`（默认1450）、`--running-state-raw`（默认1，允许2/7做故障注入）。新版collector需要四寄存器模拟器；旧温度CLI仍可单点读取。详见[正式点位表](docs/protocols/点位表.md)与[四测点验收及独立练习命令](docs/verification/four-points/验收说明.md)。

### OPC UA 电机B主动读取（M3 第一小步，2026-09-17）

新增独立 `opcua_simulator.py` 和 `collect_opcua.py`，将电机B的Double温度接入统一数据库、持续温度告警、只读API和设备切换看板。仅Good、源时间存在且足够新并严格递增的测量可参与；Bad/Uncertain及缺失、过旧、未来、重复、倒退源时间只保存诊断，取消待确认但保留已激活告警。通信、质量、源新鲜度分别展示，接收时间不替代源时间；A的Modbus语义保持。

正式模拟器每0.5秒产生源测量，采集器默认每1秒主动读，默认源年龄上限5秒，假设双方UTC时钟同步。现有 `run_dashboard.py` 仍启动A；B的独立启动、同库双设备、故障注入命令和限制见 [M3第一步验收说明](docs/verification/opcua-motor-b/验收说明.md)。此步不含正式订阅/订阅恢复，不代表整个M3完成，旧独立OPC UA实验不变。

### OPC UA 正式订阅与断线重建（M3 后续，2026-09-17）

`collect_opcua.py --mode subscribe` 使用持久连接、单订阅和单监控项；`--mode read`（默认）保留主动读取对照。同值新源时间也产生通知，断线后按有界退避创建新连接世代和新订阅。通知身份去重、旧世代屏蔽、有界队列和专用数据库线程保护采集链，GET保持只读。

页面独立显示模式、订阅状态、保活、数据通知及服务端修订参数。保活不能当温度；重复投递不影响pending，新的通知若源时间重复仍按既定保守规则取消pending。订阅在取得数据库写锁后重新核对源年龄，保留真实接收时间和判定时间；排队后过期不能推进或解除告警。

独立练习命令、去重边界、故障注入、验证记录及限制见[订阅验收说明](docs/verification/opcua-subscription/验收说明.md)。同库B的read/subscribe应二选一，先停自己的旧采集器再切换。本步不保证断线补采、所有静默丢采可检测或生产可靠性。

### 三个只读业务工具（M4.1，2026-09-17）

新增 `get_device_status`、`query_metric_history`、`list_alarms`，通过 `python -m assistant` 或 Python 调用，无需模型。API 与工具共用状态事实；历史统计覆盖完整查询区间，明细最多1000条；告警按持续区间相交查询，并区分范围计数与设备全历史计数。失败和未核实仍保留最后有效记录。

参数、CLI 命令、只读快照、查询预算、结果限制和验收证据见 [M4.1验收说明](docs/verification/m4-readonly-tools/验收说明.md)。本步未接入模型、RAG 或助手界面。

### 真实资料本地索引与检索（M4.2，2026-09-18）

新增 `python -m assistant.rag build/query/evaluate`，只从manifest白名单读取资料，使用固定版本的真实E5或BGE权重在本地嵌入，并建立显式cosine距离的Chroma持久化索引。模型配置签名必须一致，更新资料通过全量新目录重建，旧索引不覆盖。查询返回原文、页码、来源与上下文，不生成诊断回答。

本批使用15份DOE英文电机系统指南、30物理页，配套44题中文检索问题。最终索引路径、两模型成绩、运行命令、证据匹配口径和局限见[真实RAG基线验收说明](docs/verification/m4-real-rag/验收说明.md)。没有LLM回答、自动无答案判定或回答准确率；未录入型号的资料不能当作所有设备通用手册。
