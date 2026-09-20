# M2转速与运行状态

用户在本任务批准同步开发与学习，并确认断线保留最后运行记录、枚举2无法识别、整轮无有效测量且取消温度pending。

- [x] 后端：地址2 speed uint16倍率1 rpm默认1450；地址3 running_state 0停止/1运行默认1；一次count4；四测量和温度规则同事务。运行状态2产生data_validation_error四指标事件，保存原始值，不写本轮测量，清pending不清active。通信异常独立communication_error。旧单温度CLI保留。
- [x] API：四指标latest/history独立查询，不迁移旧库；status增加可选last_failure_type/last_failure_message。旧API未声明新指标时前端不查询。speed/running_state不设告警。
- [x] 前端：显示最后有效转速、最后有效运行状态、自己的时间与可知性；枚举映射0/1，运行状态历史是记录表而非连续数值曲线；温度/电流/转速曲线单指标单单位。失败信息显示原始值证据，不能误称通信失败。
- [x] 验证：后端TDD、前端测试、全套检查构建、真实临时四点链路与状态2故障、0停止、断线、旧库旧API、390px；代码审查、验收和点位文档。

开发边界：后端代理只改Python和tests；主代理改frontend/docs/README和浏览器验收。所有测试临时库、独立端口，不动用户data库、现有服务、docs/learning。不宣称整个M2验收完成。
