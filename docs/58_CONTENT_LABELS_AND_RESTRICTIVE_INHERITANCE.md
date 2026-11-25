# Gate 2 increment 1 — Content labels and restrictive inheritance

[DEMO] Local classification foundation, 23 November 2026. This is not completed redaction or Freshfields production readiness.

## Implemented workflow

In Firm → Documents → View evidence, expand **Content labels & passage classification** in the existing `DocumentReader.tsx`. Select overlapping context/restriction labels, an exact range in the current extracted unit or the whole document, and a rationale. Offsets are zero-based Unicode code points, with exclusive end. The server derives the quote from immutable text, checks bounds and pins original byte/text hashes. PDF pages, Word paragraphs/table rows and Excel extracted rows use the existing locator system. Native cell-coordinate, image, attachment and object selectors are not implemented here.

Supported labels: legal, financial, mixed, commercial, corporate, operational, privileged, clean_team, competitively_sensitive, personal_data, export_controlled, ai_restricted and bank_eligible. Labels are independent and may overlap. Bank eligibility describes context only and never grants access. Language and governing law remain separate source facts. Jurisdiction/legal-hold assertion workflows remain future work; content labels do not set or remove lifecycle legal holds.

This increment records **human** proposals with `human-assertion-v1` provenance and no fabricated confidence/model version. It does not add a live AI classifier. AI classification adapters must later write through this same governed restriction path; untrusted model output cannot grant permissions.

Assertions are PROPOSED, then independently CONFIRMED by a source-cleared Legal SME, or CONTESTED by a cleared lawyer. A contest retains all protective restrictions. There is deliberately no remove/reject/supersede endpoint that weakens access. Controlled relaxation with separate legal/antitrust decisions is the next increment. Original source bytes, legal findings and existing approvals are not replaced.

## Policy and traceability

Every assertion is evaluated through the shared document PDP over original/derived lineage. Sensitive or competitive labels require an explicit active named clean-team scope, including for the proposer. Proposed/contested restrictions apply immediately to the whole original and its derived findings/report lineage; the reader does not expose selected ordinary passages to someone denied the complete original. Unknown or inconsistent attributes return CONTENT_ATTRIBUTES_INDETERMINATE and deny. Walls and matter validation remain prerequisites. AI-restricted, personal-data and export-controlled assertions prevent analysis in this conservative baseline. Restricted labels prevent external disclosure pending the future sanitized-artifact workflow.

Attribute and decision hashes enter policy snapshots only when assertions exist. Sources without assertions preserve their earlier snapshot format, so migration alone does not invalidate releases. Any actual attribute change invalidates prior release/grant snapshots and creates an immutable counsel-review impact for each already released descendant. Documents shows a permission-filtered impact inbox. These are retained unassigned review obligations, not completed incident investigation, assigned Action Center tasks or proof that disclosure occurred. Impact disposition, named notification routing and new sanitized-release revisions remain future work. Previously downloaded copies cannot be remotely recalled.

Access logs inherit segment clean-team scopes even if the source's older broad classification is ordinary. Scoped audit export rechecks all current content scopes. The broad source classification column remains separate; inspect the reader labels for the richer content attributes.

Migration 0030 adds immutable `content_label_assertions`, `content_label_decisions` and `content_label_impacts`. Matter locks serialize classification against signing; frozen matters reject new assertions/decisions/impacts. Future signing manifests (schema 7) include these records; retained historical manifests are unchanged. An older pending signing proposal must be reproposed if its schema no longer matches, rather than silently rewritten.

API group: `/docs/content-labels` (four operations). Portal Home and role-specific downloadable Resources guide are updated. Start/Stop use the existing shared API, worker and popup reader; no new service or competing viewer was introduced.

## Verification

- Full regression: **258 passed, 1 skipped**, 394.94 seconds. This run preceded the final clean-team audit-routing hook; the final 20-test matrix below covers that hook. Existing Starlette/httpx deprecation warning remains.
- New workflow tests: **5 passed on PostgreSQL** in isolated schemas, covering exact ranges, unknown labels/state, idempotency, independent confirmation, contest/no-removal, source/reader isolation, clean-team/wall precedence, release invalidation, retained counsel impacts, immutable rows and freeze.
- Final content-label, observability/governance and review-work matrix: **20 passed** on SQLite after audit routing changed, including a new assertion that segment-restricted reader access is categorized under pricing clean-team audit. Counts overlap.
- TypeScript/Vite build passed; popup reader/controls were visually verified using normal SME sign-in. Screenshot: `outputs/content-labels-reader.jpg`.
- Automatic approval review rejected saving a live synthetic proposal because it would change immutable classification/audit state. It was not retried through another interface. Persistence was verified in isolated tests; the live source remains attribute revision 0, with no new classifications or approvals.
- Read-only live verification checked the reader flag, empty unchanged source attributes, scoped impact inbox, Resources guide, OpenAPI's four operations and Root Admin/bank/client denial. Receipt: `.runtime/prompt-audit/content-labels-live-readonly.json`.
- Encrypted pre-migration backup restored with matching inventory: **101 tables / 14,708 rows**. Rehearsal and live application preserved all **100 existing application-table digests**, 17 source versions, 16 logical documents and 17 version links. Identity/checklist backfills replayed twice without changes.
- Migration SHA-256: `84458471a6b7011dbf8efbd6caa8637bb150ab46d7e0b74ed8cab38dd14e6e69`. Receipts: `.runtime/prompt-audit/content-labels-migration-*`. Start/Stop restart succeeded; worker and monitor report ready.

## Next increment and rollback

Next: versioned redaction proposals, physical sanitization and validation, controlled relaxation approvals, counsel-impact disposition/assignment and new audience-scoped derivative identities/releases. PDF text/OCR/attachment removal needs penetration tests; unsafe Office containers must remain blocked or flatten to proven-safe outputs. No visual overlay, metadata flag or bank-eligible label may substitute for sanitized bytes or independent release approval. Audience retrieval must use released derivative content exclusively; originals remain denied.

Populated downgrade refuses to discard label evidence. Prefer a forward repair and preserve the verified encrypted pre-migration archive; never restore automatically over live data. Runtime files are outside the logical DB backup. This local foundation has bounded 200-assertion histories and a 500-row permitted impact view, with no production-scale performance claim. DataTables remains Gate 4; LangGraph remains Gate 5. No paid AI calls or public deployment occurred.
