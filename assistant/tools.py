"""模型无关工具边界。只暴露三个结构化业务操作，不接收SQL、路径或命令。"""
import json
from storage import DEFAULT_DB
from .contracts import QueryError
from .query_service import QueryService

PARAMETERS = {
    'get_device_status': ({'device_id'}, set()),
    'query_metric_history': ({'device_id','metric','start','end'}, {'limit'}),
    'list_alarms': ({'device_id','start','end'}, {'status','limit'}),
}

class ReadOnlyTools:
    def __init__(self, db_path=DEFAULT_DB, **config):
        self.service = QueryService(db_path, **config)

    def invoke(self, name, arguments):
        try:
            if not isinstance(name,str) or name not in PARAMETERS:
                raise QueryError('unknown_tool','仅支持get_device_status、query_metric_history、list_alarms')
            required, optional = PARAMETERS[name]
            if not isinstance(arguments,dict) or not required <= arguments.keys() or not arguments.keys() <= required | optional:
                raise QueryError('invalid_parameters','参数缺失或包含未允许的字段')
            data = getattr(self.service,name)(**arguments)
            try:
                json.dumps(data,allow_nan=False)
            except (ValueError,TypeError):
                raise QueryError('invalid_stored_data','查询记录包含无法表示为JSON的值，请检查数据',503) from None
            return {'ok':True,'data':data}
        except QueryError as exc:
            return {'ok':False,'error':{'code':exc.code,'message':exc.message}}

    def get_device_status(self, device_id):
        return self.invoke('get_device_status', {'device_id':device_id})

    def query_metric_history(self, device_id, metric, start, end, limit=1000):
        return self.invoke('query_metric_history',dict(device_id=device_id,metric=metric,start=start,end=end,limit=limit))

    def list_alarms(self, device_id, start, end, status='all', limit=1000):
        return self.invoke('list_alarms',dict(device_id=device_id,start=start,end=end,status=status,limit=limit))
