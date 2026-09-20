"""助手模型配置合同。只从后端环境读取三个变量；chat请求不能覆盖。

ASSISTANT_MODEL 必填；ASSISTANT_BASE_URL / ASSISTANT_API_KEY 仅确需时存在。
本模块不导入任何网络库、不发起请求：只做纯配置解析与脱敏日志视图。
供应商适配（model_provider）待D4运行方式确认后另建，不在本模块假设。
"""
import os
from dataclasses import dataclass
from urllib.parse import urlsplit

ASSISTANT_MODEL_ENV = 'ASSISTANT_MODEL'
ASSISTANT_BASE_URL_ENV = 'ASSISTANT_BASE_URL'
ASSISTANT_API_KEY_ENV = 'ASSISTANT_API_KEY'


class ModelNotConfigured(RuntimeError):
    """模型配置缺失时的一致报错；不猜测默认供应商或密钥。"""


@dataclass(frozen=True)
class ModelSettings:
    model: str
    base_url: str | None = None
    api_key: str | None = None

    def to_log_dict(self):
        """日志安全视图：密钥绝不出现，端点只留主机名。"""
        host = None
        if self.base_url:
            host = urlsplit(self.base_url).hostname or 'unparsed-endpoint'
        return {'model': self.model, 'base_url_host': host, 'api_key_set': self.api_key is not None}

    def __str__(self):
        return f'ModelSettings({self.to_log_dict()})'

    __repr__ = __str__


def load_settings(environ=None):
    """从给定环境（默认 os.environ）读取配置；未配置模型时返回 None。纯函数，无网络。"""
    env = os.environ if environ is None else environ
    model = env.get(ASSISTANT_MODEL_ENV, '')
    if not isinstance(model, str):
        raise TypeError('environ values must be strings')
    model = model.strip()
    if not model:
        return None
    base_url = env.get(ASSISTANT_BASE_URL_ENV, '').strip() or None
    api_key = env.get(ASSISTANT_API_KEY_ENV, '').strip() or None
    return ModelSettings(model=model, base_url=base_url, api_key=api_key)


def require_settings(environ=None):
    settings = load_settings(environ)
    if settings is None:
        raise ModelNotConfigured(
            '助手模型未配置：请通过后端环境变量 ASSISTANT_MODEL 指定模型'
            '（如需自定义端点再设置 ASSISTANT_BASE_URL / ASSISTANT_API_KEY）')
    return settings


def load_env_file(path, environ=None):
    """把 .env 的 KEY=VALUE 读入给定环境（默认 os.environ）。

    不覆盖已存在的变量；空行/#注释/无等号的行跳过；值支持成对引号剥离。
    返回实际设置的键名列表。键永不写入日志。
    """
    import os
    from pathlib import Path
    env = os.environ if environ is None else environ
    target = Path(path)
    if not target.is_file():
        return []
    loaded = []
    for line in target.read_text(encoding='utf-8').splitlines():
        stripped = line.strip()
        if not stripped or stripped.startswith('#') or '=' not in stripped:
            continue
        key, _, value = stripped.partition('=')
        key = key.strip()
        value = value.strip()
        if len(value) >= 2 and value[0] == value[-1] and value[0] in ('"', "'"):
            value = value[1:-1]
        if not key:
            continue
        if key not in env:
            env[key] = value
            loaded.append(key)
    return loaded
