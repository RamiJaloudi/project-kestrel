# DataTables rollout plan

## Current implementation record

**Deadline scope approved 24 November, approximately 12:50 PM Eastern:** finish Registry acceptance, then freeze application features. Secondary-register conversions below are deferred beyond today's submission. Final regression, honest packaging and Azure preparation proceed in parallel; genuine approvals and the bounded final manual walkthrough remain separate gates.

The original read-only planning snapshot below is retained for context. Completed local acceptance records now exist for [Review Tasks](../02_workflows/89_TASK_DATATABLES_IMPLEMENTATION.md), [findings/risk/consent grids](../02_workflows/90_FINDINGS_DATATABLES_IMPLEMENTATION.md), the [contract inventory](92_CONTRACT_INVENTORY_DATATABLE_PLAN.md), the [account directory](93_ACCOUNT_DIRECTORY_DATATABLE_PLAN.md), the [scoped audit grid](94_AUDIT_DATATABLE_PLAN.md) and [Registry access/history](95_REGISTRY_DATATABLE_PLAN.md). Existing inventory and financial grids remain working baselines. Application features are frozen for final regression and submission; secondary-register conversions are deferred. This does not claim all tables, expanded feature gates, production-scale testing or manual script acceptance are complete.

**24 November 2026 — read-only implementation plan.** The latest user priority supersedes the earlier feature-gate execution order: deliver consistent table workflows now, starting with the matter-wide Review Tasks grid that root and the backend agent are implementing. Do not wait for manual SME review to build these increments. Genuine legal/profile/release decisions remain required at their existing boundaries and at the final acceptance gate; this plan grants no approval or processing authority.

Only this document changes. No frontend, API, dependency, DDL, live state or presentation changes were made. Rollback is removal of this planning document. Root's in-flight Review Tasks work must be reconciled with this snapshot before the next increment.

## Existing reusable foundation

The active prompt (workspace reference not included in the public snapshot) asks for one typed wrapper, server paging/filtering/sorting, authorized export and bulk actions, and owned/shared saved views. It explicitly preserves charts and the reader.

Local primary-source package inspection confirms:

- `datatables.net-react` **2.0.1**, `datatables.net-dt` and core **3.1.5**, React **18.3.1**; the installed React package declares React `^18.3.1 || ^19` and core `^3.0.0` peers. These packages declare MIT licensing. No upgrade is needed for this rollout.
- Installed `dist/index.d.mts` supports `<Column>` children receiving `(data, type, row, meta)`, named/indexed React slots, `Options['ajax']`, and `DataTableRef.dt(): Api | null`. The installed implementation uses React portals. Keep JSX action controls; do not replace them with HTML strings or delegated `innerHTML` handlers.
- [KestrelDataTable](../../frontend/src/KestrelDataTable.tsx) already supplies server-side draws, 10/20/50-page sizes, named sortable/searchable columns, 400 ms global-search delay, column filters/picker, selected-ID checkboxes, internal selected CSV/XLSX export, abortable queries and 15-second refresh. [InventoryDataTable](../../frontend/src/InventoryDataTable.tsx) and [FinancialDataTable](../../frontend/src/FinancialDataTable.tsx) use it.
- At inspection, dataset/query/saved-view types accept only `inventory | financial`; saved evidence references accept only `source | financial`. This is not yet an adapter for every domain. Selection/export/share capability must be explicit per dataset, rather than inferred from one `allowExport` flag. No Responsive, Select or Buttons extension is installed; selection and export are application controls.
- [SavedTableViews](../../frontend/src/SavedTableViews.tsx) already preserves immutable revisions, exact hashes, ownership and independent named internal sharing. Bank saved queries are private financial queries only; Halden saved queries are unavailable. Column visibility is explicitly a live preference, not persisted saved layout. These limits must remain visible.

## Implementation order

| Increment | Deliverable | Preserve / prerequisite |
|---|---|---|
|0, alongside 1|Shared request-generation, denial, selection and loading safeguards below; narrow typed dataset extension.|Keep the two working datasets and their actual server contracts. Do not invent a generic endpoint URL or arbitrary SQL-column interface.|
|1, already assigned|Matter-wide **Review Tasks**: document/version, stage, assignee, state, due/SLA, actions; timing columns optional.|Query existing task/event/SLA models. Open task details and the existing source work/reader flow. No automatic acceptance, completion, analysis or legal sign-off.|
|2|Risk Review findings/issues, risk and consent registers; then contract inventory in `MatterWorkspace`.|Separate server-paged rows from board aggregates. Preserve connected finding editor, document-review progress, exact evidence, history, manual lawyer finding and revision-aware decisions.|
|3|Admin account directory, matter assignments/walls and scoped audit.|Use directory/configuration/audit-specific authority. The current legal source-table guard cannot be applied blindly to Root Admin configuration. No source override.|
|4|Custodians/parties and assignment history; policy/playbook versions, jobs and impact task queues.|Reuse source detail forms and domain commands. Table selection is not an assignment or approval; job recovery is not a generic paid retry.|
|5|Intelligence record rows, reconciliation, tracker/import/package lists and other eligible secondary registers.|Keep the wheel/group drilldown, exact financial evidence, retained workbook proposal review and audience-specific package controls.|
|Final gate|Combined regression, signed-in role/browser checks and workflow-script verification; genuine SME/manual acceptance still pending.|Update screenshots/scripts after the stable UI. This order does not enable paid processing, publish profiles, release content or authorize public deployment.|

For increment 1, the row key is the **task ID**, not source ID: one document can have several parallel stages. Optional cross-page selection needs an explicit bulk-command contract before buttons appear. Preserve expected task revision, idempotency key, eligible assignee, rationale, historical read-only state and current source/retained restrictions. Reuse `SourceWorkPanel`'s reader/task-clock handoff; choosing a row must not itself record an opening or advance work.

## Actual locations and action flows

Snapshot: **26 native `<table>` blocks in 18 components**, in addition to the two wrapper consumers. This is a source inventory, not a completion metric; card lists and root's new in-flight component are additional work.

| Location | Actual headers / current representation | Keep when changing the list |
|---|---|---|
|`SourceWorkPanel`|Tasks, custodians and parties are source-specific cards, not an existing matter-wide grid.|Eligible-person forms, task revision/event history, accept/start/pause/resume/complete/reassign/cancel/reopen, SLA bindings, evidence reader and historical restrictions.|
|`MatterWorkspace`|Contract/counterparty, Scope, Review, Open findings. Finding/source or Contract/trigger, Risk or Requirement, Owner/action.|`choose(f)` connected editor; source/version and `finding` deep links; exact passage `unit/start/end`; whole-document review remains separate.|
|`DocumentReviewPanel`|Progress stages, eight-risk list and whole-document form; **no table**.|Keep this detail panel. Engine outcomes do not become lawyer decisions or document completion.|
|`AccountManagement` / `Administration`|Account directory is a select plus edit form. Existing access table: Account, Organization, Assignment active, Ethical wall; history: Revision, Event, Rationale, Time.|UPN, display name, employee-ID leading zeros, active/role state, selected account form and expected revision. Preserve separate access/wall approvals.|
|`AuditWorkspace`|Time, Action, Outcome, Object.|Category/matter/time scope and separately generated JSONL/CSV/HTML/PDF ZIP+manifest exports. Preserve the 1,000-event export bound.|
|`ActionCenter`|Document/target, Partition, Impact, Status/due, Open; separate Field/Before/After diff.|Open task, historical source reader, exact snapshot decisions, rationale, claim/rerun/reconciliation/closure. A diff is evidence, not a bulk command.|
|`PolicyWorkspace`, `JobWorkspace`, `WorkflowWorkspace`|Name/ID, State, Revision, Actions; Job, State, Attempts, Actions/Source; small Risk/Engine outcome table.|Open exact definition, replacement draft and state-specific independent actions; inspect result, bounded explicit recovery, source click-through.|
|`IntelligenceWorkspace`|Permitted record, Delay, Reviewed legal risk, Financial signal, Evidence; currently its own 20-row paging.|Cluster path/wheel, UNKNOWN handling, evidence-backed explanation and reader. Bank projection omits internal legal/delay/reviewer data.|
|`TrackerExchange`, `VdrImportPanel`, `FolderImport`|Proposal selection/status/changes; package headers from retained workbook rows; CSV Row/File/key/Source/index/folder/Result; folder Import/Document/Version/Access/Status.|Original row numbers, quarantine, explicit proposal decisions, exact package/recipient approval/download. Never remap selected rows by display index.|
|`WallChecker`, `LifecycleWorkspace`|Document/policy reference, Decision, Reason; historical Time/operator, Person/action, Result, Receipt; Document/Version/Filename.|Recorded receipt inspection, current precheck distinction, retained source-version links and holds/signing decisions.|
|`ReportsWorkspace`|Finding/source, Risk/requirement, Action/status in retained annexes.|Saved report snapshot, citation, reader and current-finding link; editing live findings must not silently rewrite the annex.|
|`DocumentReader`|Literal workbook Row/A/B/... and extracted Word table rows.|**Keep as evidence rendering.** Preserve coordinates and source order, immutable literal formulas/caches, sheet visibility controls and independent pane authorization. Generic sorting/search must not reorder the evidence surface.|
|`Resources`, `GovernancePreview`, `DiligenceWorkspace`|Engine/Status/Details, fixture version/classification/approved/released, and static register/output status.|These are small informational or preview tables. Record their final treatment explicitly; do not add live source requests to preview fixtures. Bounded detail/evidence tables do not justify replacing the reader.|

Agent Registry, DDR Runs, reconciliation and several inboxes are presently cards/lists. Include them in the later register inventory; absence of `<table>` does not mean they already use DataTables.

## Significant state and UX findings

These are code findings, not claims of a reproduced backend authorization bypass.

| Finding | Required handling |
|---|---|
|Wrapper selection survives changed filters, new draws and refresh. Current consumers remount on matter, but the wrapper itself does not reset all state on dataset/matter/session change.|Separate active detail from bulk selection. Clear or explicitly reconcile selection on changed scope/filters; show whether selected IDs are outside the page/filter. Reset internally on dataset/matter/CSRF identity generation, not only callers' React keys. Server reauthorizes every ID.|
|`ajax` parses JSON before attaching HTTP status. A non-JSON 401/403/409 can enter the generic error path without `deny()`.|Classify status even if JSON parsing fails. Clear table, selection, saved configuration and protected parent details on denial/stale authority; retain only a safe message.|
|Queries have aborts, but export has neither an abort controller nor a scope epoch; it checks `alive` only.|Abort/suppress stale downloads after denial, unmount or scope change. A completed old response must not create a new object URL after the UI has invalidated that scope. Keep backend fresh export checks.|
|Loading a saved query changes typed filters underneath unchanged workspace controls. Detaching the saved identity after a search/sort edit leaves those typed filters active.|Show a readable effective-filter summary and an unambiguous “Use workspace filters” action. Do not rely on raw JSON. Synchronize meaningful parent context through `onEffectiveQuery`; Finance currently does not consume it.|
|100 selectable IDs versus at most 50 source-bound saved-view evidence bindings.|Explain the different limit before save. Use operation-specific selection limits; do not silently truncate or reinterpret bindings.|
|The wrapper always adds a Select column and defaults to sort index 1.|Make selection opt-in for a supported action. Derive initial ordering from the named sortable column when selection is absent; do not carry index arithmetic unchanged into read-only admin/audit grids.|
|The 15-second query timer aborts a pending draw when another begins; background refresh can replace rows while a detail form is open.|Use one in-flight generation, avoid refresh starvation, preserve user edits and revalidate detail revision separately. Counts/loading/empty/failure must remain distinct. Sorting or paging must not submit a form.|
|Audit does not clear rows on matter-input edits or failed load, and has no response-generation guard. Account-directory failures likewise retain earlier rows/form values.|When these increments land, clear/invalidate old projections on scope changes/denials and suppress late responses. Label applied versus draft filters; disable actions until the relevant current row/revision is loaded.|
|Compact CSS sets 12 px table text and a 780 px table minimum; there is no dedicated `.table-scroll` rule. Mobile relies on a global `table { display:block; overflow-x:auto }` rule.|Give the wrapper a bounded horizontal scroll region and wrapping toolbar. Verify keyboard focus, zoom and narrow layouts; an installed Responsive extension must not be assumed.|

Keep a compact default: one search/page-size row, collapsed **Filters**, **Columns** and **Saved views**, a selected-count/action strip only where supported, and one pager/count basis. Show document/version and human names with IDs in secondary text. Use explicit **Open task**, **Review finding**, **Read evidence** actions, not an entire clickable row that also contains checkboxes. Optional timing/technical columns belong in the picker or detail pane.

## Acceptance and ownership handoff

- Backend tests first for each new dataset: filter/count/page/export after canonical current PDP and retained source union; allowlisted fields; stable tie-break ordering; fresh permission check before return; cross-matter, wall, expired clean-team and bank-release negatives. Admin configuration needs its own genuine Root permission path, not a source-policy exception.
- UI checks: delayed/reordered responses, non-JSON denial, filter/matter/session change during query/export, selection outside the current page, saved typed-filter visibility, stale saved hashes, busy action cells and empty/loading/error states. Preserve literal/React escaping for untrusted names and summaries.
- Signed-in workflow checks: a task row opens the existing reader/detail controls; a finding opens its exact source and revision; unsaved editor text survives unrelated paging; a permission loss clears protected detail. Verify keyboard and narrow-screen controls.
- Bulk work needs a dedicated bounded domain command with per-resource authorization, idempotency, expected revisions and safe partial-success counts. Do not expose bulk approve/publish/release or treat a UI selection as authority. Existing internal metadata export is not audience release.
- Root owns integration and the current Review Tasks frontend; backend agent owns its query contract/tests. Subsequent increments should name their component/service owners before shared wrapper edits. Keep existing inventory/finance behavior as regression baselines. No schema migration is justified merely to restyle/query existing rows.

Validation for this planning task was read-only source, installed package/license/typing and CSS inspection. No build, browser check, API test, dependency installation, live action or new approval was performed; UI behavior findings remain implementation/test targets.
