# Permission-first retrieval — Gate 3 baseline

[DEMO] 24 November 2026. Migration 0032 adds an immutable, source-version/policy-snapshot-bound embedding cache. No embeddings, classifications or approvals are created by migration.

Automatic and lexical search use deterministic BM25 on the permitted corpus. Explicit internal semantic search uses OpenAI text-embedding-3-small, 256 dimensions. Hybrid combines BM25 and cosine rankings with reciprocal-rank fusion. Source access, processing policy and current classification are checked before provider inputs, then checked again before saving results. External search remains lexical over approved releases and sanitized derivatives.

Semantic requests use the existing shared $2 reservation / $10 monthly budget and explicit idempotency keys. No automatic paid retries. Cached answers reauthorize every contributing corpus reference before returning citations, ranking or counts. Ranking is neither legal verification nor legal materiality. Financial SQL queries use the separate verified fact store and are available in Financial mode with explicit typed filters; see docs/02_workflows/61_FINANCIAL_EVIDENCE_AND_RECONCILIATION.md.

Verified: 271 passed / 1 skipped in the full regression; 21 focused tests passed; 7 PostgreSQL retrieval tests passed. Provider calls were mocked: no paid end-to-end embedding call was made. Official interface and pricing references: [embeddings API](https://developers.openai.com/api/reference/resources/embeddings/methods/create.md), [pricing](https://developers.openai.com/api/docs/pricing.md). The pinned input rate is $0.02 per million tokens, rounded conservatively to whole cents locally; this is not an account-wide billing guarantee.

Live migration rehearsal and application preserved all 109 prior application-table digests and the 17 source versions / 16 logical documents / 17 identity links. Receipt files are retained under `.runtime/prompt-audit/retrieval-*`. Existing launchers run retrieval within the shared API; no duplicate API process is needed.

Limits: bounded 400-chunk/200-object corpus; source-only embeddings; no external vector index; no claim of production search quality, OCR accuracy or financial inference. Query routing is explicit and automatic currently selects no-charge BM25. DataTables, reader comparison and governed LangGraph orchestration remain later gates.
