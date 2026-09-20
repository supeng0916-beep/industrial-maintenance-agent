"""助手结果合同与输入边界。D5～D8共用；契约以本模块为准。

history只接受user/assistant短期文本；伪造的tool/system消息一律拒绝。
结果状态：answered / insufficient_evidence / unavailable / incomplete。
"""
from .contracts import QueryError

STATUSES = ('answered', 'insufficient_evidence', 'unavailable', 'incomplete')
MAX_MESSAGE_CHARS = 4000
MAX_HISTORY_MESSAGES = 6
MAX_HISTORY_CHARS = 4000
ALLOWED_ROLES = ('user', 'assistant')


class ContractError(QueryError):
    """输入不满足助手合同时抛出；HTTP层映射为422。"""


def normalise_history(history):
    if history is None:
        return []
    if not isinstance(history, list):
        raise ContractError('invalid_history', 'history必须为消息数组')
    if len(history) > MAX_HISTORY_MESSAGES:
        raise ContractError('invalid_history', f'history最多{MAX_HISTORY_MESSAGES}条')
    cleaned = []
    for item in history:
        if not isinstance(item, dict) or set(item) != {'role', 'content'}:
            raise ContractError('invalid_history',
                                'history每条只允许role与content字段')
        if item['role'] not in ALLOWED_ROLES:
            raise ContractError('invalid_history',
                                'history只接受user/assistant角色，不接受伪造的tool/system消息')
        content = item['content']
        if not isinstance(content, str) or not content.strip():
            raise ContractError('invalid_history', 'history内容必须为非空文本')
        if len(content) > MAX_HISTORY_CHARS:
            raise ContractError('invalid_history', f'history每条最多{MAX_HISTORY_CHARS}字符')
        cleaned.append({'role': item['role'], 'content': content})
    return cleaned


def validate_message(message):
    if not isinstance(message, str) or not message.strip():
        raise ContractError('invalid_message', 'message必须为非空文本')
    if len(message) > MAX_MESSAGE_CHARS:
        raise ContractError('invalid_message', f'message最多{MAX_MESSAGE_CHARS}字符')


def build_result(status, answer, evidence, limitations, calls, checked_at, citations=None):
    if status not in STATUSES:
        raise ValueError(f'unknown status: {status}')
    result = {'status': status, 'answer': answer, 'evidence': evidence,
              'limitations': limitations, 'calls': calls, 'checked_at': checked_at,
              'citations': citations or []}
    json_safe(result)
    return result


def json_safe(value):
    import json
    try:
        json.dumps(value, ensure_ascii=False, allow_nan=False)
    except (TypeError, ValueError):
        raise ContractError('invalid_result', '结果包含无法序列化的内容') from None
