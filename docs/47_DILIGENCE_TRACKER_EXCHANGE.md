# Diligence trackers and Excel exchange

[USER DECISION] Database records are authoritative. Excel is an import/export interface. Mixed privileged, clean-team and ordinary data require server-filtered views and separate recipient-approved workbooks. Hidden rows/sheets are not a security boundary.

## User workflow

1. Open **Firm → Diligence Trackers → Excel exchange** and choose a permitted matter. The existing contract/coverage, risk and consent registers remain available beside this tab.
2. Choose **Coverage**, **Reviewed risks** or **Consents** and download a scoped template. It contains at most 100 currently permitted database records and a short Guide. Identifiers are text, expected revisions are numeric and due dates are typed Excel dates. Amber fields are proposals; RecordID and ExpectedRevision must remain unchanged.
3. Edit and upload the synthetic XLSX. The server checks schema, IDs, matter, authorization, duplicates, categories, dates, owners, revision numbers, source policy and coverage prerequisites. Unknown/unavailable rows are redacted in the preview. Formulas, macros, external links, hidden content, merged cells, unexpected sheets and oversized files are rejected. Limits are 3 MiB and 100 nonblank proposal rows.
4. Inspect before/after values, select valid rows, attest review and give a rationale. Previewing writes no register changes. Unchanged rows are identified and cannot create gratuitous versions. Applying selected changed rows creates retained `LegalFindingRevision` or `DocumentReviewVersion` records in one transaction; one invalid/stale/unauthorized selected row prevents the entire selection. An exact repeated request returns the original receipt. Further changes require a new preview. One preview is applied once, including when only a subset was selected.
5. Risk/consent imports update severity, materiality, consent/notice exposure, action status, next action, owner and due date. They preserve the current finding summary, topic and exact source evidence. Use **Risk Review** for new findings, legal reasoning or evidence corrections. A consent import must reference an existing consent-register topic. Owners must be active cleared legal users. Coverage completion requires confirmed extracted text/OCR verification and a decision on all current candidates.
6. Select reviewed records and one named Halden/Castlegate recipient, edit audience wording if necessary and create a separate export draft. Coverage exports require explicit completed whole-document review. Each workbook contains only its selected rows and public columns; evidence-passage columns, internal owner UPNs and source UUIDs are omitted. A summary can contain lawyer-approved quoted wording; omission of the evidence column does not itself classify text as non-sensitive.
7. Another cleared lawyer approves the exact version, recipient, source snapshot and workbook hash. Clean-team lineage additionally requires a separate cleared antitrust approval of sanitized content, followed by a different audience approver. The author cannot approve their own export. Bank privilege exclusion cannot be bypassed by editing public wording.
8. The recipient opens **Trackers** in their portal. Another assigned person at the same employer does not automatically receive the workbook. Every list, detail and download rechecks the shared policy, recipient, walls, matter membership, review/release status and source lineage. A changed finding/source invalidates old external eligibility; generate and approve a new workbook. Revocation blocks future downloads but cannot recall copies already downloaded.

## Persistence and policy

Migration 0023 adds immutable import originals/proposals, application receipts, export bytes/metadata and named recipient scopes. File hashes and exact applied row numbers are retained. Export content hashes bind the public body, recipient and workbook SHA-256. No version is silently overwritten or deleted. Internal draft/historical downloads are labeled in filenames.

The implementation reuses the existing authoritative lawyer/document review services with a transaction option. It introduces no competing tracker truth. Import processing does not call AI, approve a finding candidate or grant external release. Operational edits create new finding versions and therefore require new approval for affected downstream packages, even when the summary itself is unchanged.

Named recipient scopes are enforced centrally in `services/documents.py`, including contributing lineage and the ordinary release routes. Recipient rows are included in approval snapshots only when present, preserving historical snapshot hashes for older packages. Root Admin has no source-data override. Tracker originals, receipts, exports and recipient scopes are included in signing manifests; signing freeze blocks new imports/exports. Audit categories inherit clean-team restrictions.

## Workbook engine and operations

The local workbook adapter uses the bundled `@oai/artifact-tool` through a bounded Node subprocess. `openpyxl` is used for reading/validation, not authoring these workbooks. Plaintext payloads travel through pipes and are excluded from normal logs. The adapter checks generated workbooks for formulas. The builder prefixes formula-like literal strings and preserves identifier text before assigning values. Temporary builder files/inspection sidecars are removed after the pipe result; retained originals and approved export bytes remain in PostgreSQL.

Runtime paths are local configuration in `.runtime/tracker-workbook-runtime.json`, with optional `KESTREL_ARTIFACT_NODE` and `KESTREL_ARTIFACT_MODULES` environment overrides. Start prepares a local module junction. No package downloads or provider credentials are needed. If the runtime is unavailable, workbook generation returns a clear 503; no fabricated file is returned. The runtime is a local desktop dependency, not an assertion that Azure already has a licensed or configured equivalent. Public/portable deployment remains a separate gate.

Start and Stop retain the five real components and database tools. The tracker API is part of the shared backend; Swagger is `/docs/trackers`. Start seeds a separate tracker lab once and preserves later user decisions, credentials, main matter data and Wave 2. No paid AI call occurs during seeding or tracker processing.

## Synthetic walkthrough

Matter **054323-100001** contains two source versions, three manually reviewed synthetic findings and explicit document coverage. One source is privileged Halden-only legal advice. The local folder is `C:\Freshfields-Takehome\Synthetic_Data\Tracker_Lab`.

- `tracker_next_updates.xlsx`: a valid proposal against the current consent finding revision.
- `tracker_validation_examples.xlsx`: a valid row, invalid date, duplicate record IDs and an unavailable record.

The explicit `verify_tracker_lab.py` smoke test stages/applies one proposal, verifies idempotency, independently releases a bank workbook, checks download and denies another assigned bank user. It leaves a Halden draft for independent approval and regenerates fresh local proposal workbooks. The fixture uses authentic sessions under separate synthetic roles sharing a demo password; it is not independent real-world legal approval.

## Verification and rollback

Security tests cover atomic changes, stale revisions, duplicate IDs, invalid categories/dates, source-policy changes, formula/hidden-content rejection, formula-like literal text, leading-zero values, own-preview access, ethical walls, post-generation clearance rechecks, bank privilege exclusion, named recipients through ordinary release routes, clean-team approvals, revocation and signing freeze. Regression checks include existing reports, document review and policy behavior.

Before migration, retain an encrypted restore-verified backup. Rollback stops owned components and retains the additive schema, original uploads, receipts, workbook versions, approvals and audit history. A downgrade is blocked once tracker records exist. External WORM storage, large-scale import queues, arbitrary workbook mapping, `.xls`/CSV import and unsourced finding creation are outside this bounded local workflow.


## Verification recorded 21 November 2026

- Full regression run: 195 passed, 1 skipped. Final focused tracker run: 10 passed, including the unchanged-row guard and post-render authorization recheck.
- Isolated PostgreSQL tracker/report/lifecycle run: 15 passed.
- TypeScript/Vite built successfully through the normal launcher. Migration 0023 applied and live Alembic metadata parity check passed.
- Live HTTPS walkthrough passed XLSX staging, atomic version update, idempotent retry, independently approved bank export, recipient download and denial to another assigned bank user. A Halden draft remains unreleased for independent approval.
- Fresh local examples were verified after the final restart: one valid proposal; validation workbook has one valid row and four invalid rows. These final previews were not applied.
- Four workbook sheets were rendered and visually inspected: Records, Guide, Tracker and Package, including the actual retained bank workbook. Leading-zero text, numeric revision and typed date checks passed.
- Portal login, tracker navigation, workflow steps and controls were observed. Browser file-picker upload verification stalled in the browser transport, and the recovery read also timed out. Full browser upload acceptance remains unverified; no extra proposals were applied during that check.
- Main matter unchanged: 10 source versions, 20 source findings, 7 audience packages, zero imported Wave 2 documents.
- Pre-migration encrypted restore verification: 57 tables / 6,561 rows. Final retained backup verification: 61 tables / 10,012 rows, with matching schema and row digests in an isolated restored database. Runtime files are not part of the database restore test.
- Five owned components remain running; readiness passed. pgAdmin and owned psql were reopened. Existing accounts/passwords and prior Action Center decisions remain intact. No paid AI call was made.
