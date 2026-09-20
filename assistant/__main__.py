"""无需模型的业务工具CLI：python -m assistant --db PATH TOOL --params JSON。"""
import argparse
import json
from storage import DEFAULT_DB
from .tools import ReadOnlyTools


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--db',default=DEFAULT_DB,help='应用配置的只读SQLite路径，不是工具参数')
    parser.add_argument('tool',help='get_device_status / query_metric_history / list_alarms')
    parser.add_argument('--params',required=True,help='结构化JSON对象')
    args=parser.parse_args()
    try:
        parameters=json.loads(args.params)
    except (json.JSONDecodeError, ValueError):
        result={'ok':False,'error':{'code':'invalid_parameters','message':'params必须为合法JSON对象'}}
    else:
        result=ReadOnlyTools(args.db).invoke(args.tool,parameters)
    print(json.dumps(result,ensure_ascii=False,allow_nan=False,indent=2))
    return 0 if result['ok'] else 1

if __name__=='__main__':
    raise SystemExit(main())
