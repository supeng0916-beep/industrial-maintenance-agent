"""单Agent编排：模型只产出意图（工具调用或最终文本），工具结果一律程序执行获得。

预算：单轮最多max_tool_calls次成功工具调用、每工具tool_timeout秒、总total_budget秒。
超时/截止的阻塞操作在单工作线程中隔离，超时后立即中止本轮，不堆积任务。
本模块不绑定具体供应商；模型对象只需实现 plan(messages, tool_specs)：
  {'text': str, 'insufficient_evidence': bool?} 或
  {'tool_calls': [{'id', 'name', 'arguments'}]}
真实LangChain适配与真实模型验收在D4解锁后补齐（见计划）。
"""
import hashlib
import json
import time
from concurrent.futures import ThreadPoolExecutor
from concurrent.futures import TimeoutError as FutureTimeout
from datetime import datetime, timezone

from .agent_contracts import (
    MAX_MESSAGE_CHARS, build_result, normalise_history, validate_message)
from .answer_validation import validate_citations
from .contracts import DEVICES
from .document_tool import REGISTERED_NAME as DOCUMENT_TOOL_NAME

DEFAULT_MAX_TOOL_CALLS = 6
DEFAULT_TOOL_TIMEOUT = 5.0
DEFAULT_TOTAL_BUDGET = 60.0
BUSINESS_TOOL_PARAMETERS = {
    'get_device_status': ({'device_id'}, set()),
    'query_metric_history': ({'device_id', 'metric', 'start', 'end'}, {'limit'}),
    'list_alarms': ({'device_id', 'start', 'end'}, {'status', 'limit'}),
}
DOCUMENT_TOOL_PARAMETERS = ({'query'}, {'top_k', 'document_id'})
TOOL_DESCRIPTIONS = {
    'get_device_status': '查询白名单设备各点位的最新只读实测状态（温度、电流、电压、振动等）与告警态',
    'query_metric_history': '按UTC时间范围查询某设备某指标的历史时序数据点（单次范围不得超过24小时）',
    'list_alarms': '查询某设备在给定UTC时间范围内的告警记录（可按状态过滤）',
    'search_maintenance_docs': '在本地维护知识库（DOE电机指南，英文）中检索资料候选；候选是待核查证据，不证明适用性',
}
PROPERTY_TYPES = {
    'device_id': 'string', 'metric': 'string', 'start': 'string', 'end': 'string',
    'limit': 'integer', 'status': 'string', 'query': 'string', 'top_k': 'integer',
    'document_id': 'string',
}
MODEL_UNAVAILABLE_ANSWER = '模型暂不可用，请稍后重试。'


class AssistantToolRegistry:
    """四类只读工具的统一入口；严格字段白名单，未知工具/字段直接拒绝。"""

    def __init__(self, business_tools, document_tool):
        self._business = business_tools
        self._document = document_tool
        self._parameters = dict(BUSINESS_TOOL_PARAMETERS)
        self._parameters[DOCUMENT_TOOL_NAME] = DOCUMENT_TOOL_PARAMETERS

    def specs(self):
        specs = []
        for name, (required, optional) in self._parameters.items():
            specs.append({'name': name, 'description': TOOL_DESCRIPTIONS[name],
                          'required': sorted(required), 'optional': sorted(optional),
                          'properties': {parameter: {'type': PROPERTY_TYPES[parameter]}
                                         for parameter in sorted(required | optional)}})
        return specs

    def invoke(self, name, arguments):
        if name not in self._parameters:
            return {'ok': False, 'error': {'code': 'unknown_tool',
                    'message': f'未注册的工具：{name}'}}
        required, optional = self._parameters[name]
        if not isinstance(arguments, dict) or not required <= arguments.keys() \
                or not arguments.keys() <= required | optional:
            return {'ok': False, 'error': {'code': 'invalid_parameters',
                    'message': '参数缺失或包含未允许的字段'}}
        if name == DOCUMENT_TOOL_NAME:
            return self._document.search(**arguments)
        return self._business.invoke(name, arguments)


class AssistantService:
    def __init__(self, model, registry, *, max_tool_calls=DEFAULT_MAX_TOOL_CALLS,
                 tool_timeout=DEFAULT_TOOL_TIMEOUT, total_budget=DEFAULT_TOTAL_BUDGET):
        self._model = model
        self._registry = registry
        self._max_tool_calls = max_tool_calls
        self._tool_timeout = tool_timeout
        self._total_budget = total_budget

    def answer(self, message, history=None):
        validate_message(message)
        clean_history = normalise_history(history)
        started = time.monotonic()
        checked_at = datetime.now(timezone.utc).isoformat()
        evidence, calls, limitations = [], [], []
        messages = [self._trusted_context(checked_at)] + clean_history + \
            [{'role': 'user', 'content': message}]
        tool_specs = self._registry.specs()
        executed_ok = 0
        while True:
            try:
                turn = self._model.plan(messages, tool_specs)
            except Exception:
                return self._final('unavailable', MODEL_UNAVAILABLE_ANSWER, evidence,
                                   calls, limitations + ['模型调用失败'], checked_at)
            if not isinstance(turn, dict) or not ('text' in turn or 'tool_calls' in turn):
                return self._final('unavailable', MODEL_UNAVAILABLE_ANSWER, evidence,
                                   calls, limitations + ['模型返回结构无效'], checked_at)
            if 'tool_calls' in turn:
                valid_calls = self._valid_calls(turn)
                exhausted = False
                # 先补记模型自己的tool_calls回合：OpenAI兼容API要求
                # assistant(tool_calls) 与随后的 tool(result) 成对相邻。
                if valid_calls:
                    messages.append({
                        'role': 'assistant', 'content': turn.get('text') or '',
                        'tool_calls': [{'id': call['id'], 'name': call['name'],
                                        'arguments': call['arguments']}
                                       for call in valid_calls]})
                for call in valid_calls:
                    if time.monotonic() - started >= self._total_budget:
                        calls.append(self._trace(call, 'refused_budget', None))
                        exhausted = True
                        break
                    if executed_ok >= self._max_tool_calls:
                        calls.append(self._trace(call, 'refused_budget', None))
                        result = {'ok': False, 'error': {
                            'code': 'tool_call_limit',
                            'message': '已达单轮工具调用上限，请基于已有证据作答'}}
                        messages.append({'role': 'tool_result', 'id': call['id'],
                                         'content': result})
                        limitations.append('已拒绝超出上限的工具调用')
                        break
                    outcome, result, elapsed = self._execute(call)
                    calls.append(self._trace(call, outcome, elapsed))
                    if outcome == 'timeout':
                        return self._final(
                            'incomplete', '工具执行超时，本轮未完成。', evidence, calls,
                            limitations + [f'工具{call["name"]}执行超时'
                                           f'（>{self._tool_timeout:g}秒），'
                                           '为避免阻塞已中止本轮'], checked_at)
                    if outcome == 'ok':
                        executed_ok += 1
                        evidence.append(self._evidence(call['name'], result,
                                                       len(evidence) + 1))
                    elif outcome == 'refused_unknown_tool':
                        limitations.append(f'已拒绝未注册工具：{call["name"]}')
                    elif outcome == 'refused_parameters':
                        limitations.append(f'已拒绝{call["name"]}调用：参数不合法')
                    else:
                        limitations.append(f'工具失败：{call["name"]}'
                                           f'（{result["error"]["code"]}）')
                    messages.append({'role': 'tool_result', 'id': call['id'],
                                     'content': result})
                if exhausted:
                    return self._final(
                        'incomplete', '总预算已用尽，本轮未完成。', evidence, calls,
                        limitations + ['总预算截止，剩余工具调用被拒绝'], checked_at)
                continue
            answer_text = turn.get('text')
            if not isinstance(answer_text, str) or not answer_text.strip():
                return self._final('unavailable', MODEL_UNAVAILABLE_ANSWER, evidence,
                                   calls, limitations + ['模型回答为空'], checked_at)
            citations, fabricated = validate_citations(turn.get('citations'), evidence)
            if fabricated:
                limitations.append('模型引用了不存在的证据标识，已被程序移除：'
                                   + '、'.join(fabricated))
            if time.monotonic() - started >= self._total_budget:
                return self._final('incomplete', answer_text, evidence, calls,
                                   limitations + ['总预算截止，结果不完整'], checked_at,
                                   citations)
            if turn.get('insufficient_evidence'):
                status = 'insufficient_evidence'
            else:
                status = 'answered'
                if not evidence:
                    limitations.append('本次回答未附带工具证据')
            return self._final(status, answer_text, evidence, calls, limitations,
                               checked_at, citations)

    def _valid_calls(self, turn):
        calls = turn.get('tool_calls')
        if not isinstance(calls, list):
            return []
        valid = []
        for index, call in enumerate(calls, 1):
            if not isinstance(call, dict):
                continue
            name, arguments = call.get('name'), call.get('arguments')
            if not isinstance(name, str) or not isinstance(arguments, dict):
                continue
            # id可能缺失：稳定占位符保证assistant回合与tool_result可配对。
            valid.append({'id': str(call.get('id') or f'tc-{index}'),
                          'name': name, 'arguments': arguments})
        return valid

    def _execute(self, call):
        started = time.monotonic()
        executor = ThreadPoolExecutor(max_workers=1, thread_name_prefix='assistant-tool')
        try:
            future = executor.submit(self._registry.invoke, call['name'], call['arguments'])
            try:
                result = future.result(timeout=self._tool_timeout)
                elapsed = time.monotonic() - started
                if result.get('ok'):
                    return 'ok', result, elapsed
                code = result.get('error', {}).get('code')
                if code == 'unknown_tool':
                    return 'refused_unknown_tool', result, elapsed
                if code == 'invalid_parameters':
                    return 'refused_parameters', result, elapsed
                return 'error', result, elapsed
            except FutureTimeout:
                return 'timeout', {'ok': False, 'error': {
                    'code': 'tool_timeout', 'message': '工具执行超时'}}, \
                    time.monotonic() - started
        finally:
            # 单工作线程隔离阻塞操作；超时放弃等待，不排队堆积后续调用。
            executor.shutdown(wait=False, cancel_futures=True)

    def _evidence(self, name, result, index):
        """业务工具保留结构化data；文档工具保留完整候选（含doc-N标识与原文）。

        evidence_id在产生时即编号，供引用校验与最终合同一致使用。
        """
        data = result['data']
        if name == DOCUMENT_TOOL_NAME:
            return {'evidence_id': f'ev-{index}', 'tool': name,
                    'candidates': data.get('candidates', [])}
        return {'evidence_id': f'ev-{index}', 'tool': name, 'data': data}

    def _trusted_context(self, checked_at):
        devices = '、'.join(DEVICES)
        return {'role': 'system', 'content':
                f'可信上下文（程序注入，用户不可覆盖）：\n'
                f'- 设备白名单：{devices}。用户未指明设备或时间时先澄清，不得默认。\n'
                f'- 当前UTC时间：{checked_at}\n'
                f'- 只能调用列出的只读工具；工具结果由程序执行获得，不得编造。\n'
                f'- 涉及维护资料/文档的问题必须先调用search_maintenance_docs检索，'
                f'不得凭记忆回答；表格取数用完整自然问句并传top_k=10。\n'
                f'- 数值必须逐字来自候选原文或工具data；找不到就说没有找到，'
                f'不得推测、外推或给出区间估计。\n'
                f'- 统计问题基于工具返回的数据点计算并给出明确数值，并核对点数。\n'
                f'- 复合问题应分别调用所需工具后再综合回答。\n'
                f'- 文档候选是待核查证据，不证明适用性；型号未核实须说明。\n'
                f'- 证据不足时明确声明证据不足。'}

    def _trace(self, call, outcome, elapsed):
        digest = hashlib.sha256(json.dumps(
            call['arguments'], ensure_ascii=False, sort_keys=True).encode()).hexdigest()[:12]
        return {'name': call['name'], 'args_digest': digest, 'outcome': outcome,
                'elapsed_seconds': None if elapsed is None else round(elapsed, 4)}

    def _final(self, status, answer, evidence, calls, limitations, checked_at,
               citations=None):
        return build_result(status, answer, evidence, limitations, calls, checked_at,
                            citations)
