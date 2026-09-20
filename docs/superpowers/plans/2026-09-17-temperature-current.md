# 温度＋电流计划

已批准范围，按TDD和完成前验证执行。保护用户库、既有服务及docs/learning。

- [x] 集中points.py定义地址0/1、uint16、0.1℃/0.01A；模拟器和启动器支持--current-raw默认123。新采集器一次holding地址0 count2，旧read_temperature count1保持。
- [x] save_round同事务温度写入/温度告警/电流写入；共享collected_at。save_round_failure同事务两个metric失败事件与清温度pending。旧单温度storage入口保留。
- [x] latest?metric=temperature|current默认温度；history同规则；各metric独立样本/失败/新鲜度，电流alarm=null。devices声明两指标，旧库空电流不补数据，GET不迁移。
- [x] 页面加电流读数/独立时间状态；历史选择温度或电流，单位轴独立；旧API不声明电流则显示未提供，新API旧库显示暂无数据。
- [x] 临时库验证批量协议倍率、长度错误、同轮/回滚/失败恢复、API隔离旧库；Python/前端全检查、Chrome验收、审查与教学文档。
