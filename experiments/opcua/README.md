# 独立 OPC UA 小实验

使用 **Python 3.11.15 + asyncua 2.0.1**，版本固定在项目 `pyproject.toml` / `uv.lock`。本实验只学习节点读取和订阅，未接入现有 Modbus 采集器、数据库或 HTTP API，也不是完整 M3。

## 1. 地址空间与边界

| 项目 | 约定 |
| --- | --- |
| 本地端点 | `opc.tcp://127.0.0.1:4840/opcua-lab/` |
| 命名空间 URI | `urn:industrial-maintenance:opcua-lab` |
| 对象标识符 / 浏览名 | `MotorA` / `MotorA` |
| 变量标识符 / 浏览名 | `MotorA.Temperature` / `Temperature` |
| 节点类型 / 值类型 | 普通变量 / Double |
| 初始工程值 | 65.3，文档约定单位 ℃；不乘倍率 |

客户端每次连接先用 URI 查询命名空间索引，再构造字符串 NodeId。默认通常显示 `ns=2;s=MotorA.Temperature`，但不要把 2 当成长期标识。

本阶段**没有暴露可浏览的 EngineeringUnits 属性**。输出中的 `UnitConvention` 是客户端按文档补充的说明，不是从标准单位属性读出的元数据，也不是倍率。

服务仅绑定本机回环地址，启用 NoSecurity 和匿名身份。没有认证、加密或生产授权保护，本机其他进程也可能写变量。设温命令仅用于这个教学模拟器，不能作为工业设备控制工具；命令只接受端口，不接受远程主机。不要把服务改为公网监听。

## 2. 三个终端完成一次实验

所有终端先进入项目目录；首次同步依赖：

```bash
cd /Users/yuanqi/项目/工业设备智能运维agent
uv sync --locked
```

### 终端 A：服务端

```bash
uv run --locked python -m experiments.opcua.server
```

看到 `event=server_ready` 后继续。服务端初值为65.3，不自动升温，只有设温命令才改变温度；重启会重置为65.3。

### 终端 B：主动读取，然后持续订阅

```bash
uv run --locked python -m experiments.opcua.client read
uv run --locked python -m experiments.opcua.client subscribe
```

读取会输出一行 JSON，包含解析后的 NodeId、Value、DataType、StatusCode/数值、SourceTimestamp、ServerTimestamp。`null` 明确表示没有该时间。

订阅进程建立 **1 个订阅、1 个温度监视项**，通常首先输出当前值通知。回调还输出 `ReceivedAt`（客户端收到通知的 UTC 时间）。让这个终端保持运行，勿重复启动多个订阅进程来模拟“重连”。

### 终端 C：仅设定本地教学温度

```bash
uv run --locked python -m experiments.opcua.client set-temperature 72.8
uv run --locked python -m experiments.opcua.client read
```

预期：终端 B 收到72.8的数据变化通知；主动读取显示72.8、Double。即使输入整数 `73`，设温客户端也显式写为 Double；NaN/Infinity 被拒绝。

再写一次相同值：

```bash
uv run --locked python -m experiments.opcua.client set-temperature 72.8
```

观察终端 B 一两秒。默认关注状态和值变化，单独时间变化不会触发该数据变化回调，因此同值写入不保证出现新通知。无通知不能直接判定断线。

结束时先在终端 B 按 Ctrl+C：正常清理会输出 `subscription_deleted`，随后关闭连接，退出码130。再在终端 A 按 Ctrl+C 停止自己的模拟器。服务器已经不可达时，删除订阅可能失败并报通信错误；本实验未实现自动重连，需要重新启动客户端。

端口被占用时，给三种客户端命令和服务端都加相同 `--port 4841`，不要停止别人的服务。

## 3. 命名空间移位实验

停止自己的模拟器后，运行：

```bash
uv run --locked python -m experiments.opcua.server --extra-namespace
```

它先注册一个无关命名空间，使本实验 URI 的索引由2变为3。客户端命令完全不变，读到的 NodeId 会变成 `ns=3;s=MotorA.Temperature`。这验证了 URI 解析，而不是让客户端猜索引。

## 4. 质量、时间与订阅参数

- **Good 不等于电机健康。** 它是该 DataValue 的质量状态；本实验没有诊断设备健康，也没有质量故障注入。
- 初始 `SourceTimestamp` 由模拟服务端写初值时生成，`ServerTimestamp` 由 asyncua 服务端记录。它们是这个软件模拟器的时间，不是真实传感器时钟。
- 设温客户端只发送 Double 值，不上传客户端时间充当设备源时间。2.0.1 实测写入后 `SourceTimestamp=null`，`ServerTimestamp` 更新。这里缺源时间是如实表达，不用接收时间补齐。
- `ReceivedAt` 是客户端回调时刻，与服务端时间含义不同。主动读取不会把最后一次写入时间刷新为当前读取时间。

| 参数 | 本实验设置与含义 |
| --- | --- |
| 服务端值更新 | 无周期更新，仅响应教学设温请求 |
| 请求 SamplingInterval | 100ms：监视项请求的采样间隔，不是传感器更新频率 |
| 请求 PublishingInterval | 250ms：订阅发布节奏，不意味着每250ms一定有数据变化通知 |
| 请求 QueueSize | 10：有限监视项队列，不是持久化历史 |
| DataChangeTrigger | 本版默认 StatusValue，关注状态/值，不单独关注时间戳变化 |

日志的 `requested_*` 明确表示请求值。服务端可以修订参数；本版 asyncua 模拟服务端通过地址空间写入回调检测变化，不能据此声称完成了100ms硬件采样。高速变化、有限队列、网络问题或客户端处理不及时都可能影响通知；本实验不承诺端到端每个变化必达，不实现 PubSub、持久队列或重连框架。

## 5. 已完成的真实验收

2026-09-16，由 AI 启动独立服务端和客户端进程，使用空闲端口 **60573**，通过 `--extra-namespace` 实测：

| 操作 | 实际结果 |
| --- | --- |
| 按 URI 主动读取 | `ns=3;s=MotorA.Temperature`，65.3，Double，Good（0） |
| 初始源时间 / 服务端时间 | `06:40:47.578693+00:00` / `06:40:47.578697+00:00`（日期均为2026-09-16） |
| 建立订阅 | 初次通知65.3，客户端接收时间 `06:40:47.866852+00:00` |
| 设温72.8 | 收到72.8、Good；源时间null，服务端时间 `06:40:48.000240+00:00` |
| 再次同值写72.8 | 服务端时间变为 `06:40:48.404644+00:00`；随后1.2秒观察窗口新增数据变化通知0，主动读取成功 |
| 写入整数形式73 | 读取值73.0、类型仍为Double |
| Ctrl+C停止订阅 | 输出subscription_deleted，退出130；服务端仍运行，之后由测试清理 |

这是本版本本次实验的观察，不是所有 OPC UA 设备的固定表现。完整未修改输出见 [验收日志](../../docs/verification/2026-09-16-opcua-transcript.txt)。日志中会话超时由请求3600000ms修订为600000ms的库警告是实际协商结果，不表示实验通信失败。

独立实验验收：

```bash
uv run --locked python -m unittest discover -s tests -p test_opcua.py -v
```

全项目回归：

```bash
uv run --locked python -m unittest discover -s tests -v
```

本次 **17 项测试通过，13.169秒**（原15项+2项OPC UA测试）。独立代码审查未发现需修复缺陷。验收使用真实进程并清理自己创建的订阅/连接/服务；没有停止用户已有服务，没有使用学习数据库或修改学习笔记。

## 6. 关键代码与官方依据

- `server.py:23`：明确 NodeId、浏览名和 Double 变量；第29行在服务端写入初始值。
- `common.py:24`：`get_namespace_index(URI)` 后构造 NodeId。
- `common.py:33`：直接提取 DataValue 的值、类型、质量和时间，不生成替代时间。
- `client.py:30`：用不带源时间的 DataValue 显式写 Double。
- `client.py:35`：创建订阅；第38行只监视一个温度变量；finally 删除订阅。
- `client.py:14`：回调打印 DataValue 和本地接收时间。

入门文档：[最小服务端](https://opcua-asyncio.readthedocs.io/en/latest/usage/get-started/minimal-server.html)、[URI解析客户端](https://opcua-asyncio.readthedocs.io/en/latest/usage/get-started/minimal-client.html)。接口及行为另核对了固定版本源码：[v2.0.1订阅](https://github.com/FreeOpcUa/opcua-asyncio/blob/v2.0.1/asyncua/common/subscription.py)、[监视项过滤/回调](https://github.com/FreeOpcUa/opcua-asyncio/blob/v2.0.1/asyncua/server/monitored_item_service.py)、[服务端时间处理](https://github.com/FreeOpcUa/opcua-asyncio/blob/v2.0.1/asyncua/server/address_space.py)。
