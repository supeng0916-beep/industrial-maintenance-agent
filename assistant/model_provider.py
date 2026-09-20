"""D4 供应商适配：本地Ollama零成本路线（langchain-ollama==1.1.0）。

- 惰性导入：模块加载不发网络请求；真实连接仅在适配器被调用时发生。
- 模型/端点只来自后端环境（assistant.settings）；密钥概念对本地路线不存在。
- ChatOllama超时经client_kwargs传给ollama客户端（不可取消的HTTP请求由总预算兜底）。
- 适配为D5的plan协议：模型只产出意图，工具结果一律程序执行。
"""
import json
import os
from pathlib import Path

from .agent import AssistantService, AssistantToolRegistry
from .document_tool import MaintenanceDocumentTool
from .settings import load_settings

DEFAULT_OLLAMA_BASE_URL = 'http://127.0.0.1:11434'
DEFAULT_TIMEOUT_SECONDS = 45.0
PROJECT_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_INDEX_PATH = PROJECT_ROOT / 'docs/verification/m4-real-rag/doe-e5-final'


def specs_to_openai_tools(specs):
    """registry的富规格 → OpenAI function格式（ChatOllama.bind_tools接受）。"""
    tools = []
    for spec in specs:
        tools.append({'type': 'function', 'function': {
            'name': spec['name'],
            'description': spec['description'],
            'parameters': {'type': 'object',
                           'properties': {key: dict(value)
                                          for key, value in spec['properties'].items()},
                           'required': list(spec['required'])}}})
    return tools


def messages_to_langchain(messages):
    from langchain_core.messages import AIMessage, HumanMessage, SystemMessage, ToolMessage
    converted = []
    for message in messages:
        role, content = message['role'], message['content']
        if role == 'system':
            converted.append(SystemMessage(content=content))
        elif role == 'user':
            converted.append(HumanMessage(content=content))
        elif role == 'assistant':
            pending_calls = message.get('tool_calls')
            if pending_calls:
                converted.append(AIMessage(
                    content=content or '',
                    tool_calls=[{'id': str(call['id']), 'name': call['name'],
                                 'args': dict(call.get('arguments') or {})}
                                for call in pending_calls]))
            else:
                converted.append(AIMessage(content=content))
        elif role == 'tool_result':
            converted.append(ToolMessage(
                content=json.dumps(content, ensure_ascii=False, default=str),
                tool_call_id=str(message.get('id') or 'tool')))
        else:
            raise ValueError(f'unknown message role: {role}')
    return converted


class LangChainModelAdapter:
    """把D5的plan(messages, tool_specs)协议适配到LangChain聊天模型。

    工具调用统一走bind_tools（OpenAI兼容协议）；子类只负责构造客户端。
    """

    def __init__(self, settings, timeout_seconds=None, client=None):
        self.model_name = settings.model
        if client is not None:
            self._client = client
            return
        self._client = self._build_client(settings, timeout_seconds)

    def _build_client(self, settings, timeout_seconds):
        from langchain_ollama import ChatOllama
        return ChatOllama(
            model=settings.model,
            base_url=settings.base_url or DEFAULT_OLLAMA_BASE_URL,
            client_kwargs={'timeout': float(timeout_seconds or DEFAULT_TIMEOUT_SECONDS)})

    def plan(self, messages, tool_specs):
        converted = messages_to_langchain(messages)
        client = (self._client.bind_tools(specs_to_openai_tools(tool_specs))
                  if tool_specs else self._client)
        response = client.invoke(converted)
        tool_calls = getattr(response, 'tool_calls', None) or []
        if tool_calls:
            return {'tool_calls': [
                {'id': str(call.get('id') or f'tc-{index}'),
                 'name': call['name'],
                 'arguments': dict(call.get('args') or {})}
                for index, call in enumerate(tool_calls, 1)]}
        text = getattr(response, 'text', None)
        if not text:
            text = response.content if isinstance(response.content, str) \
                else str(response.content)
        return {'text': text}


class OpenAICompatibleAdapter(LangChainModelAdapter):
    """云API路线：任何OpenAI兼容端点（智谱/DeepSeek等），密钥只存在settings。"""

    def _build_client(self, settings, timeout_seconds):
        if not settings.base_url:
            # 避免静默回落到付费的默认OpenAI端点；供应商必须显式声明。
            raise ModelProviderError(
                '云API路线需要设置ASSISTANT_BASE_URL'
                '（如 https://open.bigmodel.cn/api/paas/v4/）')
        from langchain_openai import ChatOpenAI
        return ChatOpenAI(
            model=settings.model,
            api_key=settings.api_key,
            base_url=settings.base_url,
            timeout=float(timeout_seconds or DEFAULT_TIMEOUT_SECONDS),
            max_retries=1)


class ModelProviderError(RuntimeError):
    """供应商配置不完整时的明确报错；不猜测默认供应商。"""


def build_model(settings, timeout_seconds=None):
    """路由规则：配置了ASSISTANT_API_KEY走云API（OpenAI兼容），否则走本地Ollama。"""
    if settings.api_key:
        return OpenAICompatibleAdapter(settings, timeout_seconds=timeout_seconds)
    return LangChainModelAdapter(settings, timeout_seconds=timeout_seconds)


def build_assistant_service(environ=None, index_path=None, db_path=None,
                            timeout_seconds=None, business_tools=None,
                            document_tool=None):
    """按部署环境装配真实服务；未配置模型返回None（API层转503）。

    ASSISTANT_INDEX / ASSISTANT_DB 可覆盖默认索引与业务库路径；chat请求不可触及。
    """
    settings = load_settings(environ)
    if settings is None:
        return None
    env = environ if environ is not None else os.environ
    index = index_path or env.get('ASSISTANT_INDEX') or DEFAULT_INDEX_PATH
    if business_tools is None:
        from .tools import ReadOnlyTools
        business_tools = ReadOnlyTools(db_path=db_path) if db_path else ReadOnlyTools()
    if document_tool is None:
        from .rag_embeddings import LocalEmbedder
        document_tool = MaintenanceDocumentTool(index, LocalEmbedder('e5'))
    model = build_model(settings, timeout_seconds=timeout_seconds)
    return AssistantService(model, AssistantToolRegistry(business_tools, document_tool))
