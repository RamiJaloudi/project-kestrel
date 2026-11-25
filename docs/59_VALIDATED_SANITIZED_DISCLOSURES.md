# Gate 2 increment 2 - Validated sanitized disclosures

[DEMO] Local flattened-text disclosure workflow. Original document permissions and source bytes are unchanged. This is not layout-preserving redaction of original PDFs or native Office containers.

## Implemented

1. Firm -> Documents -> View evidence -> Redaction & sanitized disclosure. Select exact zero-based Unicode ranges in existing extracted units, preview proposed removals, and submit an immutable plan with safe title, audience, purpose, expiry and rationale. Preview strike-throughs do not remove original bytes. Adjusting a plan creates a new proposal.
2. Another source-cleared lawyer approves/rejects the exact plan hash. Whole-document review, confirmed text and verified OCR where relevant are required before building output.
3. Build & validate transcript reconstructs a new PDF from sanitized text. Original PDF/Office images, attachments, annotations, active content, metadata and original container objects are not copied. Hidden/very-hidden worksheets are omitted. Native DOCX/XLSX/XLSM disclosure is not supported; no cosmetic or hidden-row security claim is made.
4. Disclosures shows the validated artifact and internal manifest. An independent senior lawyer (Legal SME role) approves the exact output bundle. Clean-team/competitive content additionally needs a separate antitrust counsel; author, builder and legal/antitrust approvers cannot collapse into self-approval. Approvers' current account, role, matter/wall and source authority are rechecked on external access.
5. Halden/Castlegate see only artifacts approved for their own organization and unexpired purpose. The existing reader loads the sanitized PDF/text; metadata and citation locators refer to the derivative, never the original. Original-source routes remain denied. Root Admin has no content/approval override.
6. External Questions includes only approved derivative text in addition to already-approved report/finding releases. Cached answers reauthorize their exact citations; reclassification or revocation denies prior cited answers. No source index is substituted for a derivative query. This remains bounded keyword retrieval, not a vector/BM25 implementation.

The central PDP has a dedicated sanitized_document branch backed by an actual immutable artifact, validation, exact source snapshot and approval evidence. Merely setting a sanitized flag or resource type does not grant access. Whole-source privileged/legal-advice records cannot be routed to Castlegate. Labelled restricted passages must be fully covered by removal ranges. Whole-source personal-data/export-controlled labels require scope refinement rather than automatic declassification. Whole-source clean-team context requires explicit independent antitrust review of the exact reconstruction. Source restrictions themselves are never removed.

## Validation and limitations

The adapter creates a new PDF container from sanitized text only, then reopens it with pypdf and validates text reconstruction, removed-text absence, generic metadata, no name trees/attachments, no forms/annotations, no images or action entrypoints. Repeated removed tokens must also disappear elsewhere, including the safe title. The lexical leakage check is conservative for removed tokens of at least eight normalized characters; exact range deletion does not rely on that threshold. Human reviewers remain responsible for semantic inference, context and unidentified sensitive data. There is no claim of general automated de-identification or production penetration certification.

The private manifest pins original source/version byte and text hashes, source policy snapshot, removal coordinates/quote hashes, independent reviewer/rationale/time, reconstruction tool/version/time, omissions and antitrust requirement. Artifact bytes, text, manifest and bundle hashes bind independent release decisions. External responses do not disclose original IDs, locators, private rationales or manifests. Outputs are explicitly text transcripts: original layout, signatures, images, charts and attachments are not faithfully reproduced. Email/XLS/XLSM and arbitrary attachment ingestion remain unsupported by the original importer; this increment does not silently broaden its supported formats.

A changed source snapshot immediately denies future derivative reads/downloads/listing/retrieval; there are no persistent anonymous service links to leave active. ContentLabelImpact retains the exposure-review record. For sanitized artifacts, a source-cleared recorded senior approver is assigned an idempotent specialized_legal task with durable notifications when still eligible; otherwise it stays unassigned for a cleared user to route. Existing task accept/start/pause/reassign/complete history handles its disposition. Closing a task does not publish a replacement. Explicit revocation is append-only and can deny future access after signing without rewriting signed content. Downloaded copies cannot be recalled.

## Data, operations and rollback

Migration 0031 adds six immutable tables: disclosure_plans, disclosure_plan_reviews, disclosure_artifacts, disclosure_validations, disclosure_decisions and content_impact_tasks. Source-linked records retain prior restrictions. Future signing manifest schema 8 captures records/byte hashes while excluding raw binary data from JSON hashing. Normal business changes are frozen at signing; access revocation remains possible. Existing historical manifests are not rewritten. A stale earlier pending signature must be reproposed.

Reconstruction uses the already-bundled local ReportLab runtime with a 30-second timeout and bounded output/validation; source originals never enter the renderer, only sanitized text. No paid AI call, public deployment, new service process or test identity bypass was introduced. API/Swagger group: /docs/disclosures (10 operations); counsel routing extends /docs/content-labels. Start/Stop comments and all three portal navigation menus are updated. The reader tool panels have a capped side-by-side layout to preserve document space; the final compact styling passed TypeScript/Vite build.

Populated downgrade refuses to discard retained disclosure records. Prefer forward repair and retain the verified encrypted pre-migration archive. Restoring an older archive is a separate controlled recovery, never an automatic overwrite. Runtime files remain outside the logical database backup.

## Verification evidence

- Focused disclosure/task/label/lifecycle matrix: 21 passed after correcting the task-creation transaction option. Additional manual counsel-routing/idempotency/admin-denial case: 1 passed. Counts overlap with wider runs.
- PostgreSQL isolated-schema disclosure/label matrix: 10 passed after correcting the binary column mapping to BYTEA. Prior failed runs were retained; no live migration was attempted with their failing DDL.
- Full stable regression: 263 passed, 1 skipped, 456.68 seconds; see .runtime/disclosure-final-regression.txt. The additional counsel-routing case was added after collection and passed separately.
- TypeScript/Vite production build passed. Browser verified the new Disclosures navigation/page and a local-only removal-range preview in the preserved reader. No live plan, classification, approval or public release was created. Preview: outputs/redaction-reader-controls.jpg (captured before the final bounded two-column tool-panel style adjustment).
- A synthetic reconstruction was rendered with bundled Poppler and visually inspected: output/pdf/sanitized-transcript-qa.pdf and its page PNG. Its removed token is absent from both extracted and visible text; validation JSON is adjacent. This filesystem QA artifact is not a published application release.
- Read-only normal-session live check: zero current artifacts, 10 Swagger operations, Resources guide, Root Admin content denial and bank/client audience isolation. Receipt: .runtime/prompt-audit/disclosures-live-readonly.json.
- Restore-verified encrypted backup: 104 tables / 14,855 rows. Rehearsal and application preserved all 103 prior application-table digests, 17 source versions, 16 logical documents and 17 version links. Existing identity/checklist backfills replayed twice without change.
- Migration SHA-256: 78f8e57b239a8c1d05a5dceabdf4d6515ba88044c7018ffd7f3dfd281f5d00bd. Receipts: .runtime/prompt-audit/disclosures-migration-*. Services restarted and report ready.

## Remaining scope

Layout-preserving PDF page redaction, native Office-container sanitization, image/attachment coordinate editing, original-label relaxation and production-scale/independent penetration certification remain unavailable. The implemented safe output is a rebuilt text-only PDF with independent release gates. Gate 3 adds true BM25/semantic/hybrid routing and typed financial facts; Gate 4 retains React DataTables/reader comparisons; Gate 5 retains LangGraph orchestration and versioned agent governance.
