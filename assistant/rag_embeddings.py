"""Pinned, CPU-only local embedding models with explicit retrieval formatting."""
from __future__ import annotations

import os
from pathlib import Path
from importlib.metadata import version

# Set before importing Hugging Face libraries; no inference telemetry or remote code.
os.environ['HF_HUB_DISABLE_TELEMETRY'] = '1'
os.environ['DO_NOT_TRACK'] = '1'
os.environ['TOKENIZERS_PARALLELISM'] = 'false'
os.environ['HF_HUB_DISABLE_XET'] = '1'

DEFAULT_CACHE = Path(__file__).resolve().parents[1] / '.cache' / 'rag-models'
MODEL_SPECS = {
    'e5': {
        'model': 'intfloat/multilingual-e5-small',
        'revision': '614241f622f53c4eeff9890bdc4f31cfecc418b3',
        'pooling': 'attention_mask_mean',
        'query_prefix': 'query: ', 'passage_prefix': 'passage: ',
        'dimension': 384,
    },
    'bge': {
        'model': 'BAAI/bge-small-zh-v1.5',
        'revision': '7999e1d3359715c523056ef9478215996d62a620',
        'pooling': 'cls',
        'query_prefix': '为这个句子生成表示以用于检索相关文章：', 'passage_prefix': '',
        'dimension': 512,
    },
}
_DOWNLOAD_FILES = ['config.json', 'model.safetensors', 'tokenizer.json',
                   'tokenizer_config.json', 'special_tokens_map.json',
                   'sentencepiece.bpe.model', 'vocab.txt']


class LocalEmbedder:
    """Use download=True explicitly once, then load solely from the local cache.

    ``embed`` accepts already formatted strings; formatting and length counting
    belong to callers so chunk budgets include every prefix and special token.
    """

    def __init__(self, model_key='e5', download=False, cache_dir=None, *,
                 batch_size=8, threads=2):
        if model_key not in MODEL_SPECS:
            raise ValueError(f'Unknown embedding model: {model_key!r}; use e5 or bge')
        if type(batch_size) is not int or not 1 <= batch_size <= 64:
            raise ValueError('batch_size must be an integer between 1 and 64')
        if type(threads) is not int or not 1 <= threads <= 8:
            raise ValueError('threads must be an integer between 1 and 8')
        self.model_key = model_key
        self.batch_size = batch_size
        self.spec = dict(MODEL_SPECS[model_key])
        self.cache_dir = Path(cache_dir) if cache_dir is not None else DEFAULT_CACHE
        from huggingface_hub import snapshot_download, constants
        constants.HF_HUB_DISABLE_TELEMETRY = True
        constants.HF_HUB_DISABLE_XET = True
        from huggingface_hub.errors import LocalEntryNotFoundError
        try:
            local = snapshot_download(
                self.spec['model'], revision=self.spec['revision'],
                cache_dir=str(self.cache_dir), local_files_only=not download,
                allow_patterns=_DOWNLOAD_FILES, max_workers=2,
            )
        except LocalEntryNotFoundError as error:
            raise FileNotFoundError(
                f"Model {model_key} is not cached; explicitly use download=True first"
            ) from error
        if not (Path(local) / 'model.safetensors').is_file():
            raise FileNotFoundError(f'Model {model_key} weights missing; use download=True')
        import torch
        from transformers import AutoModel, AutoTokenizer
        torch.set_num_threads(threads)
        self._torch = torch
        self.tokenizer = AutoTokenizer.from_pretrained(
            local, local_files_only=True, trust_remote_code=False,
        )
        self._model = AutoModel.from_pretrained(
            local, local_files_only=True, trust_remote_code=False,
            use_safetensors=True,
        ).to('cpu').eval()
        if self._model.config.hidden_size != self.spec['dimension']:
            raise ValueError('Loaded model dimension does not match pinned signature')
        self.signature = {
            **self.spec, 'normalize': 'l2', 'max_length': 512,
            'special_tokens': True, 'dtype': 'float32', 'device': 'cpu',
            'libraries': {name: version(name) for name in
                          ('torch', 'transformers', 'tokenizers', 'safetensors')},
        }

    def format_passage(self, text: str) -> str:
        if not isinstance(text, str):
            raise TypeError('passage must be a string')
        return self.spec['passage_prefix'] + text

    def format_query(self, text: str) -> str:
        if not isinstance(text, str):
            raise TypeError('query must be a string')
        return self.spec['query_prefix'] + text

    def embed(self, texts: list[str]) -> list[list[float]]:
        if not isinstance(texts, list) or any(not isinstance(t, str) for t in texts):
            raise TypeError('embed requires a list of fully formatted strings')
        # Validate the complete request before computing any vectors. Never truncate.
        for index, text in enumerate(texts):
            count = len(self.tokenizer.encode(text, add_special_tokens=True,
                                              truncation=False, verbose=False))
            if count > 512:
                raise ValueError(f'Embedding input {index} has {count} tokens; maximum is 512')
        result = []
        torch = self._torch
        with torch.inference_mode():
            for start in range(0, len(texts), self.batch_size):
                batch = self.tokenizer(texts[start:start+self.batch_size],
                                       padding=True, truncation=False, return_tensors='pt')
                hidden = self._model(**batch).last_hidden_state
                if self.spec['pooling'] == 'cls':
                    pooled = hidden[:, 0]
                else:
                    mask = batch['attention_mask']
                    pooled = hidden.masked_fill(~mask[..., None].bool(), 0).sum(dim=1)
                    pooled = pooled / mask.sum(dim=1)[..., None]
                normalized = torch.nn.functional.normalize(pooled, p=2, dim=1)
                if not torch.isfinite(normalized).all():
                    raise ValueError('Model produced non-finite embeddings')
                result.extend(normalized.tolist())
        return result
