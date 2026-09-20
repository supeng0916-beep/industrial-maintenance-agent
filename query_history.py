"""只读查询历史：最新记录在前，时间相同时按 ID 降序。"""

import argparse
from contextlib import closing
import json
from pathlib import Path
import sqlite3
import sys

from storage import DEFAULT_DB, DEVICE_ID, METRIC, query_history


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--db", default=DEFAULT_DB)
    parser.add_argument("--device-id", default=DEVICE_ID)
    parser.add_argument("--metric", default=METRIC)
    parser.add_argument("--limit", type=int, default=10, help="最新条数，1～1000，默认 10")
    parser.add_argument("--events", action="store_true", help="查询失败事件而非测量值")
    args = parser.parse_args()
    if not 1 <= args.limit <= 1000:
        parser.error("--limit 必须在 1～1000 之间")
    try:
        # mode=ro 防止输错路径时悄悄创建空库；查询进程有自己的连接。
        uri = Path(args.db).resolve().as_uri() + "?mode=ro"
        with closing(sqlite3.connect(uri, uri=True, timeout=2)) as conn:
            rows = query_history(conn, args.device_id, args.metric, args.limit, args.events)
        print(json.dumps(rows, ensure_ascii=False, indent=2))
        return 0
    except (OSError, sqlite3.Error) as exc:
        print(f"数据库查询失败（{args.db}）：{exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(main())
