# Governed application of legacy reviewer, QC and date proposals

24 November 2026. [PLAN ONLY — ROOT REVIEW REQUIRED] This document proposes the next bounded Gate1 increment against the three active document-metadata-workflow prompts and docs80. No application code, model, migration, fixture, live row, identity, approval or provider call was changed for this plan. Migration0039 is **not reserved** by this document.

## Recommended result and boundary

Let the original VDR uploader explicitly turn selected reviewer/QC proposals into **current coordination assignments**, with a durable source-bound import/application trail. Retain vendor dates/statuses as separately labelled historical declarations. Offer independent review of those declarations without pretending that the reviewer performed the old work.

Reuse the existing task engine, assignee eligibility, notifications, source PDP and immutable event clock. Add retained proposal/evidence/decision/application/link sidecars because the existing records cannot safely represent imported-date provenance or exact command/application identity. Do not add imported dates to task events or change their timestamps.

The first increment supports only `assigned_reviewer → review` and `qc_reviewer → qc`. It does not import a legal finding, complete coverage/QC, accept a task for someone else, grant access, infer custodianship, execute AI, change a deadline from an old date, publish a checklist, authorize reanalysis or release a document. Other existing task stages remain available through their normal explicit workflow.

## Existing contracts inspected

| Contract | Actual behavior and consequence |
| --- | --- |
| `schemas/vdr.py` / `services/vdr_imports.py` | Versioned header mappings, at most100 rows/256KiB, immutable raw and mapped JSON, row/batch/profile hashes. Fields already include assigned_reviewer, assigned_at, reviewed_at, days_open, review_status, qc_reviewer and qc_status. No identity/date truth is inferred. |
| `VdrImportBatch` / `VdrImportRow` | Original uploader identity and request fingerprint are retained. `batch_access` is uploader-only and rechecks current access to referenced versions before returning rows/counts. This private whole-CSV contract must remain intact. |
| `DocumentSource` | Exact import-row/source-version/logical-document/vendor identity linkage already exists; unique(import_row_id,source_id). A repeated metadata batch can link to an existing identical source rather than create another source. Use these links, not filename or global VDR index guesses. |
| `Account` / `repositories.identity.principal` | Stable Account.id; globally unique casefolded username used as the current UPN identity; display_name and optional unique email are separate attributes. Current account activity, legal roles, validated matter membership, person/client/matter walls and clean-team membership are rederived. There is no general legacy-person identity resolver. |
| `review_work.eligible` / `eligible_people` | Source-cleared active firm legal accounts; assigning a task grants no source access. Existing task reassignment can require retained task/event restrictions as well as the current source. Root-only and external accounts are ineligible. |
| `review_work.create_task(..., commit=False)` | Current source/matter freeze check, future optional UTC deadline, stable document attachment, actual server-time task and assign event, existing in-app notifications. This is the transaction-safe reuse point for application. |
| `ReviewTask` / `ReviewTaskEvent` | Immutable source-bound task and revisioned events. Creation/assignment/accept/start/pause/resume/complete/open times are actual server events. Only the current assignee can record their activity; creator/scoped SME controls management transitions. Imported completion cannot bypass this. |
| `review_clocks` / `task_output` | Queue age, observed activity, idle/unobserved time and SLA derive from actual events/leases and published calendars. Imported Days Open must never feed these functions or score components. |
| `TrackerImportApplication` | Applies a different XLSX register contract, with a unique whole-import application and legal/coverage assessment semantics. It has no VDR-row/source linkage or legacy-time sidecar. Reusing it would confuse different authority and retention contracts. |

All30 vendor columns remain retained; this slice consumes only the explicit reviewer/QC/date/status subset. Request-list/disclosure references, findings/risk answers, custody assertions and checklist replacement impacts stay with their existing or separately planned services.

## Proposed commands

New protected router: `/api/v1/legacy-workflow`. Every command uses the authenticated session/CSRF, never a supplied actor/role. Initial bounds: one exact import row and current source version per proposal, at most8 explicitly selected account mappings, at most32 evidence references and a bounded100-item visible queue. Narrow filters rather than truncate authoritative totals.

| Method / path | Strict input / behavior |
| --- | --- |
| GET `/rows/{row_id}/preview?source_id=...` | Uploader-only preflight: exact existing DocumentSource linkage, source and import integrity, raw selected fields, deterministic date interpretation suggestions, eligible source-cleared accounts and permitted existing tasks. No write/decision and no whole-CSV access expansion. |
| POST `/proposals` | `{row_id, source_id, expected_row_hash, expected_profile_hash, expected_source_snapshot, expected_previous_hash?, reviewer_id?, mappings, date_interpretations, history_mode, rationale, request_key}`. Server reads original values; caller cannot supply replacement raw text, timestamps or security status. Creates an immutable source-bound proposal and evidence snapshot. |
| GET `/proposals?matter_id=...` | Owner's permitted proposals and proposals naming the current actor as independent reviewer. Counts after current and retained authorization. No matter-wide private-proposal directory. |
| GET `/proposals/{id}` | Exact permitted selected-field package, source/version and hash evidence, proposed current effects, clearly separate vendor declarations, reviewer state and immutable application receipts. Does not call or weaken `get_batch` for a reviewer. |
| POST `/proposals/{id}/decisions` | `{operation: confirm_history\|reject_history\|revoke_history\|withdraw, content_hash, content_reviewed, rationale}`. Defined authority below. This never approves legal work or a report. |
| POST `/proposals/{id}/apply` | `{content_hash, expected_source_snapshot, expected_task_revisions, request_key, rationale}`. Original proposer/uploader explicitly applies the pinned current effects in one transaction; source/identity/task/decision checks run again. Returns retained receipt and only currently permitted task references. |

`mappings` is an explicit list, not an imported role list. Each item contains `field: assigned_reviewer|qc_reviewer`, exact Unicode `token_start/token_end` within that retained field, `account_id`, `match_kind: username_exact|manual_confirmation`, `mapping_rationale`, and `effect: create_current_task|link_existing_task|provenance_only`. Linking includes exact task ID/revision; creating optionally includes a newly chosen future `due_at`. Stage is derived from the field, not user-controlled vendor text. Duplicate field/token/account mappings fail validation.

Do not split comma-separated names automatically: commas can be part of a personal name. Compound/ambiguous values remain UNRESOLVED until a human selects explicit tokens/accounts or chooses provenance-only. Every selected token remains traceable; the preview warns when nonblank source text is left unmapped. An unresolved legacy identity cannot silently become a “verified” match.

### Identity matching

1. Suggest an account only for an exact normalized **username/UPN** match among currently eligible accounts. Never choose the first account by display name, substring, employee number, email alias or fuzzy similarity. Suggestions do not assign anyone.
2. A display-name/alias value requires an explicit stable-ID choice and mapping rationale. Label this an operator mapping unless the independent historical-declaration review confirms it. Email is not silently promoted to UPN.
3. Account/role/matter/wall/clean-team eligibility is checked on preview, proposal creation, independent review and apply. An earlier suggestion, task or SME title is not an entitlement. A target who becomes inactive, walled or uncleared is unavailable; do not reveal the private reason or alternate account list.
4. Create no users, roles, memberships, clean-team grants, custodian records or external recipients. A Root administrator with no legal/source authority cannot use the import bridge. Combined roles still cannot overcome a wall.

## Current assignments versus accepted history

Two explicit `history_mode` values avoid inventing historical work:

- `retain_unconfirmed`: Keep the raw original fields as vendor declarations. The uploader can create **new current tasks** through existing operational authority after explicitly acknowledging “assignments start now; imported dates/statuses are not accepted activity.” This is no more legal approval than an ordinary current TaskCreate. It does not independently confirm the imported identity or date claim.
- `request_independent_confirmation`: The selected history/identity/date interpretation is proposed to a named source-cleared Legal SME. Applying that confirmed-history package requires the exact current independent decision. Until confirmation, an uploader who wants current assignments only must create a distinct immutable proposal in retain_unconfirmed mode rather than silently dropping the review requirement.

The named reviewer must be an active eligible Legal SME, distinct from the import uploader/proposal author and from a mapped person whose own historical review/QC activity is being asserted. Explicit review covers the original selected fields, mapping choices, date precision/ambiguities, evidence/source hashes and the proposed current effects. It confirms the **provenance declaration**, not that the SME performed or legally approved a historical review. No participant can approve for another person's current accept/start/complete actions.

`confirm_history`/`reject_history` apply only to the exact latest unapplied proposal. Current source/evidence and reviewer authority are rechecked at application/use. `withdraw` is author containment before application; `revoke_history` withdraws reliance on a confirmed declaration. Tightening withdrawal/revocation can append after signing, with current scoped authority and a minimal receipt; no stale body is returned. Revoking a historical declaration does not erase an actual assignment event or automatically cancel/reassign a current task. Any corrective current task action uses its existing independently authorized revisioned transition.

## Original date/status provenance

Persist the raw vendor string, original header/profile/row/hash, declared format, parser version, precision, explicit timezone/offset if present, normalized declaration if unambiguous, and flags/rationale. Store the real import/proposal/decision/application event times separately.

| Input | Permitted interpretation | Never do |
| --- | --- | --- |
| `Date Assigned` | Retain literal raw value; optional explicit parsed date-only or offset timestamp declaration. Current task assigned_at is application server time. | Backdate ReviewTask.created_at, assign event, notification or queue age. |
| `Date Reviewed` | Vendor-claimed review date with reviewed precision/interpretation, or UNRESOLVED. | Create complete/accept/start/open events, attorney FindingReview, whole-source complete coverage or a reviewer signature. |
| `Days Open` | Raw vendor number/text; optional exact decimal-string declaration, labelled “vendor-claimed days,” never merged with observed metrics. | Back-compute assignment time, measured activity, business days, SLA breach or hotness. |
| `Review Status` / `QC Status` | Exact legacy status text plus optional independently reviewed explanatory interpretation. | Translate “Reviewed/Complete/Approved” into current task completion, QC approval, legal finding review or external release. |
| Missing / ambiguous / formula-looking input | Retain literal evidence and UNRESOLVED flag. Allow current assignment only as a separate present-time choice. | Execute a CSV formula, assume a locale/timezone, silently fill null with midnight/now, or fabricate a historical event. |

Initial parser allowlist: ISO date; ISO timestamp with explicit Z/offset; explicitly chosen DMY/MDY date format; UNRESOLVED. No arbitrary strptime expressions, free-form date model or network lookup. A date-only value has no invented UTC instant. A timezone-less timestamp stays UNRESOLVED in this first increment, even if a vendor names a zone: do not silently pick a DST fold or normalize a nonexistent time. A future zone-aware parser would require its own pinned interpretation contract/tests. Preserve contradictory/future/missing values as flagged declarations, not claimed activity. A deadline is a newly selected future UTC operational value, separate from these inputs and subject to existing validation.

## Recommended additive models

Five small retained tables keep this bridge out of task timestamps and source/raw-row history. Names are a proposal for root review; none are implemented/reserved here. All business records carry SourceWorkScope or equivalent explicit evidence unions, immutable hashes and UTC server occurrence times.

| Model / proposed table | Main fields and constraints |
| --- | --- |
| `LegacyWorkflowProposal` / `legacy_workflow_proposals` | Target matter/source, import_row_id FK, batch/profile/row/mapped-subset hashes, expected source snapshot, previous proposal/hash, author and optional named reviewer, typed mappings and date-interpretation package, individually named raw reviewer/QC/date/status fields or a strict versioned subset document, history_mode, rationale, created_at, request_key/input_hash/content_hash. Unique(author,request_key); monotonic exact previous-hash chain per row/source. No arbitrary extras field used for authority. |
| `LegacyWorkflowEvidence` / `legacy_workflow_evidence` | proposal_id, source_id FK and retained class/scope, source snapshot/byte/text hashes, reference_kind source|task, optional DocumentSource linkage FK and optional ReviewTask FK with matching-kind check, immutable reference hash. Unique proposal/reference key. Capture the exact target, every source version of its logical document checked by the existing batch owner contract, and any selected existing/reused task; task evidence resolves full retained task/event history. A source evidence row may predate DocumentSource, so its SourceVersion FK remains authoritative. |
| `LegacyWorkflowDecision` / `legacy_workflow_decisions` | proposal_id, operation, exact content_hash, independent actor, explicit content_reviewed, rationale, occurred_at. Unique(proposal,operation); allowlist/check constraints. Append-only containment exceptions only. |
| `LegacyWorkflowApplication` / `legacy_workflow_applications` | proposal_id unique, exact proposal/evidence/decision hash, actor, request_key/input_hash, result hash, applied_at. Durable receipt even for a meaningful provenance-only package with no new task. Unique actor/request_key and proposal application; changed retry conflicts. |
| `LegacyWorkflowTaskLink` / `legacy_workflow_task_links` | application_id, mapping index/field/token hash, stable account FK, task FK and originating event FK/revision, effect_kind created|linked|reused, and nullable unique server effect_key for created assignments. Captures retained restrictions; links are immutable normalized references, not a comma-separated task-ID list. |

Raw date declarations remain in the immutable proposal sidecar, not in ReviewTaskEvent.occurred_at. Actual applied task/account/event relations are normalized in TaskLink. Do not add legacy reviewer text, imported dates or approval flags to SourceVersion or accounts.

Why new DDL: existing raw VDR rows preserve inputs but cannot record current stable-ID application, independent declaration review, atomic task links or durable retries. ReviewTask.rationale is not a safe substitute for structured imported-date provenance. TrackerImportApplication belongs to a different register/whole-XLSX contract; reusing it would weaken source taint and conflate legal-register application with coordination. A UI-only “create task from row” shortcut can reuse TaskCreate without DDL, but **does not close this provenance/application requirement** and should not be presented as this increment.

## Authorization, private metadata and restriction unions

1. At owner preflight/create, retain original VDR uploader-only batch access and integrity checks. Reject quarantined rows, wrong matter, wrong logical document, missing exact DocumentSource link or ambiguous unlinked source selection. Never resolve by filename/VDR index alone.
2. Target writes require `review_work.source(..., write=True)`, current non-superseded/unfrozen source, lifecycle.mutable and the existing task engine. Inspect linked historical source versions with historical read; do not rewrite them or move their citations.
3. Explicitly snapshot the selected subset as its **own** source-bound object. Keep original CSV/batch routes private. Named SME review can see only that proposed subset after owner selection and current full-union source checks, not all raw rows, unknown vendor columns, prices, filenames or other-matter fields. No ordinary matter member gets a private proposal merely through a task link.
4. Free text is not automatically classified by this bridge. The owner must attest that the selected provenance belongs to the specified matter/source context; uncertain/compound fields remain unresolved. A named reviewer opens the exact proposed subset through an explicit review assignment. No automatic downstream sharing of accepted history is added. Assignee notifications contain the existing task metadata and a fixed current-assignment rationale, not imported CSV text or date claims.
5. Evidence includes every relevant current/retained restriction: exact target source; all versions of that logical document which the existing batch owner check requires; every additional source linked to that import row; selected existing/reused task and **all** its task events; proposal, decisions and application links. These source IDs are server-derived, deduplicated and frozen in evidence. This preserves the existing conservative all-version import-read boundary rather than letting a newer ordinary version erase an older known partition. Do not select the first source/clean-team scope or infer an unrecorded historical classification. If the bounded complete union cannot be captured/authorized, return a generic unavailable/conflict, not a truncated permissive package.
6. Proposal body defaults to original author and the named independent reviewer only, each subject to current source/retained authority. Task assignees get current task rights through existing rules, not automatic raw-history rights. A later explicit broader history-sharing design is outside scope.
7. Every list/read/count/preview/decision/apply uses fresh authentication and final exact authorization rechecks; opaque request hashes are not grants. Do not add a global input stamp that invalidates a write merely because it appended its own receipt. Denial audit messages contain no supplied names, IDs, dates or passages.

## Application transaction and idempotency

1. Lock matter, then exact proposal and any target tasks in stable order. Recheck freeze, current source snapshot, row/profile/content/evidence hashes, expected task revisions, actor/uploader capability, target identity eligibility and required independent decision/current reviewer scope.
2. Derive effects on the server. Create new tasks through `create_task(commit=False)`; link/reuse only exact permitted same-source/stage tasks. Do not forge TaskEvent actor, occurred_at, status or assignee acceptance. Keep normal notification dedupe and event history.
3. Task effects dedupe by a server key containing exact matter/source-version, field-derived stage and stable account ID. Repeated equivalent metadata from another retained batch linked to the **same exact source** reuses the recorded effect after current checks, and adds provenance through a new application/link receipt. Byte equality across different source IDs/documents/matters never merges tasks.
4. If an earlier effect exists, preflight must explicitly pin its permitted task/revision and display reuse; do not silently select a hidden/stale task or produce a duplicate. A changed deadline/reassignment uses the existing explicit TaskEvent command, not another import-created task. A deliberately new cycle can be created through the normal task engine; it is not disguised as replayed import application.
5. Commit application receipt, task events/notifications and normalized links atomically. No nested service commit. Any stale identity/policy/task/decision rolls back the whole row proposal. Do not report partial task creation from an atomic row command; bulk batching is a later explicit contract.
6. Same request key and exact input returns the same retained receipt after current read/use checks; changed input is409. Cross-batch equivalent source effects do not multiply tasks. Repeated provenance-only application has a durable receipt and creates zero task/clock/legal events.
7. A source policy change or newer proposal requires explicit refresh/reproposal; do not fall back to an older approved package. Final response withholding after a later wall change must not falsely claim an earlier committed authorized application was undone.

## Signing, audit, retention and rollback

Add all five retained tables to the next signing manifest and application freeze guard; do not rewrite historical manifests. The audit resolver must follow the entire LegacyWorkflow proposal/evidence/application/task-link union and existing task/event retained restrictions regardless of audit category. Audit events record IDs/action/outcome; raw vendor names/date text stays in protected business records.

New proposals, historical confirmations and applications stop after signing. Only narrow append-only withdrawal/revocation is an access-tightening exception, with minimal response and retained prior decisions. Operational task history and previously sent in-app notifications remain history; revocation is not deletion or a fabricated cancellation.

Migration has no automatic backfill/application. Existing staged rows remain proposals; existing assignments/clocks/approvals remain unchanged. Rehearse on a verified restored copy, compare every prior-table digest/identity count and orphan check, run upgrade twice, and test metadata via Alembic command.check on SQLite/PostgreSQL. Static frozen DDL and ORM index declarations must match. A retained row blocks destructive downgrade before any new table is dropped. Safe rollback disables the new command surface and retains records/old routes; use forward repair or separately approved verified restore, not delete/import reversal.

## Proposed files and acceptance tests

Implementation ownership, only after root review:

- New `models_legacy_workflow.py`, `schemas/legacy_workflow.py`, `services/legacy_workflow.py`, `api/legacy_workflow.py`, and a root-reserved additive migration.
- Narrow model import; main/router and lifecycle/audit integration under root coordination. Reuse VDR/read-only helpers and `review_work.create_task(commit=False)`; no imported timestamp option added to TaskCreate/TaskEvent.
- A new `LegacyWorkflowImportPanel.tsx` mounted narrowly in the existing VDR/import/source-work UI. The actual existing VDR component filename must be confirmed before editing. Separate current task effects from raw historical declarations and independent review. No browser role switch or auto-apply on upload.
- New isolated `tests/test_legacy_workflow.py`; existing VDR/task/clock/lifecycle/audit suites as regressions.

Required meaningful cases:

1. Exact linked source identity; filename collision, equal bytes/different documents, foreign matter and quarantined row refusal.
2. Import owner isolation and named reviewer subset access without raw-batch/unknown-column disclosure; Root-only/bank/client denial and current wall/scope revocation before emission.
3. Exact UPN suggestion, ambiguous display names, inactive/walled/root-only/external targets, compound names and email-not-UPN behavior. No role/grant/custodian creation.
4. Parallel review/QC tasks through existing engine; distinct current clocks/notifications; source/task retained clean-team unions and target task revision conflict.
5. Current assignments start at server now; imported dates/statuses stay unchanged declarations. No completed/accepted/reviewed event, finding, coverage, release, measured activity or hotness generated from historical strings.
6. Date-only, explicit offsets, ambiguous DMY/MDY, DST ambiguity/nonexistence, future/reversed/invalid/formula-looking values and claimed Days Open. No locale guessing or midnight conversion.
7. Independent exact-history confirmation, no author/subject self-confirmation, stale hash, reviewer role/clearance loss, reject/revoke/withdraw and replay behavior. Current-only assignment does not masquerade as confirmed history.
8. Request retry and cross-batch repeated effects create one current assignment; different source IDs remain separate. Provenance-only receipts create no task or clock events.
9. Atomic failure leaves no half row/task/notification; concurrent apply has one receipt/effect; current identity/source changes withhold prepared names/counts/results safely.
10. Complete signing/audit taint union, populated downgrade refusal, immutable UPDATE/DELETE triggers and post-signing containment receipts. No data/approval/source/hash backfill mutation.

Run first SQLite, then disposable PostgreSQL schemas, including command.check and real transactional concurrency. Record exact component results; do not count a parser compilation or skipped test as a PostgreSQL workflow pass. No fixture, migration or model test was run for this planning-only task.

## Coordination and proposed order

The `azure_portability` agent is planning checklist replacement impacts in docs85 only. Its edge/impact/evidence/decision/context records and source-free added-request obligations are separate from this source-bound import bridge. Do not force source-free checklist work into ReviewTask or reuse playbook impact FKs for checklist publication. This plan does not touch checklists, coverage rules or replacement publication.

Recommendation: root reviews both plans, then assigns one migration owner and exact next revision. A standalone0039 for this bridge is justified **if root reserves it**; checklist replacement can follow in the next revision. If root chooses one combined revision, freeze the complete static DDL under a single owner before test processes start. No agent has reserved or authored0039 through this plan.

Review decision requested from root: approve the five-table retained bridge, two explicit history modes, owner/named-SME subset ACL and present-time-only task effects; or select the narrower UI-only task shortcut while acknowledging that it does not complete legacy provenance/application coverage. No application/DDL work begins under this plan alone.

## Independent root-review amendments — required before implementation

Read-only source review on 24 November 2026 identified the following contract clarifications. Root accepted the first as implementation-blocking. These are requirements for a future implementation, not claims that this planned bridge exists or that a fixture has demonstrated a new production defect.

1. **A private proposal ACL does not attach its restriction union to a task.** `review_work.create_task` captures the target source's current single `SourceWorkScope`; `eligible` checks additional retained records only when explicitly supplied; `task_row` authorizes the task and its events, not a future proposal sidecar. Choose and document one authority contract before building: either enforce the exact complete retained input union through every derived task read, transition, clock/session use, notification and audit path, or require a separate explicit current human assignment containing no private imported history or imported rationale. The latter uses ordinary current task authority and must not claim that the historical declaration was accepted. A proposal/task link alone is never declassification or an access grant. Source/task evidence keys must preserve distinct historical restriction/origin rows; a source-ID-only key cannot represent multiple retained scopes.
2. **Freeze the history state machine and replay identity.** Define permitted confirm/reject/withdraw/revoke predecessors, the unique latest proposal chain per exact row/source, and exact replay behavior under the matter/proposal lock. `Unique(proposal, operation)` alone does not prevent both confirmation and rejection or two competing proposal successors. Current scope/independence and the exact decision hash remain necessary at every reliance point; revocation cannot erase genuine task activity.
3. **Smallest safe first slice:** owner-only, exact-linked-row preview plus an explicitly chosen ordinary current review task, with no auto-apply, imported completion, historical confirmation or named-reviewer sharing. Keep raw declarations private and visibly unchanged. This is a bounded coordination shortcut and leaves the prompt's durable legacy provenance/application requirement **PARTIAL**. If the retained bridge is selected instead, implement one `retain_unconfirmed` reviewer mapping first after resolving item 1; defer the wider confirmation/link/reuse surface until its own boundary tests pass.

No migration is reserved by this review. Root is sequencing the Resources Excel scope first. Required acceptance evidence includes an older pricing-restricted version/task history followed by a current ordinary version: neither the proposal bridge nor task/notification/clock endpoints may reveal private imported material to an actor outside the retained union. A deliberately separate current assignment must expose only its ordinary current task contract.
