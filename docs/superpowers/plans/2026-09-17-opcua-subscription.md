# OPC UA订阅与断线恢复 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use executing-plans to implement this plan task-by-task. Steps use checkbox (`- [x]`) syntax for tracking.

**Goal:** 增加明确的订阅模式、断线重建和通知去重，保持主动读取及保守数据准入。

**Architecture:** asyncua低层订阅回调将带世代/序号的通知送入有界队列，单独DB线程串行事务落库。runtime保存模式/活性/故障和revised参数，API只读重算，页面分别展示订阅活性与测量有效性。

**Tech Stack:** Python3.11、asyncua2.0.1、SQLite、FastAPI、React19、Vitest、Playwright。

**Spec:** ../specs/2026-09-17-opcua-subscription-design.md

## Global Constraints

- 当前主任务5191/8021/15041/4841、旧5180服务和全部data/experiments/docs/learning不能改动。
- 新测试仅临时库随机端口，只关闭自身进程。
- Default read，对同device session做事务fence，A/B隔离。
- 通知传输重复忽略；新通知同源拒收清pending保active。keepalive不推进温度告警。
- root负责API/frontend/docs；backend代理负责runtime/subscriber/collector/storage及Python测试，不重叠写文件。

### Task 1: 后端生命周期与写入边界

Files: new opcua_runtime.py/opcua_subscription.py；modify collect_opcua.py/opcua_storage.py；tests/test_opcua_subscription*.py。

Interfaces: read_runtime(conn,now) -> runtime|null，只读；save_data_value兼容原调用，新增可选投递身份和世代验证。CLI --mode read|subscribe 默认read。runtime字段按spec。

- [x] 写失败测试：相同publish身份二次提交不新增任何测量、不清pending；新序号同SourceTimestamp诊断拒收清pending；新session/新generation使旧写入无效；队列满产生显式中断。
- [x] 运行对应unittest确认缺失行为失败，再实现最小事务去重、runtime和worker。
- [x] 真实随机端口测试：StatusValueTimestamp常值新源；服务器重启；Bad/Uncertain/源异常；队列/DB失败；停止退出。逐项先失败后实现。
- [x] 运行全部后端测试，无Git不做提交。

### Task 2: 只读状态与页面

Files: api.py；frontend/src/{model,OpcuaPanel,useDashboard,App,alarmFreshness}；frontend测试、tests/test_opcua_runtime_api.py。

- [x] 前端先写渲染测试：subscribed可见但Bad仍不可用；reconnecting保历史；keepalive不显示测量可用；旧runtime=null兼容。
- [x] 后端API先写测试：过期runtime/停用eligible=false且active保留，GET旧库不迁移；同device过滤。
- [x] 接入runtime只读门槛和独立模式/活性UI，运行npm test/check/build。

### Task 3: 集成、审阅、交付

Files: frontend/scripts/verify-opcua-subscription.mjs；docs/verification/opcua-subscription；README。

- [x] 实际Chrome：A正常+B订阅高温、停B、重连恢复、Bad诊断、退出未知；独立端口临时库。
- [x] 独立审查高风险生命周期、并发、事务和API新鲜度，按复现测试修复。
- [x] 完整Python/frontend回归、构建、验收截图人工检查，清理自己的进程。
- [x] 文档说明实际revised、退避、去重边界、故障可见、无断线补采；通知主任务命令及限制。
