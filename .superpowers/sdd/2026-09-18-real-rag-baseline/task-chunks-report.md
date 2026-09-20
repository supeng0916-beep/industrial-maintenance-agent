# RAG chunking implementation report

Owned files: `assistant/knowledge_documents.py`, `assistant/rag_chunks.py`, `tests/test_rag_chunks.py`.

## Final interface

`build_rag_chunks(documents, tokenizer, *, format_passage=lambda text: text) -> list[dict]`.
`STRATEGY = rag-page-heading-sentence-v4`; `ChunkingError` is the existing compatible exception from knowledge_chunks.
All old chunk fields retained. Adds `context_text`, `source_pages`, `context_source_pages`, `context_sources`, `strategy`.
`embedding_text` already includes formatter/model prefix. `token_count` counts tokenizer.encode with special tokens over the entire formatted input. No truncation; hard limit 512.

`source_pages` is the physical page of original_text, **not** the union of original and context pages. `context_source_pages` records pages of repeated source context; `context_sources` records each repeated text with its own source_pages and kind (`source_context` or `metadata`; metadata entries have a field such as title/applicability). Metadata applicability and global H1 title do not claim to originate from every page. Evaluate original-text anchors against source_pages, and context anchors against each matching context_sources entry.

Optional frontmatter fields accepted with strict nonempty-string type: language, source_url, publisher, source_document_id, applicability, license, source_sha256. source_pages is a list of nonempty strings. Required legacy fields unchanged, unknown fields still rejected, whitelist/hash behavior unchanged.

## Source fidelity and conservative boundary

Exact character/line ranges partition the body; original_text is a contiguous exact source slice without duplicated context. Markdown headings and numeric `## Page N` / `## 第N页` markers supply hierarchy/pages, with metadata source_pages as fallback. Context explicitly labeled repeated source context. Parent headings and all paragraphs under explicitly labeled Scope/Applicability/适用范围/前提 are retained, plus metadata applicability. Multi-paragraph explicit scope accumulates until the relevant heading scope ends; an oversized required scope is never silently dropped. Ordinary if/only/based-on paragraphs are not promoted into section scope. Physical page boundaries clear local scope and prior sidebars. Only a recognizable table/figure caption or a colon-terminated lead-in is repeated for a structural block; an arbitrary preceding paragraph is not repeated. Additionally, the immediately preceding introduction before a Table N caption is retained only when it explicitly references that same Table N or “table below.” This exact local introduction includes page and character-range provenance. A different table number does not match.

Tables, Markdown lists, Unicode bullet (`•` / `–`) items, and fenced blocks remain intact when they fit. Immediately following `Note:`, `Source:`, `*Results...` / `*These...` footnotes are attached to the table before splitting. Oversized numeric tables can split at complete row boundaries, repeating the original column headers, caption, and complete footer in every group. A leading numeric label row with one fewer column than consistently shaped data rows stays in the repeated header. Other inconsistent numeric-row widths are refused instead of guessing a table schema. Long single list items can split at full sentences with the actual item first sentence repeated. Prose callouts explicitly fenced as text, with a blank-separated title, can split at full sentences while repeating the actual title and opening sentence. Repeated structural context includes precise original character offsets as well as pages. Unrecognized structures or single required atoms still exceeding the complete 512-token input raise an error. Prose uses sentence punctuation and excludes common abbreviations such as U.S.; never character windows.

This is deliberately conservative. Oversized atomic tables/lists require reviewed source restructuring or a different model strategy; no safety condition or table footer is removed to fit. The splitter does not claim a language parser or semantic completeness proof; unusual implicit scope in a long paragraph still needs corpus review. Character coverage is a provenance check, not evidence of semantic completeness. In particular, TS12 page-2 tables 2/3 refer to a 50-hp example introduced across pages; this implicit dependency is not automatically inferred or promoted to document-wide scope. Such answers require multiple retrieved evidence spans and source review; no single-chunk semantic completeness is claimed.

## TDD / unit verification

Initial tests failed for absent module and unsupported optional metadata. Follow-up failing tests exposed parent-scope loss, missing following table notes, unsupported Unicode bullets, missing cross-page context provenance, stale sidebar scope across page boundaries, and asterisk footnotes separated by Source credits. Each was corrected before the final suite.

Final command: `.venv/bin/python -m unittest tests.test_rag_chunks tests.test_knowledge_chunks tests.test_knowledge_preview`
Result: 44 tests passed (20 new RAG tests, 24 legacy tests), 2026-09-18.

## Frozen real corpus probe

Manifest SHA256: `2a1da80dca7f618e0b39c19ed77417bc4dc45f1f5655083d10bdbef9b02e15a3`.
Loaded all 15 entries through load_documents, validating hashes. Both actual locally cached tokenizers used with their correct passage formatting. No inference or published index created by this task.

- E5: 15/15 documents chunk successfully, 113 chunks; maximum complete input 512 tokens. ts01 annual savings table retains 8,000 h / 75% / $0.08 note; ts07 table retains motor-specific Results vary caveat; ts11 retains typical-performance and no-standard-test-protocol footnote.
- BGE: 15/15 documents chunk successfully, 131 chunks; maximum complete input 508 tokens. The same 15 documents are retained. ts01/07/11 table footnotes are checked for both tokenizers, and ts11 explicitly checks absence of unrelated centrifugal-fan scope in the table context.
- Historical v2 failure retained: BGE initially rejected ts02 Page 2 at 569 tokens, ts11 at 523, and ts14 at 606. Investigation found overly broad local-scope inheritance, long list text, and a prose callout treated as a table. v3 removes the scope pollution and provides safe structural splitting. No document or safety footnote was removed to make the probe pass.
- Both strategies keep physical source pages exact (`['1']` or `['2']`), with repeated-context provenance separate.
- Different tokenizers produce different chunk counts from the same complete corpus. The index/evaluation comparison must state this chunking difference.
- SOFT_TARGET_TOKENS=300 currently supplies only the over_soft_target diagnostic flag. Packing is greedy under the full 512-token hard limit; this is not a tuned 300-token packing strategy.

Detailed per-document hashes/counts/failures: `chunks-real-probe.json` beside this report. Tokenizers may print a length warning while evaluating an oversized candidate; oversized candidates are rejected or split before emitting model inputs.

No dependency, old chunk strategy, real corpus, data, or running service changes.


## Final v4 review corrections and freeze

- Real TS11 audit found the table remains a single complete data block under both current tokenizers, with all seven numeric load-percentage labels and full footnote present. Thus the v3 numeric-header hazard was latent in the row-splitting fallback rather than triggered in this specific final corpus. A forced-long-table fixture reproduced loss of numeric header labels; v4 preserves the numeric header and refuses inconsistent row shapes. No unsupported claim of a real TS11 split failure is made.
- Explicit multi-paragraph Scope fixture now retains both the model-only restriction and the separate outdoor-use prohibition before a nested table.
- TS07 exact table introduction with 1,800 RPM / 100-horsepower conditions is retained in every actual table-data chunk. TS08's explicit “table below” introduction retains continuously operated / obtainable 2.5-volts example conditions. Local source offsets are recorded, without generalizing these paragraphs into page scope.
- Both full-corpus probes rerun after these changes: E5 15 documents / 113 chunks / max 512; BGE 15 documents / 131 chunks / max 508. `chunks-real-probe.json` records `strategy=rag-page-heading-sentence-v4`, per-document hashes, and targeted semantic checks. No corpus modifications occurred.
- Strategy frozen at v4 for the parent task's fresh build/evaluation. Older v2/v3 prebuilds must not be labeled the final comparison. v3 counts happened to match v4, but content/context and strategy hashes changed.
