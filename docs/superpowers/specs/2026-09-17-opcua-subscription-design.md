# M3正式订阅：设计

主学习任务代表用户授权订阅、断线恢复和防重复接入，并给出完整约束；按已授权范围执行，不重复请求许可。属于采集生命周期扩展。

## 选择与边界

采用显式 `--mode read|subscribe`，默认read保持对照。subscribe使用持久Client、一个订阅、一个monitored item；断线关闭旧资源，有限超时后指数退避（1/2/4/5秒上限）创建新连接和新订阅。相比自动转移旧订阅，此方式生命周期可观察且易于隔离；不承诺断线补采。异步库内自动重连禁用，避免双重恢复。订阅低层服务保留PublishResult的SequenceNumber和CreateMonitoredItems的完整revised结果。

通知触发使用StatusValueTimestamp、无deadband；常值但SourceTimestamp变化也应提供新源证据。请求发布/采样250ms、服务端队列16（DiscardOldest）及MaxNotificationsPerPublish有界；保存返回的revised参数，服务端不支持或修订超出连续证据策略则明确失败，不静默降级到StatusValue。模拟器0.5秒源周期不变，告警有效观测间隙按--interval（默认1秒）的1.5倍上限；所有keepalive只影响订阅活性。

## 去重及世代

同一采集会话的每次连接都有严格递增generation。通知传输身份为(session,generation,subscription_id,PublishSequenceNumber,item_ordinal)，原始publish回调中提取，不从稍后可变的last_sequence_number推断。相同身份重投递无新measurement/diagnostic/event且不清新pending。旧generation回调在入队和写入前丢弃；不得影响新连接状态。数据库提交与投递身份去重同事务，防“先记处理后写失败”丢证据。

新序号、同SourceTimestamp属于新通知但源不是新测量，沿已确认的保守策略诊断拒收并立即清pending保active。不能按value去重。不同世代初始通知仍走持久源水位，防断线重放旧源。

同库同device新采集session使旧写端失效，事务开始先验证session（包括状态/诊断/故障更新），旧采集器停止而不能争写；A的独立session不受影响。必要时CLI可附加设备进程锁，但数据库session防护仍为最终边界。

## 非阻塞与失败

通知回调只解析/入有界队列，不做SQLite或等待。单独一个数据库线程拥有连接，消费者串行提交，避免SQLite阻塞事件循环。队列满、服务端Overflow位、序号缺口或通知活性超时显式记为证据中断，清pending保active；丢弃不可信积压并重连，不悄悄略过。仅keepalive不能延长样本新鲜度或推进告警；没有新源观测超过允许间隙时取消pending。接收时间来自回调收到通知时；取得SQLite写锁后使用decision_clock读取判定UTC，重新校验源年龄，诊断分别保存received_at和decision_at。源龄4.9秒+排队0.2秒在判定时必须拒收。已取出但超过处理期限的通知仍持久化拒绝诊断和identity，清pending保active，然后清积压重连；重复identity优先忽略。积压超过源时限/允许延迟的通知不能因批处理时间伪装连续观测。

数据库异常停止采集并输出可观察错误，尽力更新failed；无法写数据库时不声称已保存故障，API根据过期runtime心跳显示未知。退出阻止新回调、失效当前世代、清理订阅/连接/任务和数据库线程，状态stopped且清pending保active。

## 只读API与页面

B opcua增加可选runtime，旧库/旧主动读进程无此表时为null，GET不迁移：
`{mode, state, generation, updated_at, last_notification_at, last_publish_at, reconnect_count, duplicate_count, dropped_count, error, revised}`。
mode read|subscribe；state reading|connecting|subscribed|reconnecting|stopped|failed|unknown。runtime心跳每秒刷新；查询时超过5秒显示unknown，原state可附reported_state。停用/失败/重连/未知令eligible=false及有效性/告警unknown，但不伪造质量错误；订阅保活与通知接收时间分别显示。前端还需在查询延迟/错误时显示未知，不继续说已订阅。

## 验收

真实UA：同值新源持续通知并触发/低温恢复；服务器停/同端口重启自动恢复；Bad/Uncertain/缺源/旧/未来回归；URI解析；revised参数可见。真实双采集器共库验证A正常且B中断不清active。投递身份与世代边界、队列溢出、源重复、SQLite故障、退出清理测试。完整Python与前端回归、类型/build、浏览器订阅状态与重连演示。只使用临时库/随机端口。

## 保护范围

不得测试或迁移data/m3-opcua-practice.sqlite3；不得停止主任务5191/8021/15041/4841及5180等已有服务。所有data、experiments、docs/learning保持不动。无Git仓库，不创建虚假提交或部署。完成告知主学习任务实际覆盖和剩余限制。
