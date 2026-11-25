# Internal financial context and deterministic staging

[IMPLEMENTED / LOCAL DEMO] 24 November 2026. Migration `0038_financial_context.py` adds four append-only sidecar tables. It does not alter existing financial facts, source bytes, source extraction JSON, approval history or released output. This increment supplies an explicit human-reviewed context workflow and a bounded deterministic candidate stage; it does not complete the broad financial extraction requirement or establish production readiness.

## Context workflow

Firm legal users can select an existing financial fact and propose an immutable context revision. The additional dimensions are instrument identifiers, precision/accuracy declarations, physical numeric sign plus declared sign convention, fiscal calendar, reporting-period kind and restatement status. Every missing dimension defaults to `UNKNOWN`. A known dimension must include exact retained source evidence containing its literal identifiers/labels. The physical sign must agree with the original immutable numeric token. No checksum, instrument registry, taxonomy, FX, calendar or restatement inference is performed.

An independent source-cleared SME, distinct from both the context author and the underlying fact author, must explicitly review every dimension, UNKNOWN field and evidence range before confirming or rejecting the latest exact hash. The underlying fact must already be independently verified and active. Proposing another revision never overwrites an earlier version. Request keys, expected head hashes, revision hashes and immutable database triggers retain concurrency and idempotency boundaries. Context revocation is append-only and returns a body-free receipt; an eligible author or scoped SME can tighten future use after signing without changing signed records.

Confidence defaults to UNKNOWN. An optional decimal-string reviewer assessment is explicitly labelled an uncalibrated opinion. It is not extractor accuracy, measured confidence or a model score. Extractor confidence remains UNKNOWN. Identifier schemes and values are source declarations, including a declared ISIN/LEI; they are not externally validated identities.

`POST /api/v1/financial-context/compare` is a **separate** internal comparison. It requires both exact current context hashes and rechecks the confirmer's active account, SME role and current source/retained clearance. Missing confirmation or dimensions produce UNKNOWN with no arithmetic. Different existing fact dimensions or new declarations produce INCOMPATIBLE with no arithmetic. A ticker without a venue or an OTHER instrument scheme remains unresolved. Only compatible independently confirmed contexts permit deterministic Decimal difference and percentage against the absolute right-hand amount. A zero baseline produces an unknown percentage. No reconciliation preference, old fact or published output is rewritten.

All reads require the current source PDP **and** the retained restrictions of the original fact, context, evidence and decisions. These can be different historic clean-team partitions; each restriction is ANDed. Original access is never inherited from a sanitized derivative. Walls, validated matter assignment, active roles/accounts, source handling, disclosure state and confirmer clearance are rechecked. Root administration has no source override. The API refreshes identity and source authorization after preparation, then re-resolves the exact context/candidate result; stale confirmation, revocation or evidence cannot emit earlier arithmetic or content. Access and denial audit records retain protected reference resolution without recording passages in errors.

Contexts and candidates are internal-only. **No context fields, source identifiers, assessment values or candidate data are added to released bank facts, bank queries, bank table exports, financial Q&A or the existing comparison JSON.** Bank and client actors cannot call the context/staging API, even when they can read a separately released financial fact. A future context publication workflow would require its own explicit release design and independent decisions; it is not supplied here.

## Explicit unapproved extraction stage

Only an explicit user command stages candidates against a confirmed, text-ready, current and mutable original source. There are no startup scans, automatic re-extraction, model calls or source ingestion. A scan is limited to 50 candidates, each with at most 8,000 characters of exact evidence; a retained source has a local 100-candidate read bound. Exceeding a selected limit fails without committing a partial stage. Duplicate keys bind source version, exact source snapshot, sheet/row or XBRL fact anchor, extractor version and mode. Existing candidates and source evidence remain immutable.

Request fingerprints are retained on newly created candidates. Empty scans and scans that only reuse existing candidates do not create a separate durable scan-command receipt; the extraction anchors still prevent duplicate candidate/fact creation. A standalone scan-history/receipt workflow is not implemented.

The workbook/CSV extractor accepts exact lowercase first-row headers, not natural-language header guessing. The core vocabulary is:

`amount`, `entity`, `metric`, `period_label`, `period_start`, `period_end`, `currency`, `scale`, `scale_label`, `accounting_basis`, `consolidation_scope`, `decimal_mark`, `numeric_notation`.

Additional declared-context columns are:

`instrument_scheme`, `instrument_id`, optional `instrument_venue`, `precision_kind`, optional `precision_value`, `precision_label`, `sign_convention`, `calendar_kind`, `calendar_label`, `period_kind`, `restatement_kind`, `restatement_label`.

The existing `period_label` also supports the reporting-period declaration. Unknown or duplicate headers make that sheet unsupported; a sheet without `amount` is not guessed. All retained sheets can contribute candidates, including hidden content, under the original whole-source restrictions. Formula cells and their caches never supply candidate values or dimensions. XML numeric cells use strict XML dot-decimal/scientific syntax; literal string/CSV numbers require explicit decimal convention and notation. Scale is only the explicitly declared supported multiplier 1, 1000 or 1000000. Amounts use the existing exact Decimal bounds; no float conversion or formula execution occurs.

XBRL/iXBRL staging reads retained numeric fact/context/unit metadata from the bounded inert parser. It preserves expanded concepts, entity identifiers, exact periods, accuracy attributes, unit measures, original sign/scale/transform and exact Decimal value. Explicit iXBRL scale/sign is applied once by the retained parser. Simple ISO4217 monetary units can populate currency; compound/non-monetary units stay unresolved. Nil remains missing, never zero. Entity identifiers are not re-labelled as instrument IDs; a twelve-month duration does not establish annual reporting or a fiscal calendar. Missing accounting basis, consolidation, period label, instrument, sign convention, calendar and restatement generally leave XBRL candidates INCOMPLETE. There is no taxonomy/network lookup or mapping from dimensions to accounting semantics.

Relational candidate fields preserve known values and explicit missing-field lists. `normalized` is present only when every required core and additional dimension is known and supported. READY_FOR_REVIEW remains **UNAPPROVED**. No candidate automatically creates a FinancialFact, verification, disclosure or release. The existing separate exact human capture workflow remains the route to independently reviewed financial facts; candidate promotion is not implemented.

## API and UI

The protected router prefix is `/api/v1/financial-context`:

| Method | Path | Result |
| --- | --- | --- |
| GET | `/facts/{fact_id}` | Permitted internal context history, exact evidence units and current status |
| POST | `/facts/{fact_id}/versions` | New immutable unapproved revision, exact previous-hash concurrency |
| POST | `/versions/{context_id}/decisions` | Confirm, reject or append-only revoke of the exact content hash |
| POST | `/compare` | Separate context-aware UNKNOWN/INCOMPATIBLE/COMPATIBLE assessment |
| GET | `/sources/{source_id}/candidates` | Source-authorized retained unapproved stage |
| POST | `/sources/{source_id}/scan` | Explicit bounded literal template or XBRL scan |

`FinancialContextPanel.tsx` mounts only for internal Financial Evidence users. It displays selected-fact context, exact evidence reader links, human declaration fields, independent confirmation controls, a separate context comparison and explicit staging commands. It polls every 15 seconds, binds results to matter/selection generations and clears protected state on 401/403/409. No raw source markup is rendered. The current form supports one instrument per revision and one evidence range per field; the strict API supports up to eight identifiers and 32 evidence ranges. Use the API for a multi-identifier edit rather than silently reducing an existing identifier set. No UI automation or visual acceptance claim is made from a successful build alone.

The signing manifest includes `financial_fact_contexts`, `financial_context_evidence`, `financial_context_decisions` and `financial_extraction_candidates`. Its authorization uses the same complete fact/source taint union. New writes are frozen; append-only context revocation remains possible. Retained populated tables block destructive downgrade. No WORM-storage claim is made.

## Verification and limits

The final integrated SQLite run passed **36/36 tests in 76.60s** across the new context suite, existing financial workflow, literal cell evidence, migrations, lifecycle and observability/audit governance. The final isolated PostgreSQL context suite passed **14/14 tests in 42.96s**. It includes PostgreSQL Alembic `command.check` against ORM metadata, populated destructive downgrade denial, exact Decimal persistence, released-bank JSON equality, source-policy changes, prepare/response wall-role-revocation races, candidate response clearance, all four signing tables and body-free post-signing revocation. The historic-fact partition fixture proves that ordinary current source access cannot erase another retained fact restriction from context reads, audit visibility or signing. All disposable PostgreSQL schemas were removed by fixture teardown; no test process remained active when backup/rehearsal control returned to the root agent.

Initial test development exposed two fixture-only PostgreSQL portability assumptions: a synthetic timestamp outside INTEGER range and string comparison of a NUMERIC value's trailing zeros. Both were corrected to a real clock value and Decimal equality. An intermediate SQLite race run also found pending read-audit autoflush holding a write lock before the deliberately concurrent authorization mutation. The API now defers autoflush during preparation/revalidation and commits permitted read audit records after checking the final response. The final race suites pass on both databases.

Migration SHA256: `d15d43eda216a23003d32e6f83840f0ceffd7b8be023fe3d8c53ad5d479131c7`. Test module SHA256: `0d0559ae74d56a1af260d4a8cfe45e5c6e3d8f853e2750fc1c75df8cd988e29d`.

The frontend TypeScript/Vite production build passed after panel integration (82 modules). Test fixtures use disposable SQLite files and PostgreSQL schemas and contain synthetic evidence only. The implementation agent performed no live migration, ingestion, approval, paid AI call, deployment or restart.

The root agent subsequently performed the controlled local backup, restore rehearsal and application of 0038. The encrypted backup contained 150 tables / 17,436 rows and passed restore/schema verification. All **149 prior application-table digests** were preserved through rehearsal/application, alongside **17 source versions / 16 logical documents / 17 version links**, with **zero orphans**; existing backfills replayed twice without changing the preserved identities. Receipts: restore rehearsal (workspace reference not included in the public snapshot) and controlled application (workspace reference not included in the public snapshot). The root agent coordinates launcher restart and visual acceptance; the successful build and data-preservation receipts do not themselves prove UI acceptance or production readiness.

Unsupported broad/ambiguous layouts, legacy XLS/PST/OST/MSG converters, scanned table recognition, full XBRL taxonomy semantics, calibrated extraction confidence, automatic candidate promotion, instrument registry resolution and context-specific external publication remain outside this implemented subset. Exact-match evidence and independent confirmation are controls, not claims of financial accuracy or complete risk coverage.
