# 09 — Document ingestion, AI extraction, search and evaluation

## Wave ingestion
Source VDR mock/API: manifest with stable source ID, path, document version, source timestamps, checksum, access label, maybe extraction permission. Idempotent import by `(source_id, source_version, checksum)`. Batch jobs with retry/failure queue, lifecycle status and source lineage. Process PDF/DOCX safely, malware/size checks, page mapping; OCR scanned pages only; detect German; preserve **original language** and document bytes, optional English translation as *separate derived artifact*. Never replace original span with translation.

## Document routing
Classify commercial/customer contracts, licenses/IP, employment, real estate, finance, litigation, corporate records, unknown. Assign playbooks for **document type + known jurisdiction + matter context**, but keep `document_language`, `governing_law`, and `applicable_regimes` as independent, each with confidence and whether express/inferred/unknown. Unknown law triggers legal review, not false certainty.

## Batch AI risk extraction (separate from RAG)
Apply *approved playbook versions* across prioritized documents; structured Pydantic outputs `{rule_id, risk_category, candidate_text, proposed_severity, evidence_span_id, reasoning_summary, uncertainty, escalation}`; never accept a model's self-generated quote as proof. Evidence verifier compares document-version/page/original span. If unverifiable -> `needs_evidence_review`, no auto client release. AI suggestions are never final legal conclusions.

## Q&A over documents, not a substitute for comprehensive review
Select authorized corpus using matter/label/wall/clean-team/published visibility **before** retrieval and LLM. Hybrid keyword + semantic retrieval with metadata filters, optional reranking; expose accessible citations only. External client/bank queries should use *explicitly released, audience-safe material* and avoid direct internal/privileged sources. No answer -> say unverified/unavailable, not invented.

## Legal research track
Do not use Westlaw/Practical Law full texts unless the subscription explicitly allows downstream AI/embedding. User has Westlaw Next only and lacks the separate Practical Law materials; use own issue summaries with citation pointers and publicly available legislation/official guidance subject to reuse and currency checks. Legal researchers verify authorities/versions; legal SMEs adjudicate applicability.

## Evaluation/sizing
Coverage: track by version wave, language, classification, attempted/reviewed/published status. Measure at least: OCR word/page quality and failure rate, candidate precision/recall against legal SME-labeled synthetic/approved test set, citation exact-match, misclassification, unauthorized retrieval zero-leak, attorney correction rate, per-document processing time, token/OCR cost. 12k docs/400k pages is forecast, not a throughput promise; prioritize high-risk customer contracts and reported board needs. Queue with retries/circuit breakers, partial results + uncertainty, prompt/version traceability, cache by content hash if permitted, no full corpus prompt dump. Calibrate thresholds with legal counsel.

## CAL
Continuous Active Learning from eDiscovery may assist review prioritization when relevance labels and evaluation support it, but **it is not the default M&A contract-extraction engine** and must not be confused with a BERT contract classification project. Model training/fine-tuning not required for MVP.
