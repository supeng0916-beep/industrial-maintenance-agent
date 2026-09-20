"""Pinned BGE tokenizer only: no weights, Transformers, or remote Python code."""
import hashlib
import importlib.metadata
import json
import os
from pathlib import Path
import tempfile
from urllib.request import urlopen

MODEL_ID = 'BAAI/bge-small-zh-v1.5'
REVISION = '7999e1d3359715c523056ef9478215996d62a620'
FILES = {
    'tokenizer.json': '48cea5d44424912a6fd1ea647bf4fe50b55ab8b1e5879c3275f80e339e8fae26',
    'tokenizer_config.json': 'e6f3b96db926a37d4039995fbf5ad17de158dfb8f6343d607e4dbaad18d75f5a',
}
DEFAULT_CACHE = Path(__file__).resolve().parents[1] / '.cache' / 'knowledge-tokenizer'


class BGETokenizer:
    def __init__(self, backend, file_records):
        self.backend = backend
        self.info = dict(model_id=MODEL_ID, revision=REVISION, files=file_records,
                         library='tokenizers', library_version=importlib.metadata.version('tokenizers'),
                         model_max_length=512, add_special_tokens=True, truncation=False,
                         document_query_instruction=False)

    def encode(self, text, *, add_special_tokens=True):
        return self.backend.encode(text, add_special_tokens=add_special_tokens).ids


def load_tokenizer(cache_dir=DEFAULT_CACHE, *, download=False):
    """Offline by default; only explicit download may fetch two hash-pinned files."""
    folder = Path(cache_dir) / REVISION
    records = []
    for name, expected in FILES.items():
        path = folder / name
        if path.exists():
            raw = path.read_bytes()
        elif download:
            url = f'https://huggingface.co/{MODEL_ID}/resolve/{REVISION}/{name}'
            try:
                with urlopen(url, timeout=30) as response:
                    raw = response.read(2_000_001)
            except OSError as exc:
                raise ValueError(f'tokenizer download failed: {name}: {exc}') from exc
            if len(raw) > 2_000_000:
                raise ValueError(f'tokenizer file unexpectedly large: {name}')
        else:
            raise ValueError(f'tokenizer resource missing: {path}; use --download-tokenizer once')
        if hashlib.sha256(raw).hexdigest() != expected:
            raise ValueError(f'tokenizer SHA256 mismatch: {name}; cache is unchanged')
        if not path.exists():
            folder.mkdir(parents=True, exist_ok=True)
            fd, temp = tempfile.mkstemp(prefix='.download-', dir=folder)
            try:
                with os.fdopen(fd, 'wb') as handle:
                    handle.write(raw)
                os.replace(temp, path)
            finally:
                if os.path.exists(temp): os.unlink(temp)
        records.append(dict(name=name, sha256=expected, bytes=len(raw)))
    config = json.loads((folder / 'tokenizer_config.json').read_text())
    if config['model_max_length'] != 512:
        raise ValueError('tokenizer model_max_length is not 512')
    try:
        from tokenizers import Tokenizer
    except ImportError as exc:
        raise ValueError('tokenizer dependency missing; run uv sync --locked') from exc
    backend = Tokenizer.from_file(str(folder / 'tokenizer.json'))
    backend.no_truncation()
    backend.no_padding()
    return BGETokenizer(backend, records)
