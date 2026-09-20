# 第三次增量：FastAPI 只读查询

用户已授权继续实现，沿用既有八字段数据契约。保持采集器独立，不触碰 data/my-learning.sqlite3 和 docs/learning。

## 简短方案

- `api.py`：create_app 工厂、三个 GET 路由、统一错误、时区转换、最近尝试与过期判断。
- `storage.py`：增加只读连接、同一快照内最新测量/失败查询、参数化时间范围查询。已有采集与 CLI 保持兼容。
- `serve_api.py`：仅启动本机 HTTP 服务，配置数据库路径、非特权端口、stale_after_seconds（默认5）。
- 设备显式为 motor-a，指标 temperature；未知设备404，参数错误422，库缺失/锁定/表未就绪503；统一 error.code/message。
- latest 返回 measurement 或 null 和 status；devices 返回配置设备及相同 status。status 包含 has_data、last_attempt_status/at、last_success_at、last_failure_at、data_age_seconds、is_stale、checked_at、stale_after_seconds。不返回在线/健康结论。
- 最后成功和最后失败按时间比较，后者较新为 failure，前者较新为 success；同刻无法断定先后为 unknown；无记录unknown。无样本年龄和过期为null；有样本年龄大于阈值才过期。
- history 必须传 from/to（带时区），转换为 UTC；闭区间，最多24小时，limit默认100、范围1～1000，最早在前，同刻ID升序。存储契约沿用采集器 UTC 微秒 ISO 格式。

## 步骤

- [x] 固定 FastAPI/Uvicorn 与测试依赖，先增加行为测试并观察失败。
- [x] 实现只读存储、状态与历史接口，保留原8测试。
- [x] 独立审查；真实启动服务，用临时库和端口发 HTTP 请求，记录并发只读与缺库恢复结果。
- [x] README 说明返回契约、运行/curl命令、真实验收及教学入口。

完成：FastAPI 0.141.1、Uvicorn 0.53.0、测试httpx2 2.13.0固定；15项测试通过。真实HTTP临时端口57048验证缺库503→建库200、过期旧值、失败后恢复、并发12次不改文件、锁定503→解锁200。证据见 docs/verification/2026-09-16-api-transcript.txt；独立审查无待修复项。
