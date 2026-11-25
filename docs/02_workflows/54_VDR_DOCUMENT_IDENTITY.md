# VDR identity and CSV mapping increment

23 November 2026. Implements the first bounded Gate 1 increment after acceptance of the consolidated repository audit. PostgreSQL Alembic head: `0026`. The broader 76-entity proposal is not declared complete.

## What is working

- Immutable `documents` identities scoped by `(matter_id, logical_key)` and append-only `document_version_links`. Current source-version IDs, bytes, text, URLs, approval records and previous-version chains were not rewritten. UUID strings and UTC epoch compatibility are retained.
- Six additive tables: `documents`, `document_version_links`, `vdr_mapping_profiles`, `vdr_import_batches`, `vdr_import_rows`, `document_sources`. No extra database or separate API service.
- Immutable versioned vendor column profiles, optimistic previous-version checks and raw CSV/batch/row hashes. Every Review Log column has an optional traced mapping; source ID and filename are additionally supported. Unmapped vendor extras remain original non-security data.
- Matter/vendor/source-ID/index/folder provenance is retained. A missing explicit Doc ID generates a deterministic key from the scoped source identity. Filenames and binary hashes alone do not merge documents. An explicit same Doc ID is a deliberate logical-document match; folder import asks the lawyer to review a proposed version replacement.
- Uploader-only staged batch retrieval with current firm/legal/matter access and policy rechecks against referenced existing versions. Root Admin has no legal/source override; external import routes deny access. Imported reviewer names, risk answers, QC, comments and dates never become approvals or permissions.
- CSV errors retain their original rows as quarantined metadata. Repeated idempotency keys cannot change content. Replaying a staged file returns the retained version; repeated batches with the same current bytes add provenance without duplicating versions or analysis jobs. Changed bytes require the existing explicit previous-version process.
- New versions conservatively retain prior privileged/clean-team/legal-advice and AI-processing restrictions pending the existing authorized classification workflow. They do not automatically relax access.
- Documents now includes optional vendor CSV mapping/preview followed by folder import. Existing folder-only import and evidence popup remain available. Mapping and staged metadata guide is in Resources. New Swagger group: `/docs/vdr-imports` (five operations across four paths).
- New metadata enters future signing manifests (`kestrel-signing-manifest-3`), with the existing freeze write barrier and immutable DB triggers. Historical signing payloads remain unchanged. Populated `0026` downgrade refuses to discard retained identity/import records; rollback uses the preserved old paths or a forward repair.
- Start/Stop BAT descriptions updated; existing launcher automatically migrates to head and uses the same five service consoles. No duplicate server is started for the VDR Swagger group.

## Try it locally

1. Run `START_KESTREL.bat`. In the Firm portal, sign in with an assigned lawyer, select matter `012345-789012`, and open **Documents**.
2. In **VDR metadata import**, choose `synthetic/vdr-import-demo/wave1/vendor-metadata.csv`. Select **Wave 1**, inspect the suggested columns, confirm synthetic material, then **Save mapping & check rows**.
3. Choose `synthetic/vdr-import-demo/wave1/documents` in folder import. Review the file, confirm synthetic material and import. Confirm classification through the existing workflow before analysis/legal review.
4. Repeat with the Wave 2 CSV and `wave2/documents`, selecting **Wave 2**. The renamed file keeps Doc ID `VDR-DEMO-SUPPLY-001`; review its previous-version match. Old bytes/evidence remain retained.
5. Use **View evidence** to open the same authenticated reader. An SME must separately authorize analysis; independent audience release remains required. No AI work or approval is triggered by import.

The browser verification staged one synthetic Wave 1 metadata row only. The example binaries and Wave 2 remain local for you to process. After a refresh, reselect the CSV and mapping; this increment does not yet provide a batch-history browser. Original retained batches remain in PostgreSQL.

## Verification actually performed

- Full backend suite after retention-test compatibility updates: **226 passed, 1 skipped, 1 Starlette/httpx deprecation warning**, 335.62 seconds. Initial full run exposed two assertions expecting older downgrade messages; the earlier `0026` refusal was correct. Tests now accept that earlier retention barrier and targeted regression rechecks passed (10 tests).
- Identity/VDR + migration checks: **9 passed**. PostgreSQL isolated-schema identity/VDR tests: **6 passed**.
- Frontend TypeScript/Vite production build passed; the mapping preview was exercised through normal browser sign-in, CSV file selection and Save mapping & check rows. Screenshot: `outputs/vdr-import-preview.jpg`. No role/identity header or browser cookie injection was used.
- Encrypted database backup restored into an isolated database and verified: 64 pre-migration tables / 14,170 rows, data/schema/constraints matched. No restore over the active database.
- Migration rehearsed on that restored copy, upgraded twice and backfill replayed twice. **63 existing application-table digests unchanged; 16 sources -> 15 logical documents / 16 links; zero projection orphans.** Applied live with identical preservation results while owned services were stopped. Existing tables and seven SQL views remain.
- Rehearsal/application manifests and test transcripts: `.runtime/prompt-audit/vdr-*`. Verification scripts expose counts/digests, not source contents or credentials. No provider/approval/wall/role configuration change or paid API call.

## Limits and next build

CSV metadata staging is limited to 100 rows / 256 KiB; files still use existing extraction and folder limits. No formula-bearing XLSX tracker import, real VDR connector, source binary redaction, BM25/vector store, agent graph, task-assignment import or financial-fact extraction is claimed. All 30 tracker columns are retained/mapped, but governed reviewer/issue/checklist/QC fields need their respective future normalized services before they can be applied. Rich title/party/date/workstream metadata is retained on exact immutable import rows, not yet a normalized editable registry.

Next: normalized custodians and parties, parallel stage assignments and immutable assignment events, then truthful clocks/SLA calendars and checklist projections. Segment ABAC/redaction and retrieval/finance follow. **React DataTables remains explicitly planned at Gate 4**, using server-side authorization/pagination/bulk controls; the tables in this increment are still the existing React table style. Preserve the reader and charts when that replacement is introduced.
