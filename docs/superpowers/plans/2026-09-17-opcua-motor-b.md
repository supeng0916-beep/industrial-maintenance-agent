# M3第一小步：OPC UA电机B主动读取

主学习任务已认可设计和保守准入，无需重复确认。以TDD、真实协议和完成前验证执行。

## 设计

- 新独立正式模拟器，保持旧experiments不变；URI urn:industrial-maintenance:motor-b、string标识MotorB.Temperature，客户端按URI解析ns。Double℃为教学单位约定。每0.5秒生成源测量，每1秒主动读取DataValue，显式raise_on_bad_status=False保留Bad证据。
- 源新鲜度默认5秒（参数source-max-age），要求≥1.5×interval；Good、finite Double、SourceTimestamp存在且0≤源年龄≤阈值、严格大于持久化最近接受源时间才准入。未来零容忍；UTC同步假设。Bad/Uncertain/缺失/旧/重复/倒退/未来仅诊断，不变成有效measurement。
- diagnostics保存raw JSON、type、StatusCode name/number、source/server/received时间和准入reason；collected_at对B为received_at，source_time保持原值。诊断+有效measurement+告警或诊断+拒绝事件+清pending短事务一致；拒绝不解active，通信失败独立事件。
- alarm初始化参数化device_id，默认motor-a兼容；B单独会话，互不重置。源时间水位持久化跨重启，旧测量不回放。
- API固定声明A四点/B温度。GET设备过滤且只读不迁移。B最新附opcua独立通信/质量/源新鲜度/eligible及诊断，查询时重算新鲜度，API阈值不宽于采集诊断所记阈值。A源null不套OPCUA门槛。
- 前端设备选择，B只显示温度/告警/OPCUA诊断；源与接收时间分别显示，原始拒绝值仅诊断，非有效温度。切换时清旧设备快照，取消未完成查询。旧API只有A仍可用。

## 实施与验收

- [x] Python代理：alarm设备隔离、新模拟器/collector/diagnostic存储、API和真实/事务/隔离测试；只编辑Python和tests。
- [x] 主代理：设备选择、诊断面板、兼容和切换验证；只编辑frontend/docs/README。
- [x] 集成：Good触发/恢复；Bad、Uncertain、源缺失/过旧/未来/重复/倒退不推进或解除；失败恢复；A/B同库；只读旧库；类型/build；真实Chrome切换；独立审查。
- [x] 验收文档、命令、实测结果和限制，不宣称整个M3完成。

保护用户data全部库、长期5180/8016/15035及旧服务，不改docs/learning或experiments/register_encoding。测试仅临时库随机端口，只清理自身进程。
