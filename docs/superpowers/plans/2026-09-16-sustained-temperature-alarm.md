# 持续超限确认实施计划

按主任务已批准设计顺序执行，使用TDD和完成前验证技能，不重复索要批准。

**目标：** M2下一小步，>80℃观测连续至少5秒才触发，已active时<78℃恢复。

**规则：** 固定confirm_seconds=5；max_gap_seconds=1.5×interval≤5，interval>0且≤10/3秒；默认1秒→1.5秒。API stale阈值不得低于采集max_gap（文档约束）。monotonic计时、UTC仅作证据时间。没有新样本绝不自动触发。≤80、显式失败、相邻有效样本gap>max_gap、采集会话变更都清pending；active仅新有效<78恢复。

**数据：** 写端迁移状态表增加会话、持续规则、pending首样本/单调时刻/上次时刻/累计秒；告警表增加first_exceeded_at/id/value与confirm_seconds。旧记录confirm_seconds=0，started_at仍指正式触发。写端启动重置pending/evaluated_id但保留active。每次测量/告警/pending更新一个短事务；失败事件与清pending也同事务。GET通过列检测兼容无表/旧即时表，绝不迁移。

- [x] 先写确定性monotonic时间测试：5秒边界并非5样本、≤80重置、失败/长gap/时钟回跳/重启、事务回滚、active回差再触发、旧模式读取迁移无回放。
- [x] alarms.py迁移与会话计时、storage.py成功失败事务、collector参数限制/会话/monotonic调用；旧回差测试调整到持续规则前提。
- [x] API增加pending和规则证据，pending仅在样本年龄≤max_gap时可知；前端兼容可选新字段，显示后端已累计值，长gap变未知，旧接口即时文案。
- [x] 运行Python回归、前端test/check/build、真实Chrome临时服务验证pending/中断/5秒触发/恢复/旧服务兼容，独立审查，记录命令与教学代码位置。

保护所有用户库、现有5175/5176/8010/8012/15030/15031服务和docs/learning。仅在临时库/独立端口验证。未完成整个M2，不涉及多测点。
