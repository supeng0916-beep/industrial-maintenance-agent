"""只读 HTTP 查询；不导入协议客户端，不启动采集。"""

from datetime import datetime, timedelta, timezone
import logging
import math
import sqlite3

from fastapi import FastAPI, HTTPException, Query
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from starlette.exceptions import HTTPException as StarletteHTTPException

from points import POINTS
from assistant.api_routes import register_assistant_routes
from assistant.contracts import utc_text, parse_time, check_device, QueryError, DEVICES
from assistant.observations import observation_status
from assistant.query_service import QueryService
from storage import (
    DEFAULT_DB, DEVICE_ID, METRIC, PROTOCOL,
    history_between, open_readonly_database,
)

logger = logging.getLogger(__name__)


def create_app(db_path=DEFAULT_DB, stale_after_seconds=5, now=None, assistant_service=None):
    if not math.isfinite(stale_after_seconds) or stale_after_seconds <= 0:
        raise ValueError("stale_after_seconds 必须是大于0的有限秒数")
    clock = now or (lambda: datetime.now(timezone.utc))
    service = QueryService(db_path, stale_after_seconds=stale_after_seconds, now=clock)
    app = FastAPI(title="工业设备只读查询", version="0.1.0")

    @app.exception_handler(QueryError)
    async def query_error(request, exc):
        return JSONResponse({'error': {'code': exc.code, 'message': exc.message}}, status_code=exc.status)

    @app.exception_handler(StarletteHTTPException)
    async def http_error(request, exc):
        detail = exc.detail if isinstance(exc.detail, dict) else {
            "code": "http_error", "message": str(exc.detail)
        }
        return JSONResponse({"error": detail}, status_code=exc.status_code)

    @app.exception_handler(RequestValidationError)
    async def validation_error(request, exc):
        fields = ", ".join(".".join(map(str, e["loc"])) for e in exc.errors())
        return JSONResponse({"error": {"code": "invalid_parameters", "message": f"参数缺失或不符合约束：{fields}"}}, status_code=422)

    @app.exception_handler(sqlite3.Error)
    async def database_error(request, exc):
        logger.warning("只读数据库查询失败: %s", exc)
        return JSONResponse({"error": {"code": "database_unavailable", "message": "数据库不可读：文件尚未创建、表未就绪、被锁或损坏；请检查采集器及服务日志"}}, status_code=503)

    def latest_data(device_id, metric=METRIC):
        return service.latest(device_id, metric)

    @app.get("/api/devices")
    def devices():
        return {'devices': [{**device, 'metrics': list(device['metrics']),
                             'status': latest_data(device_id)['status']}
                            for device_id, device in DEVICES.items()]}

    @app.get("/api/devices/{device_id}/latest")
    def latest(device_id: str, metric: str = METRIC):
        check_device(device_id, metric)
        return latest_data(device_id, metric)

    @app.get("/api/devices/{device_id}/alarms")
    def alarms(device_id: str):
        check_device(device_id)
        return latest_data(device_id)["alarm"]

    @app.get("/api/devices/{device_id}/history")
    def history(device_id: str, start: str = Query(alias="from"), end: str = Query(alias="to"),
                metric: str = METRIC, limit: int = Query(default=100, ge=1, le=1000)):
        check_device(device_id, metric)
        first, last = parse_time(start), parse_time(end)
        if last < first or last - first > timedelta(hours=24):
            raise HTTPException(422, {"code": "invalid_range", "message": "from 不得晚于 to，时间范围不得超过24小时"})
        with service.snapshot() as conn:
            points = history_between(conn, device_id, metric, utc_text(first), utc_text(last), limit)
        return {"device_id": device_id, "metric": metric, "from": utc_text(first), "to": utc_text(last),
                "limit": limit, "order": "collected_at ASC, id ASC", "points": points}

    # 助手路由：服务由部署配置注入；未注入时路由存在但返回503，不影响监控接口。
    register_assistant_routes(app, lambda: assistant_service)
    return app
