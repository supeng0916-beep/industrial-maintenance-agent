# SDD ledger — plan: docs/superpowers/plans/2026-09-18-real-rag-baseline.md
| Task | Owned files/interfaces | Decision |
| --- | --- | --- |
| Chunking | knowledge_documents.py optional metadata; new rag_chunks.py + tests | Do not alter old knowledge_chunks strategy |
| Embedding | rag_embeddings.py, dependency pins + tests | Fixed real weights, signature, full input no truncation |
| Index/CLI | rag_index.py, rag.py, rag_evaluation.py + tests | Chroma cosine local, new-dir atomic publication |
Ruling: user explicitly requested parallel responsibilities; independent implementation agents own disjoint files. No Git exists; retain authorized workspace, do not create repository.
Shared contract: build_rag_chunks(documents, tokenizer, format_passage=callable)->list[dict]; tokenizer.encode raw full input; embedding_text already formatted with model passage prefix; context_text explicitly repeated source context; source ranges map original_text without duplication.
Embedding contract: LocalEmbedder(model_key='e5'|'bge', download=False, cache_dir optional); .signature dict; .tokenizer.encode raw strings; .format_passage/.format_query; .embed(list of fully formatted strings)->list[list[float]], strict <=512. No prefixes inside embed.

Task chunking: complete — v4, optional metadata, explicit context/provenance, safe bounded splits, final independent review passed.
Task embedding: complete — E5/BGE actual fixed weights, official hash verified, offline CPU, real tests passed.
Task index/CLI: complete — Chroma cosine, signatures/inventory checks, build/query/evaluate, frozen final artifacts.
Final: 196 full tests passed in84.103s with RUN_REAL_EMBEDDINGS=1. E5 113 chunks/BGE131, same15documents30pages. 44 cases evaluated once per final model. Main independent integration review passed. No additional feature work or benchmark reruns.
