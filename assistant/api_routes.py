"""助手聊天路由：POST /api/assistant/chat。

- 请求schema严格：message 1～4000字符、history≤6条且每条≤4000字符、
  extra字段一律拒绝——客户端不能传入工具结果或模型配置。
- 服务未注入/未配置 → 503 assistant_unavailable；不影响任何监控路由。
- 单飞并发控制：上一条仍在处理时返回503 assistant_busy（清楚可重试）。
- 初版非流式；响应为D5结果合同（status/answer/evidence/limitations/calls/checked_at）。
"""
import threading
from typing import Literal

from fastapi import FastAPI, HTTPException
from pydantic import BaseModel, ConfigDict, Field

SERVICE_UNAVAILABLE = {'code': 'assistant_unavailable',
                       'message': '助手服务未配置：需在后端环境设置模型后重启服务'}
SERVICE_BUSY = {'code': 'assistant_busy',
                'message': '上一条问题仍在处理中，请稍后重试'}


class HistoryItem(BaseModel):
    model_config = ConfigDict(extra='forbid')
    role: Literal['user', 'assistant']
    content: str = Field(min_length=1, max_length=4000)


class ChatRequest(BaseModel):
    model_config = ConfigDict(extra='forbid')
    message: str = Field(min_length=1, max_length=4000)
    history: list[HistoryItem] = Field(default_factory=list, max_length=6)


class SingleFlight:
    """同一时刻只放行一条助手请求；不排队，忙时直接给出可重试状态。"""

    def __init__(self):
        self._lock = threading.Lock()
        self._busy = False

    def try_acquire(self):
        with self._lock:
            if self._busy:
                return False
            self._busy = True
            return True

    def release(self):
        with self._lock:
            self._busy = False


def register_assistant_routes(app: FastAPI, get_service):
    single_flight = SingleFlight()

    @app.post('/api/assistant/chat')
    def assistant_chat(request: ChatRequest):
        service = get_service()
        if service is None:
            raise HTTPException(503, dict(SERVICE_UNAVAILABLE))
        if not single_flight.try_acquire():
            raise HTTPException(503, dict(SERVICE_BUSY))
        try:
            history = [{'role': item.role, 'content': item.content}
                       for item in request.history]
            return service.answer(request.message, history)
        finally:
            single_flight.release()
