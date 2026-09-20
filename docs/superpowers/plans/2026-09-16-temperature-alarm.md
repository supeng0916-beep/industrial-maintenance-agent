# 温度回差告警实施计划

> 按主任务已批准设计，在当前专用项目内顺序执行；不重复确认，不启动子开发任务。

**目标：** M2 第一小步，motor-a 温度 >80℃触发、<78℃恢复；等号保持。教学阈值，不代表设备安全标准。

**架构：** 新采集结果在一个短事务内写测量、评估规则、保存告警与证据。独立 alarms.py 管理规则表和只读快照；collector 启用规则，API 不迁移数据库。首次启用不回放旧测量。SQLite 唯一部分索引保证每设备指标只有一条未解除告警。

**约束：** 不修改用户数据库、docs/learning、其他项目服务；临时库独立端口验证。API 和前端不执行告警规则。失败/过期只影响当前可知性，不能解除已激活告警。

- [x] 存储：tests/test_alarms.py 先验证边界序列80→80.1→90→80→78→77.9→81，重启、失败和事务注入回滚；实现 alarms.py initialize_alarms/evaluate/read_alarms。storage.save_measurement 增加显式 evaluate_alarm 参数（默认关闭，历史写入不评估）；collector 初始化并启用。
- [x] API：测试旧库 not_enabled、已启用未评估 unknown、新鲜 active/clear、失败/过期 unknown 且保留 active、GET字节不变。latest 在现有只读事务内附加 alarm 快照，/alarms 返回同一契约，历史最多20条倒序。
- [x] 前端：状态文案测试先失败，再实现 AlarmPanel；最新接口带告警及历史，同步显示当前未知与历史未解除，折叠最近20条证据。失败时将旧告警快照明确标成历史。
- [x] 验证：Python回归、前端test/check/build；真实Modbus→collector→API→Chrome独立端口，温度触发/重复/故障/恢复/再触发，截图检查390px和桌面。审查与验收文档、用户命令和关键位置。

预期命令：uv run --locked python -m unittest discover -s tests -v；cd frontend 后 npm test、npm run check、npm run build、node scripts/verify-alarms.mjs。
