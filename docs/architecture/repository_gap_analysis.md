# Consolidated prompt repository: implementation gap analysis

**23 November 2026 — Gate 0, audit only.** Application: `C:\Freshfields-Takehome\Freshfields_Codex_Handoff`. New requirements: `C:\Freshfields-Takehome\Prompts-repository`. This report changes no application source, database schema, accounts, approvals, provider configuration or authorization policy. No paid AI calls or deployment were performed. A frontend verification build regenerated local build artifacts.

## Outcome and authority

Adopt the consolidated repository's Gate 0–5 execution order. Preserve the working application and extend it incrementally. Do not execute archived prompts or replace the application with the proposed workbook schema. The next authorized planning unit is `migrations/database-schema-evolution/01_MIGRATIONS_AND_BACKFILL.md`, whose precondition is acceptance of this gap analysis. The earlier `docs/52` proposal to proceed directly to LangGraph is now deferred behind identity/workflow, disclosure and retrieval foundations. The implemented checklist foundation in `docs/53` remains intact.

The new first prompt explicitly requires: **“Produce this report ONLY in this stage. Do NOT silently begin schema migrations or deploy.”** This is the reason implementation stops at the audit boundary. No destructive or security-sensitive change is being requested implicitly by this report.

The original assessment remains authoritative. It says documents arrive **in waves over six weeks**, not exactly six waves as stated in the new decisions summary. Keep wave count configurable. Real first-wave operations must reuse approved firm tooling/M365; this personal synthetic prototype does not satisfy a firm's 4–6 week external-login security review. Financial analytics, comparison panes and agent orchestration are expanded candidate-demo requirements, not reasons to postpone the assessment deliverables.

## Evidence reviewed

- Active root instructions, implementation plan, open decisions, manifest, approved requirements, 13 feature prompts, three migration/regression prompts and workbook guidance. Archive content remains historical.
- Original assessment DOCX; checklist baseline and existing checklist implementation; schema workbook's 16 sheets, 76 entities, 809 field definitions, mapping/index/FK/security/format/backlog sheets; structural headers/formulas of the tracker. No workbook was edited or recalculated.
- Current models, migrations through `0025`, services/policy entrypoints, APIs, tests, React components and dependency manifests. Static API inventory contains 142 decorated API operations; runtime docs may additionally include main-app routes. This is a source inventory, not a claim to have exercised every route.
- **Live PostgreSQL 18.6 metadata in a read-only transaction:** 64 tables including `alembic_version` (63 application tables), seven SQL views, Alembic head `0025`. Columns, constraints, indexes, FKs and view definitions were captured without reading account/document/business rows or printing database credentials.
- Verification artifacts: full backend suite and frontend production build; results recorded below when complete. No new UI capability was implemented or visually validated during this audit.

Manifest: **27 of 28 listed files exist at their declared locations and match SHA-256**. Only `archive/previous-prompts/README.md` is absent; it is non-authoritative historical documentation. Both canonical baseline XLSX files are present. The root and baseline schema workbook copies agree. The schema workbook SHA-256 is `c70ac62eb194df09afe2f0b6de0c1f30d4e1aa7367c64baa7aa7c55a638e055e`. Do not invent the absent archive README or request older ZIPs.

Detailed deliverables:

- [Actual versus proposed schema](actual_vs_proposed_schema.md): 76-entity reconciliation and interpretation.
- [Field-by-field CSV](workbook_field_mapping.csv): all **809** rows, actual locations/types where a defensible correspondence exists, caveats, proposed type/nullability/key/origin/sensitivity and gate. **261 PARTIAL / 548 MISSING** under conservative physical-contract matching. These are schema correspondence counts, not application completion percentages. Current VARCHAR UUIDs and epoch timestamps differ from proposed UUID/timestamptz, so a working field can still be PARTIAL.
- [Tracker reconciliation](tracker_field_reconciliation.md): all **30 Review Log + 14 Issues List** headers verified against actual row 2. No tracker business rows are copied into the report.
- [Evidence inventory](audit_evidence.json): structural schema, dependency, route and manifest snapshots. Local test/build transcripts remain in `.runtime/prompt-audit/`.

## Capability matrix

EXISTING means a working local foundation is implemented; PARTIAL means materially narrower than the new prompt. MISSING means no implemented component for that requirement. CONFLICT identifies an incompatible assumption requiring a deliberate decision.

| Area | Status | Actual implementation and required extension |
|---|---|---|
| Identity, sessions, client/matter validation | EXISTING | Real accounts/session cookies, UPN/profile, combined leading-zero client/matter identifiers, scoped service tokens. Preserve contracts and identities. |
| Person/client/matter walls and centralized ABAC | EXISTING | `services/policy.py`, wall controls/checker and SQL views enforce matters, roles, lineage, privilege, clean-team membership, lifecycle and audiences on implemented routes. Future services must call these checks. |
| Logical document identity / VDR import | PARTIAL | `source_versions.logical_key`, matter, version, previous ID, hashes and folder-selection intake exist. No dedicated logical-document row, normalized vendor inventory, mapping profile or persistent batch/row reconciliation. Filename is not identity. |
| Immutable documents and original evidence | EXISTING | SQL-retained binary/text units, checksums, immutable versions, source-linked candidates and reviewed revisions. This is bounded local storage, not a production object-storage pipeline. |
| Custodians and parties | PARTIAL | Counterparty text exists on document-review versions. No normalized source custodian registry or many-to-many custody; custodian is not assignee or contracting party. |
| Parallel stage assignments / clocks / SLAs | MISSING | Matter membership, finding owner and impact-task assignee do not implement simultaneous document review/QC/finance assignments. No truthful active/idle session model or business calendar. |
| Checklists and request coverage | PARTIAL | `0025` immutable version definitions and decision/coverage events, independent SME publication/N/A decisions, restricted evidence unions and signing manifest integration work. Item/link data are JSON, not all proposed normalized tables. |
| Unified workflow events | PARTIAL | Specialized append-only decisions, task notifications and scoped audit exist. A generic workflow event/outbox contract for assignments, coverage, redaction and finance is missing. |
| Whole-document classification | EXISTING | Type, ordinary/privileged/clean-team restriction, confirmation and separate relaxation workflow. Governing law is distinct from language. |
| Multi-label content and segment ABAC | MISSING | No independent financial/legal/mixed dimension registry or segment assertions. Extracted units and OCR word coordinates are evidence, not independently authorized segments. |
| Real redaction and sanitizer validation | MISSING | A sanitized flag or released report does not prove removal from a source binary. No redaction projects/marks, recovery tests, derivative manifest or validation pipeline. |
| Audience release / named Halden clean team | EXISTING | Independently approved findings/reports/trackers, bank privilege exclusion and named approved Halden source grants exist. Extend exact-version entitlements without broadening existing gates. |
| Bank underlying financial sources | CONFLICT | New design permits specifically approved financial sources; present external raw-source rule generally denies bank access. Add a separate future entitlement path only after source-versus-derivative policy is settled; keep default deny now. |
| Legal review / reports / collaboration | EXISTING | Candidate review, confirm/correct/reject, reviewed-finding reports, editable sections, Word/PDF and Excel annexes, version approval, section discussions, client uploads and report comparisons exist. These are not generic financial-fact or raw-source redaction workflows. |
| Permission-aware Q&A | PARTIAL | `services/questions.py` bilingual keyword/excerpt baseline plus optional AI synthesis; current eligible-source cap 200 and eight selected passages. External corpus uses approved release content. Not BM25/vector/structured/hybrid retrieval. |
| Retrieval router / embedding corpora | MISSING | No indexed audience-specific corpus registry, BM25 index, pgvector store, hybrid routing/explanation, reranking or reindex/revocation outbox. |
| Financial facts / deterministic analysis | MISSING | Existing exposure/materiality text and Excel display are not Decimal fact extraction, period/entity/currency provenance, formula handling or reconciliation. |
| Bank analytics toggle / hotness / cluster wheel | MISSING | Existing scoped matter counts and risk registers are foundations only. No finance toggle, independent scoring, SLA signals, materiality policy, saved clusters or sunburst drilldown. |
| Reader popup and exact evidence | EXISTING | `frontend/src/DocumentReader.tsx`, `backend/kestrel/adapters/document_reader.py`, `GET /api/v1/workflow/documents/{source_id}/reader`. Keep these and current URLs; original PDF inline, bounded Word/Excel/text presentation and evidence spans work. |
| Comparison / full format anchors | PARTIAL | Report-version comparison exists; no 2–4 independently authorized document-reader panes. No complete derivative-specific typed citation registry or broad email/container/presentation reader. |
| React DataTables | MISSING | React 18/TypeScript/Vite UI uses existing tables; no `datatables.net-react` dependency or reusable server-paged wrapper. Preserve compact UI, charts and popup reader. |
| Live AI and jobs | EXISTING | Direct OpenAI adapter, durable PostgreSQL jobs/leases, OCR jobs, budget reservations, server-protected key configuration and approval gates exist. No paid call made for this audit. |
| LangChain / LangGraph specialists | MISSING | Neither installed nor declared. No graph checkpoints, shared specialist tools or coordinator/retrieval/finance/legal/reviewer/drafter/verifier graph. Ordinary worker jobs are not LangGraph agents. |
| Playbook governance / change impact | EXISTING | Immutable governance versions, independent SME approval, fixed impact snapshots, persistent inbox, explicit rerun approval and retained history. |
| Agent/model/prompt configuration governance | PARTIAL | Current playbook and processing settings do not constitute an approved general agent/graph/prompt registry. Add versioned contracts; do not reuse “admin settings” as legal publication approval. |
| Audit, freeze, closing and retention | PARTIAL | Scoped audits/exports, signing manifests, lifecycle/hold/deletion separation, source archives and backup tooling exist. Long-term externally immutable storage and complete new-domain incident/revocation integration still need work. |
| Production scale/readiness | CONFLICT | Local bounded demo is not verified for 12,000 docs/400,000 pages or real bank access. Keep the production architecture/phasing assessment separate from prototype feature completion. |

## Reader and intake: honest format coverage

| Format | Current behavior | Required future work |
|---|---|---|
| Text PDF | Extraction and native inline PDF; page/unit offsets and exact passage evidence | Verified geometric highlighting, segment-specific views, sanitizer and derivative anchors |
| Scanned PDF | Local English/German OCR adapter with retained word coordinates; human verification required | Runtime model integrity/availability must hold; maximum 10 OCR pages per source, no large-scale throughput assurance |
| DOCX | Bounded paragraph/table extraction and safe reader presentation | Stable conversion/render anchor map; not native Word fidelity |
| XLSX | Bounded sheet/row/cell presentation, no formula evaluation | Current intake/reader reject formulas/macros; preserve raw formula/cached-value provenance in a separate safe future pipeline |
| TXT / CSV | UTF-8 text/line units | Typed CSV column/range anchors and virtualized larger views |
| DOC / XLS / XLSM / RTF / HTML | Unsupported by current document intake | Sandbox conversion, metadata/active content policy, provenance and format tests before enabling |
| EML / MSG / PST / OST / MBOX | Unsupported | Safe message/container extraction, nested attachment lineage and independent entitlements |
| PPT/PPTX, TIFF/JPEG/PNG, ZIP/7z, DAT/OPT/LFP | Unsupported by general intake | Dedicated bounded adapters, hidden notes/layers and archives/load-file validation; OCR PDF internals do not imply generic image support |

Current intake limits include 3 MiB per file, PDF extraction up to 50 pages, 150,000 extracted characters, Excel up to 1,000 rows/50 columns/5,000 processed cells; folder UI up to 100 files/50 MiB. These are deliberate local bounds, not scalability targets. Macro/formula rejection must remain until a validated replacement path exists. Native sanitized XLSX is optional: release flattened PDF/CSV if residual content cannot be proved absent. Black rectangles over PDF text do not constitute redaction.

## Proposed migrations and code changes — design only

Names below reserve an implementation sequence after current `0025`; no migration files were created. Reconfirm the live head before assigning revision IDs. Keep existing text IDs/FKs and epoch contracts during compatibility rollout. New numeric finance values use Decimal/NUMERIC; new timestamps may use timestamptz behind explicit serialization adapters. Do not mass-cast the current schema.

| Proposed revision / file | Additive schema and key invariants | Existing files to extend |
|---|---|---|
| `0026_document_identity_vdr.py` | `documents`, `document_sources`, `vdr_mapping_profiles`, `vdr_import_batches`; nullable `source_versions.document_id` compatibility FK. Unique `(matter_id, logical_key)`; source system/external ID scoped by matter; stable version association. Batch idempotency includes matter/vendor/key and source hash. Keep renamed-file and duplicate-binary cases distinct. | `models.py`, `services/workflow.py`, `api/workflow.py`, `FolderImport.tsx`; add bounded vendor import schemas/services/repository and dry-run receipt. |
| `0027_custodians_review_tasks.py` | `record_custodians`, `document_custodians`, `document_parties`, `document_tags`, `review_tasks`, `review_task_events`; composite scope consistency and append-only task history. Parallel stage tasks explicitly permitted; idempotency prevents accidental duplicates. | `services/diligence.py`, `DocumentReviewPanel.tsx`, `MatterWorkspace.tsx`; new assignment/custodian APIs. |
| `0028_review_clocks_sla.py` | `review_sessions`, `sla_calendars`, `review_sla_policies`; versioned calendars, server UTC events, no negative/overlapping active intervals per task/session, explicit pause/idle events. | Reader activity integration, scoped review APIs, worker escalation/notifications; never infer activity solely from open tab. |
| `0029_checklist_projection_workflow_events.py` | Normalized item/link/coverage projections keyed to exact existing checklist version/item/revision; `review_clause_answers`, seller-Q&A/issue extensions and append-only workflow outbox. Preserve original definitions and coverage decisions. | `services/checklists.py`, `repositories/checklists.py`, `api/checklists.py`, `ChecklistWorkspace.tsx`, `services/lifecycle.py`, audit. |
| `0030_segments_attribute_assertions.py` | `document_segments`, `security_attributes`, `document_attribute_assertions`, `attribute_downgrade_approvals`; assertions bind immutable version/segment, source and policy revision. Restrictive provisional labels join whole-source restrictions; missing attributes deny. | `services/policy.py`, `services/documents.py`, classification workflow and extraction; add cross-entrypoint differential policy tests. |
| `0031_redaction_derivative_release.py` | `redaction_projects`, `redaction_marks`, `release_artifacts`, `release_artifact_versions`, `sanitization_validation_runs`, typed lineage, exact-version `release_grants`, `disclosure_incidents`. Preserve existing release packages/approvals, add links instead of renaming them. Approvals bind source/policy/output hashes and successful validator version. | `services/workflow.py`, `services/reports.py`, `services/policy.py`, release/audit/lifecycle APIs; new sandboxed sanitization adapter. |
| `0032_authorized_search_corpora.py` | `indexed_corpus_records`, `search_queries`, `search_result_evidence`, revisioned invalidation/outbox; separate audience-released corpus. Engine choice and vector extension require dependency review first. | `services/questions.py`, `services/qa_ai.py`, `api/questions.py`, `QuestionsWorkspace.tsx`; add retriever contracts and route explanations. |
| `0033_financial_fact_registry.py` | Financial entities/periods/metrics/instruments/facts/statement lines. Decimal precision, currency/unit/period/entity, raw value, restatement and cell evidence. No automatic formula execution or silent authoritative fact choice. | New financial domain/services/APIs; reuse extraction, policy, citations and review gates. |
| `0034_financial_reconciliation_bank_metrics.py` | Financial reconciliations/analysis runs/materiality policies; approved feature setting only. Deterministic arithmetic, authorized input-set hash, approved financial source entitlement if separately settled. | New finance workspace; existing administration, governance inbox, audit and release services. |
| `0035_reader_citation_comparison.py` | Typed `document_citations`, optional reader state/comparison sets; each pane resource has independent exact-version authorization. Never redirect derivative citations to original source. | Extend `DocumentReader.tsx`, `adapters/document_reader.py`, existing reader route; preserve callers and existing ReaderTarget. |
| `0036_dashboard_scopes_signals.py` | `document_hot_signals`, saved views, policy-revision-scoped aggregates; distinct legal/financial/delay signals, unknown values retained as unknown. | `MatterWorkspace.tsx`, new cluster component; add reusable DataTables wrapper with server filter/sort/page and per-row bulk authorization. |
| `0037_agent_config_graph_runs.py` | Typed approved agent/prompt/graph versions, execution provenance and checkpoint references; adapt rather than replace `analysis_jobs`, `ai_operations`, reservations and impact tasks. Full graph budget shared by all agents. | `services/jobs.py`, OpenAI adapter, new graph/tool adapters, `PolicyWorkspace.tsx`, `ActionCenter.tsx`; provider configuration remains private. |
| `0038_cross_domain_audit_lifecycle.py` | Integrate all new resources with signing manifest, archive/restore, release revocation/incident tasks and audit integrity. Reuse current lifecycle/decision tables; no automatic retention deletion. | `services/lifecycle.py`, `services/auditing.py`, backups and resources guides. Final cross-domain regression gate. |

These are bounded migration batches, not a commitment to create every proposed workbook table literally. Existing specialized services remain authoritative until dual-read parity is demonstrated. Exact FK targets, enum values, financial precision, graph schema and external search engine remain design decisions for the accepted migration plan. The workbook references graph/prompt versions, structured contract terms and disclosure schedules without fully defining every registry; it cannot be executed mechanically.

## Preservation, backfill and rollback contract

1. Before implementation, create and restore-verify a local backup into an isolated database. Record counts for every retained table, FK orphans, exact source byte/text hashes, previous-version chains, checklist/finding/report/release version hashes, current accounts/role grants and policy decisions. Do not copy sensitive values into build logs.
2. Expand schema only. Keep old API contracts, readers, IDs, sessions and URLs working. Build deterministic mapping receipts from `(matter, logical_key, version ID)` to new logical IDs. External source keys are scoped by matter/vendor; identical filenames and hashes across matters never merge. Multiple documents sharing bytes are not automatically the same legal instrument.
3. Backfill projections with idempotency keys and content hashes. Run twice on a throwaway copy; second run changes no logical records, assignments, financial facts, approval state or paid-processing counters. Never synthesize a historical review timestamp, custodian or SLA from current ownership.
4. Validate dual reads before switching a feature flag. A retained JSON restriction union remains authoritative until equivalent normalized access checks are proved; a projection must not relax a prior classification. JSONB vendor extras may not become a second policy authority.
5. Rollback means disable new features and route back to preserved readers/projections. Do not downgrade away new human decisions after use; preserve them and perform a forward repair. Backup restore is a last-resort isolated recovery, not an excuse to erase subsequent legal/audit history. No old columns/tables are dropped without separate approval.
6. Extend immutable guards, signing snapshots, legal holds, archive manifests, export scope and restore verification as each domain is introduced. Indexes/caches are rebuildable derivatives; authoritative records and audit are not.

## Threat analysis and required tests

| Threat | Required control / proof |
|---|---|
| Cross-matter identity collision / imported authority | Scoped source identifiers; no importer may create role grants, approve findings or publish. Repeated wave and rename fixtures; leading zeros preserved. |
| Policy drift across reader, agents, search and SQL | One canonical PDP and explicit action/resource/version checks at retrieval, evidence navigation, export and tool invocation. Differential tests retain walls even for admin and feature-enabled bank. |
| Mixed-content declassification through a derived summary | Source-restriction union plus approved derivative manifest, independent senior/antitrust decisions and exact output hash. Root admin or AI cannot authorize a relaxation. |
| Stale approvals / cached ACLs / search contamination | Bind revisions and source snapshots, fail closed on stale/unavailable policy, transactional revocation/outbox, recheck before output. Separate released corpus; never retrieve parent original as fallback. |
| Recoverable redactions | Re-extract PDF text and inspect metadata/attachments; test black-overlay failure. Inspect Excel hidden sheets/names/formulas/caches/comments/external links/objects/macros; quarantine or flatten if proof fails. |
| Unauthorized titles/counts/aggregates | Filter before grouping, SQL totals, facets, ranking, chart drilldown and exports. Compare no-access versus inaccessible-match fixtures; bank sees no internal lawyer productivity. |
| Financial numerical error | Parameterized typed SQL, Decimal and unit/currency/period/entity tests; cache/formula flags, restatement and conflict queue; no model arithmetic or arbitrary AI SQL. |
| Multi-pane or citation bypass | Reauthorize every pane/download and original/derivative anchor. Test permitted derivative alongside denied original, cross-matter pane and cell outside grant. |
| Agent privilege escalation / prompt injection | Immutable requesting identity/scope, allowlisted tools, untrusted document instructions treated as data, persisted human interrupt gates and shared run budget. Retried/resumed nodes cannot duplicate processing charges. |
| Fabricated productivity / privacy | Server-tracked explicit active/idle/pause, honest unknown/offline state; no browser-open elapsed time presented as work. Scope session data and notifications. |
| Freeze / deletion / incident history loss | New-domain signing snapshots, hold-aware client-copy deletion distinct from firm retention, archive restore test, retained prior release recipients and incident review. Cannot remotely revoke downloaded copies. |

Workbook security scenarios CT-001–CT-030 become an acceptance catalogue, not evidence they already pass. Existing tests cover established boundaries; new segment, sanitizer, financial, index, comparison and graph cases require new implementations and regression tests at each gate. Include fail-closed partial bulk operations, concurrent approval/revocation, duplicate imports, tampered hashes and expired scope. No acceptance check may be “solved” with a test identity header or role-switch control.

## Dependencies and open decisions

Installed backend metadata: FastAPI 0.165.0, Pydantic 2.14.4, SQLAlchemy 2.1.9, Alembic 1.20.1, psycopg 3.3.9, pypdf 6.21.4, python-docx 1.2.0, openpyxl 3.1.5. LangChain, LangGraph and pgvector Python packages are absent. Frontend declares React 18.3.1, TypeScript 5.6.3 and Vite 8.3.8 ranges; DataTables is absent. Broad Python dependency ranges and environment-bound OCR tooling warrant a pinned/reproducible dependency and portable deployment plan before introducing graph/conversion packages. No dependency was installed for this audit.

- **Bank source policy:** clarify whether to release originals, only sanitized derivatives, or both by explicit entitlement. Existing default source denial remains. A dashboard toggle never grants access. This is the principal security-sensitive design gate.
- **MFN:** tracker column means Most-Favored-Nation, but “MFN changes” could also refer to a model-selector discussion. A clarification was requested; no new selector is implemented on an assumption.
- **SLA:** five-day tracker default is a proposed demo starting point. Business calendar, holiday/timezone rules, idle threshold and offline treatment remain unconfirmed.
- **Retrieval engine:** ordinary PostgreSQL full-text ranking is not BM25. Choose an actual BM25 implementation/index, embedding model/store and secure indexing/revocation contract before advertising these modes. No internet/provider/extension installation is implied.
- **AI budget:** retain confirmed **$2 per run / $10 per month**. Multi-agent execution needs a shared graph-run reservation and defined treatment of embeddings/retries; agents cannot each spend $2. Ollama/Vertex are not assumed available.
- **Governance:** retain current independent legal/antitrust/security/conflicts approvals and synthetic users. Do not promote an admin into an SME or expand the roster automatically.
- **Schema conflicts:** preserve `clients` versus tenant organizations; document IDs versus version IDs; specialized immutable checklist/impact events versus generalized proposed registries. Content topic labels do not replace restrictions. No mass conversion to native UUID/JSONB/timestamptz or rewriting old approvals.

## Ordering and effort

Indicative engineering estimates, not a promised delivery date: Gate 0 migration contracts/restore tests **2–4 days**; Gate 1 identity/import and workflow foundations **5–9 days**; Gate 2 segment policy plus validated bounded PDF/CSV derivatives **7–12 days**; Gate 3 router/financial facts and reconciliation **7–12 days**; Gate 4 reader comparison/cluster/DataTables **4–8 days**; Gate 5 graph/governance and final integration **6–10 days**. Unsupported legacy/email/archive formats and validated native Excel sanitization require separate investigation. Real security review and 400,000-page performance validation are additional work.

Recommended next reviewable increment after audit acceptance: an additive logical-document/VDR mapping migration and dry-run importer on a restored database copy. Demonstrate repeated import, renamed file, two custodians and parallel task identity while preserving existing evidence URLs, compound matter IDs, source hashes and all current approvals. Introduce segment/release foundations before new bank source access or agent teams. Keep assessment partner note, architecture, rollout conflicts and AI disclosure progressing alongside the optional application.

## Verification

Frontend: `npm run build` **passed**, TypeScript/Vite build, 49 modules. Backend: full `python -m pytest -q` **220 passed, 1 skipped, 1 warning in 218.40 seconds**. The warning is the installed Starlette/httpx test-client deprecation; no dependency change was made. PostgreSQL inspection was read-only and returned head `0025`; no migration was run. No new browser visual assessment, public security review, paid AI verification, scale benchmark or new-feature acceptance test was performed.
