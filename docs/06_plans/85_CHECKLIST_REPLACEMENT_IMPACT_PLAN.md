# 85 Checklist replacement and coverage/report impact plan

24 November 2026. **Planning only - awaiting root review.** This document changes no application code, models, migrations, approvals or live data. Head 0038 is the reviewed baseline. No migration number is reserved here.

## Requirement and the precise remaining gap

The active requirement is 03_CHECKLIST_AND_WORKFLOW_EVENTS.md (workspace reference not included in the public snapshot): versioned request taxonomy, many-to-many document coverage, governed workflow transitions, linked request/disclosure references and reproducible historical report coverage. Bloomberg Law is a request-taxonomy source, not legal advice or an approved Freshfields report. The existing A-N section map plus one original synthetic request is not a completed inventory of every request in the source PDF; additional requests require separately authored, counsel-reviewed abstractions and provenance.

The current block is deliberate and explicit. `services/checklists.transition(..., 'publish', ...)` returns 409 when another published checklist exists: "Checklist replacement publication requires the material-change impact workflow, not implemented in this batch." Drafting, submission and independent definition approval already work. Removing this guard alone would allow multiple apparently current published scopes without impact decisions, coverage provenance or report handling.

Four related gaps must be solved together:

1. `ChecklistVersion.previous_id` follows the latest **authored** version, which may be an unpublished or rejected draft. It is not a reliable pointer to the currently published replacement base.
2. Coverage staleness currently compares source/finding snapshots within one checklist version. There is no governed mapping/disposition across old and new request definitions, nor an explicit current-published successor edge.
3. `checklist_records.snapshot_report` records only coverage events whose source IDs intersect the report's finding sources; revising a report copies those exact old references. An added request, a derived GAP with no decision row, or a legacy report with no checklist snapshot can therefore be absent from report provenance. Absence must not be treated as unaffected or complete diligence.
4. `reports.read/persist` and `workflow.release_decision` validate report content, source lineage and existing DDR approval, but do not currently evaluate checklist-replacement impacts. Historical reproducibility exists; current coverage/report eligibility after a replacement does not.

The new workflow must also use fresh request identity/PDP after response preparation. Existing checklist routes call services with the dependency's Principal directly. Reusing that cached identity for a new impact preview, inbox, report-context or decision response would repeat the response-race problem already corrected elsewhere.

## Reuse the existing contracts

| Existing contract | Reuse and limitation |
|---|---|
| `ChecklistVersion` / `ChecklistVersionDecision` | Immutable definitions, draft history, exact hash/revision transitions and independent current SME definition approval. Preserve all old rows and initial publication behavior. |
| `ChecklistCoverageDecision` | Append-only recorded statuses, source/finding references, retained restriction union, partial-evidence checks, whole-document/OCR checks for VERIFIED, separate N/A and waiver requests/decisions. Create new target-version events only after a real authorized decision. |
| Section/item/coverage projections and document/finding links | Existing `checklist_projection_v1` creates stable normalized IDs and many-to-many links. Call it for newly appended versions/events; do not rewrite or duplicate the old projections. |
| `ChecklistRequestEvent` / `ChecklistRequestEvidence` | Existing request/follow-up/reference history, exact import-row references and source-bound authorization. Preserve author-only treatment of source-free private notes. A scope replacement does not transfer or publish their free text. |
| `ReportChecklistSnapshot` | Retain exact historical coverage-event IDs. It cannot represent a selected request with no event or pin the complete declared checklist context of a new report. |
| `action_center.diff`, publication and independent task patterns | Reuse pure deterministic diff principles, locks, explicit decisions and idempotency patterns. Do not reuse its playbook `ImpactSnapshot`, `GovernanceTask` or `ImpactDecision` tables: their FKs and analysis-job semantics are specific to `GovernanceVersion`. |
| `review_work` / notifications | Reuse current and retained PDP helpers, named-eligibility logic and audit patterns. A generic `ReviewTask` has one required source; it cannot honestly represent a source-free added request or a multi-source union. Do not invent a source to fit that table. Optional source-specific follow-ups are a later explicit action, not automatic publication effects. |
| Reports, audience release, DDR human review and signing | Use new report versions and the existing independent package/antitrust approvals. Checklist publication must not create findings, supersede sources, run AI, resume DDR, send messages or approve/release a report. |

Current stored status names remain the existing contract. UI aliases such as IN_REVIEW/COMPLETED may explain UNDER_REVIEW/VERIFIED, but must not rewrite history or equate a missing request with a legal finding, approved N/A or waiver.

## Proposed bounded behavior

### Definition approval and publication

- Keep initial publication unchanged. A replacement targets an exact independently approved definition and the exact current **published** base, recorded separately from `previous_id` authoring lineage.
- Compare requests by stable `item_id`, not array positions. Identify added, removed, unchanged and changed definitions. Treat changes to request meaning, applicability/jurisdiction, evidence types, playbook references, specialist/tool manifests, provenance or report-section mapping conservatively as material. Mere documented set/order changes need not invent a legal change; free text must not be aggressively normalized.
- Preserve the current rejection of unapproved tool activation and same-matter published-playbook validation. The impact workflow cannot activate unavailable agents/tools or infer jurisdictional applicability.
- Serialize publication on the Matter row. Recheck the base is current, target hash/revision and current independent definition approver. Exactly one successor may consume a published base. An unchanged semantic replacement is refused rather than multiplying versions.
- Publication atomically records the successor, complete bounded impact snapshots and named notices. It creates no new coverage conclusion. Target-version requests initially have their honest derived GAP/unreviewed state; old decisions remain historical evidence.
- The server may internally enumerate opaque policy/coverage/report identifiers to prepare impact work, as the existing deterministic playbook assessor does. A Root Admin publication response contains only configuration/publication metadata, not source-derived counts, filenames, impact rationales or report titles. This is not a Root Admin source override.
- For this local slice, require a complete synchronous assessment: at most 50 request definitions, 200 impact work items, 500 distinct retained source-policy restrictions and a 256 KiB canonical snapshot. Query limit-plus-one and refuse before publication if exceeded; never silently truncate or publish a partial impact set. A production outbox/batched assessor is a separate reviewed extension.

### Scoped impact review

Each durable impact work item binds the replacement, old/new item definitions, exact old coverage/request/report IDs and hashes, and its complete source restriction union. Source-free added requests remain legitimate matter-scoped work; they are not evidence that a document does not exist. Separate work items allow different named SMEs to handle different clean-team scopes. A single mixed-scope item requires a reviewer cleared for its entire union; no eligible reviewer means visibly unassigned protected work, not partial approval.

An eligible reviewer must be a current active firm Legal SME, assigned and not walled, with current and retained access to every linked source, finding and report. They must differ from the replacement definition author and from the proposer of the coverage/disposition they decide. Root Admin alone cannot decide. Definition approval, impact disposition, coverage N/A/waiver and audience/antitrust release remain distinct decisions.

An unchanged request may receive an explicit, fresh-evidence carry-forward decision. This appends a new target-version coverage event through existing validation; it does not copy a status silently. VERIFIED must still satisfy current confirmed text, verified OCR, whole-document review and current finding decisions. Changed/added requests require fresh coverage review. Removed requests remain retained with a removal disposition. N/A and waiver outcomes never transfer as approvals: use the existing fresh request plus independent SME decision routes. Dates/owners/notes are provenance or proposed work metadata, never backdated workflow events or automatic completion.

### Full source-union authority

Capture the union of old coverage histories, referenced findings, request evidence and affected report lineage, including restrictions on inputs later removed from a target request. Authorize both the current canonical source PDP and every retained matter/classification/scope pair. A later ordinary classification or empty submitted source list cannot erase an earlier pricing/other clean-team restriction.

`SourceWorkScope` is one restriction per row. Retain multiple evidence rows when one source has different historical restrictions; a uniqueness key of only `(impact, source_id)` is insufficient. Existing coverage `_restrictions` are not mapped one-to-one to source IDs: conservatively preserve their complete union rather than pretend that missing association can be reconstructed. Do not copy source prose or imported private notes into metadata-visible configuration rows.

Inbox counts, notifications, work-item details, history, exports, audit resolution and decision outputs all require the same union. Read responses must reauthenticate/recheck after preparation using `response_guard.protected(..., scope_check=...)` or the established equivalent. Configuration-only reads must use a config-role scope check rather than the legal-only default `tables.begin`. After an authorized write, recheck fresh identity and returned-object authority; do not compare a stamp against the command's own authorized mutation and return a false 409. Denial audits must be sanitized and disclose no submitted source IDs or free text.

## History and report invalidation

Old coverage events, request events, report bodies, approval receipts and signing records remain immutable. Expose recorded versus current status separately. Historical internal reads continue only after current plus retained PDP checks. Default current views select the successor edge; an older published row remains published historically, with a derived `effective_state=replaced`, rather than appending a state that would break existing historical coverage reads.

For every newly generated or explicitly refreshed report, pin its declared selected checklist version/hash and selected item context, including GAP/no-event entries. This is a report's stated scope, not a claim to know all matter coverage. If a selected source-bearing request cannot be fully authorized, refuse rather than silently drop it and claim completeness. Missing legacy context is UNKNOWN, not unaffected.

When a material replacement affects that context, record a durable report impact. Keep the old artifact and approval as historical evidence, while suspend its eligibility for **current external delivery or new release** until an authorized resolution produces a fresh report version with current context and separate package approval. Do not fabricate a revocation approval, clear `released` silently or rewrite the old PDF. Bank responses reveal only that a current eligible report is unavailable, not internal impact details. Changes to a relevant report-section mapping and added source-free requests must be included, not only intersecting old source links. Legacy reports with insufficient context receive conservative review work before being treated as current under the new scope.

Store a protected context hash in the new report's server-owned body/approval manifest so the existing whole-package hash actually binds the checklist context. A sidecar unbound to the package hash is insufficient. Old body/hash validation remains unchanged for legacy versions. Default manual prose revision preserves the exact old context; a distinct explicit refresh action creates a new context/version. Do not make ordinary edit silently recalculate coverage. Recompute/validate the context hash on read, release and download, including after rendering. Existing DDR revised-report/human-review hooks must bind the new complete package; no obsolete approval or graph acknowledgement carries forward.

## Additive records actually needed

Recommended after review: six checklist-specific tables in an isolated model module, not modifications to historical coverage/version columns.

| Proposed record | Purpose and key constraints |
|---|---|
| `ChecklistReplacement` | Immutable published base-to-target edge; base/target IDs and hashes, deterministic diff/impact-set hash, publisher and time. Unique consumed base and unique target; same-matter/cycle checks. Separates publication lineage from draft `previous_id`. |
| `ChecklistImpactItem` | Immutable bounded work/snapshot for a request, coverage or report impact; exact replacement/item/report references, snapshot/hash, change kind, creator and current named assignment snapshot. Decision history derives its status. Unique replacement + typed subject + snapshot hash; no source prose in broadly visible fields. |
| `ChecklistImpactEvidence` | Immutable `SourceWorkScope` rows plus origin/input references and policy/snapshot hashes. Deduplicate by work item + source + retained-restriction/origin fingerprint, preserving multiple historical scopes. |
| `ChecklistImpactDecision` | Append-only independent disposition, exact work snapshot and definition hashes, real actor/time/rationale, and resulting new coverage/report references when applicable. Actor/request-key plus input hash; exact replay returns same result, altered replay 409. |
| `ChecklistImpactNotification` | Named work-item recipient with idempotent unread/read/acknowledgement metadata. Reading is not a decision; no external email sending. Unique item/recipient. |
| `ReportChecklistContext` | Immutable report/version + declared checklist/item/event-or-GAP context JSON/hash. Bind the complete expected context set into the report package hash; unique report/checklist version. Preserve the existing `ReportChecklistSnapshot` for historical event references. |

Use the existing audit log for actual transitions instead of inventing a second generic event bus. Add new immutable tables to explicit immutable-DDL guards, signing manifests, audit source resolution and retained-union checks. Notification read/ack metadata may remain operational; it must not mutate signed content. No automatic coverage backfill or guessed successor/context inference is part of the migration. Backfill only deterministic structural keys if required, with lossless receipts; legacy context uncertainty remains explicit.

## Idempotency and concurrency

- Preview hashes bind base/target definition hashes, changed-item mapping, exact latest coverage/request revisions, affected report version/content/context hashes and all retained/current policy fingerprints.
- Under the publication lock, recompute and compare before inserting the successor and work/notices. Concurrent coverage/report/source/policy changes require a fresh preview; competing successors cannot both publish.
- Scope publication is not authority to migrate coverage. Disposition commands require the current assigned independent SME and exact snapshot immediately before and after validation. Role/wall/clean-team/owner changes invalidate eligibility.
- Commit a decision and its new coverage projection or report link in one transaction. Do not call a helper that commits halfway through. Refactor existing `record/commit` boundaries narrowly to support an internal `commit=False` path if needed, preserving all existing callers.
- No decision retries a provider, launches a job, marks a generic review task complete or authorizes an external release. Replays deduplicate decisions, outputs and notices. A newly changed snapshot becomes new work, never an overwrite of an old decision.

## Implementation files, tests and sequencing

Proposed owner after root review: checklist-impact services/schemas/API and ChecklistWorkspace/ChecklistDraftEditor/ChecklistRequestLog additions; new `models_checklist_impact.py`; repository queries; focused `test_checklist_replacements.py` and `test_checklist_report_impacts.py`. Narrow integration points are `checklists.py`, `checklist_records.py`, `reports.py`, `workflow.package/release_decision`, report read/download APIs, existing DDR revised-report helpers, `data_tables.authorization_inputs`, lifecycle manifest/freeze guards and audit source resolvers. Root must coordinate those shared files and main/router/Swagger integration.

Test first:

1. Initial publication and all existing history/N/A/waiver/source-type/OCR checks remain valid; replacement guard stays closed until the whole path exists.
2. Exact current published-base selection despite intervening drafts/rejections; stable-ID added/removed/changed/reordered items; no-op refusal; concurrent publications produce one successor.
3. Root-only, self-approval, inactive/revoked/walled SME and cross-matter denial; mixed pricing/other-scope inputs and later source relaxation cannot reduce the retained union.
4. Fresh role/clean-team/wall removal during preview/inbox/history/report preparation withholds the prepared response; one unauthorized input hides the entire mixed item, including counts/rationales.
5. Unchanged coverage carries only after an explicit current decision; material changes, N/A/waiver and new GAPs never auto-complete. New source versions, finding corrections, QC and evidence drift reject stale snapshots.
6. Historical report snapshots and bytes remain unchanged; added empty requests, report-section changes and legacy missing context create impact. Current external list/read/download/release cannot bypass unresolved material impact; internal authorized history survives.
7. Context changes produce a new whole-package hash and new human/audience review; ordinary prose edits preserve context. No automatic DDR resume, paid call, finding change or release.
8. Exact request replay produces one edge/work/notice/decision/output; changed replay 409; transaction failure leaves no partial publication or migrated coverage. Bounds fail before mutation.
9. Signing hash includes the new retained records; proposal/approval races invalidate signing; after freeze no replacement, reassignment, coverage/report mutation or notice payload changes. Read acknowledgement remains separate operational metadata.
10. Static additive DDL, append-only guards, FK/index parity, SQLite and isolated PostgreSQL tests; root-owned verified backup/rehearsal/application only after stable head and full regression.

The parallel docs84 legacy workflow-application plan, being drafted by `saved_views_backend`, owns selected imported reviewer/QC/date proposals. Preserve uploader-only raw batches and only expose explicitly selected source-bound fields to its named independent reviewer. That slice must not reuse checklist request/disclosure references or turn imported dates/statuses into checklist approval. Its assignment/task linkage models and this replacement/context graph are distinct. Neither agent reserves 0039. Root should appoint one static-DDL/model integration owner and explicitly sequence the two accepted changes (for example 0039 import application, then 0040 checklist impacts), or approve one combined additive revision after both contracts are frozen.

## Rollback and review gates

Keep replacement publication default-closed until its endpoint, source-union authority, report containment, immutable DDL and tests are complete. Before publication, rollback is code/config removal with the current published version unchanged. After any real publication/decision, retain all immutable history and use a forward corrective version; do not delete edges or reactivate old legal conclusions. Disabling the UI/feature must not remove report-eligibility containment or resurrect an outdated current external report. A rollback binary that lacks that containment requires external delivery to remain closed until a forward fix. Schema downgrade is only for an unused isolated rehearsal, never a shortcut around retained legal history.

Root review must settle the six-record scope, conservative external report containment, context-hash package binding, reviewer assignment for multi-scope/source-free work and migration sequencing before implementation. The current root regression baseline was reported as **563 passed, 1 skipped, 743.02 seconds**. This plan was verified by read-only prompt/code/test inspection; proposed implementation tests above have not been written or run. No browser work occurred.

## Independent root-review amendments — required before implementation

Read-only source review on 24 November 2026 identified these implementation requirements. Root accepted item 1 as implementation-blocking. They refine the proposed design; replacement publication remains closed and no migration is reserved.

1. **Historically published does not mean effective-current.** Existing `checklists.coverage_version(write=True)` checks only `state == published`; `checklist_records.request_log`, N/A/waiver commands and `snapshot_report` depend on that contract. Keeping replaced versions historically published therefore also requires a server-owned effective-current predicate. Use it for every new coverage/request/applicability/waiver write and every new or explicitly refreshed report context. Direct old-version routes must reject writes after replacement. Historical authorized reads and exact copied old report context remain available. Default report capture must not enumerate every historically published version as current scope.
2. **Take the common lock before reading the inputs being decided.** `lifecycle.guard_flush` already acquires the matter row, but only at flush; it checks freeze and does not revalidate a previously read checklist base/coverage snapshot. A coverage command can read the old published state, wait behind publication at flush, then append to the replaced version unless it rechecks after acquiring the lock. Establish a consistent matter-first lock order for publication and affected coverage/request/report/context commands, reread exact revisions/effective-current state under that lock, and avoid mixing the current version-first transition order with a new matter-first order. A real PostgreSQL interleaving test must prove the old-scope command either completes before impact enumeration or fails after replacement, with no omitted committed input.
3. **Specify reassignment without mutating the immutable impact snapshot.** An immutable item containing a named assignment cannot recover when that SME leaves, becomes walled or loses clean-team clearance without an append-only reassignment/assignment event contract. Define who may assign, exact expected assignment revision, complete-union eligibility, notification dedupe and a newly evaluated independent decision. An unassigned item must remain protected; a Root-only actor must not learn source-derived counts or reasons through reassignment. Reading or acknowledging a notice grants no authority.
4. **Smallest safe first slice:** a bounded deterministic replacement preview, with exact current published base, semantic diff and complete protected impact union, while the existing publication guard stays closed. Add fresh identity/output checks to the touched read paths. Then implement immutable report context/package binding and central current-delivery containment before enabling successor publication. No preview, schema installation or configuration approval alone closes the replacement/report-impact requirement.

The required tests must include direct old-version POSTs, a publication-versus-coverage/request race, an added source-free request affecting a legacy report with unknown context, a removed restricted input that remains retained, an approved sanitized bank package without original-source disclosure, and reviewer loss/reassignment. All current external report list/read/download/release paths must consult the same eligibility decision; historical bytes and receipts stay unchanged. No application code, DDL, live row, human decision or provider call was changed by these planning amendments.
