# Embedding task report — 2026-09-18

## Files and contract

- Added `assistant/rag_embeddings.py`, `tests/test_rag_embeddings.py`; updated `pyproject.toml` and `uv.lock`.
- `LocalEmbedder('e5'|'bge', download=False, cache_dir=None, *, batch_size=8, threads=2)`.
- Local cache defaults to project `.cache/rag-models`; no runtime downloads unless explicitly enabled. Downloads use immutable revision, an allowlist of tokenizer/config/safetensors resources and two workers. No pickle weights or remote code.
- `tokenizer.encode` returns complete input IDs including special tokens by default. Formatting is separate: `embed` receives already formatted strings, does not add prefixes, refuses >512 tokens before model inference, uses CPU float32, eval/inference mode, batched execution, L2 normalization.
- Signature records model, revision, pooling, both prefixes, dimension, max length, normalization, special-token handling, CPU/dtype and versions of torch/transformers/tokenizers/safetensors.
- HF telemetry disabled (including already-imported library constants); tokenizer parallelism and Xet disabled. No LLM, LangChain or online inference.

## Official source verification

Official model repositories/API queried on 2026-09-18; model card examples inspected at these exact commits:

- [E5 model card](https://huggingface.co/intfloat/multilingual-e5-small/blob/614241f622f53c4eeff9890bdc4f31cfecc418b3/README.md): 384 dimensions, attention-mask mean pooling, English query/passage prefixes for all languages, L2 normalization, 512 token maximum.
- [BGE model card](https://huggingface.co/BAAI/bge-small-zh-v1.5/blob/7999e1d3359715c523056ef9478215996d62a620/README.md): Chinese small model has **512 dimensions**, CLS pooling and L2 normalization; recommended Chinese retrieval query instruction is configured, passage has no instruction.
- The cards demonstrate truncation; this project intentionally rejects excess tokens to honor its source-preservation contract.

Expected model.safetensors LFS SHA256 from official API `revision/<commit>?blobs=true`:

| Model | Bytes | SHA256 |
| --- | ---: | --- |
| e5 | 470641600 | 1a55775f53449dac10a2bcbc312469fac40b96d53198c407081a831f81c98477 |
| bge | 95827648 | 354763b9b1357bc9c44f62c6be2276321081ed2567773608c0d0785b61d5a026 |

## Dependencies

- Added exact pins: transformers 4.57.6, torch 2.10.0, chromadb 1.5.5, sentencepiece 0.2.1.
- Existing tokenizers 0.22.2 retained. uv resolved previously installed huggingface-hub 1.32.0 to 0.36.2 to meet Transformers 4.x compatibility. Original project's direct dependencies retained.
- Chroma 1.5.5 verified to expose `Client.close()` and `create_collection(configuration=..., embedding_function=None)`; parent owns cosine/persistence implementation and checks.

## Validation

- RED observed before implementation: module contract failure and missing-module errors, real tests skipped until weights available.
- Initial GREEN: three offline contract tests passed, opt-in real weight test skipped.
- Existing knowledge tests: 24 passed.
- BGE real inference completed: query bearing overheating vs maintenance passage cosine 0.65225, unrelated fruit 0.10022; dimension 512. This is a smoke check, not a retrieval benchmark.
- Full real-model command: `RUN_REAL_EMBEDDINGS=1 .venv/bin/python -m unittest discover -s tests -p test_rag_embeddings.py`: all 4 tests passed, including both real weights, official pooling recipe equivalence, unit norms, finite vectors, semantic ordering, individual/batch invariance, exactly-512 acceptance, 513-token and long-input rejection, and empty/malformed-list handling.
- Both local model.safetensors files matched the official LFS byte sizes and SHA256 hashes in the table above (computed with Python hashlib.file_digest).
- SentencePiece's SWIG bindings emit upstream DeprecationWarning messages during unittest; no test failure. Tests never use fake/random/hash embeddings for model acceptance.
- Ordinary regression execution keeps the real-model test opt-in and never downloads weights; use the explicit command above for model acceptance. Parent owns combined/full regression and real corpus benchmark.
