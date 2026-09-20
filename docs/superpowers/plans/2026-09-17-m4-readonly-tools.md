# M4.1只读业务工具实施计划

按已授权的docs/project-plan-v0.2.md执行，仅M4.1，不修改该计划主本。设计采用共享事实读取+短只读事务+结构化工具包装，不安装新依赖。

## 契约

- assistant/contracts.py：A/B设备指标白名单，带时区ISO时间统一UTC，闭区间start≤end且≤24小时，limit整数1..1000，告警status=active/recovered/all；错误统一QueryError(code,message,status)。
- assistant/observations.py：从api.py移出原observation_status及单测点状态拼装，API与工具调用同一函数，不重写质量/源新鲜判断。
- assistant/query_service.py：独立只读连接、BEGIN一致快照、统一checked_at；SQLite progress handler全次调用共享单调期限≤5秒，busy等待≤100ms，退出关闭连接；错误不同于空样本。
- assistant/ranges.py：完整闭区间历史SQL count/min/max及观测时间范围；明细升序limit最多1000且返回truncated。枚举只计状态次数，不计算物理min/max。不估算完整率，不声称实际物理峰值。告警区间相交定义started_at≤end AND (recovered_at IS NULL OR recovered_at≥start)，status指记录当前恢复状态；完整匹配总数、范围内未解除数、设备全历史总数/当前未解除数分开；旧库无告警表返回history_available=false。
- assistant/tools.py及__main__.py：仅get_device_status/query_metric_history/list_alarms，严格结构化参数，返回{ok,data}或{ok:false,error}；数据库路径由应用/CLI配置，不允许工具参数指定SQL/shell/path。

## 实施

- [x] 根代理TDD：参数/只读预算/状态服务抽取、旧API复用、工具封装及CLI。
- [x] 范围代理TDD：ranges.py与独立tests/test_assistant_ranges.py，完整统计、闭区间和告警相交语义。
- [x] 集成：>1000条截断外极值、空/错误/过滤/枚举、同快照一致、状态A/B隔离、旧库不迁移、锁与SQL超时、真实CLI JSON。
- [x] 独立代码审阅；完整Python回归，未改UI不重复浏览器。文档、CLI命令、完成报告同步主任务。

保护所有data、docs/learning、experiments，以及5192/8022/15042/4842与5191/8021/15041/4841等服务。测试只用临时库；无Git仓库，不创建提交或部署。不实施M4其余子步。
