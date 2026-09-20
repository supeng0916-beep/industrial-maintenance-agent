"""独立启动 FastAPI 只读服务；不启动采集器。

助手服务由环境变量启用：项目根目录放 .env（或直接设置环境变量）
ASSISTANT_MODEL + ASSISTANT_BASE_URL + ASSISTANT_API_KEY（云API路线），
或仅 ASSISTANT_MODEL（本地Ollama路线，需Ollama服务运行）。
未配置时监控接口照常、助手路由返回503。
"""

import argparse
import math
from pathlib import Path

import uvicorn

from api import create_app
from assistant.model_provider import build_assistant_service
from assistant.settings import load_env_file
from storage import DEFAULT_DB

PROJECT_ROOT = Path(__file__).resolve().parent


def main():
    load_env_file(PROJECT_ROOT / '.env')
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--db", default=DEFAULT_DB)
    parser.add_argument("--port", type=int, default=8000)
    parser.add_argument("--stale-after-seconds", type=float, default=5)
    args = parser.parse_args()
    if not 1024 <= args.port <= 65535:
        parser.error("--port 必须在1024～65535之间")
    if not math.isfinite(args.stale_after_seconds) or args.stale_after_seconds <= 0:
        parser.error("--stale-after-seconds 必须是大于0的有限秒数")
    assistant_service = build_assistant_service()
    if assistant_service is not None:
        print("助手服务已启用（模型见 ASSISTANT_MODEL）；日志只含脱敏配置。")
    uvicorn.run(create_app(args.db, args.stale_after_seconds,
                           assistant_service=assistant_service),
                host="127.0.0.1", port=args.port)


if __name__ == "__main__":
    main()
