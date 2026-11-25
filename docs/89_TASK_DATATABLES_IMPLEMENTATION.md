# Tasks & assignments DataTable

24 November 2026. The user moved workflow-script walkthroughs to the final gate and prioritized the DataTables rollout. This increment adds a matter-wide task register to the Firm portal. It does not complete the remaining registers in [the rollout plan](88_DATATABLES_ROLLOUT_PLAN.md).

## Working scope

The Firm portal's **Tasks & assignments** page uses the official installed React DataTables wrapper, server paging (10/20/50), global and column searches, typed status/stage/own-work/historical filters, sorting, column visibility, cross-page selection and selected CSV/Excel metadata exports. Evidence opens the existing document reader. **Manage source work** selects the permitted source in the existing custodian/task workflow, retaining the task history, SLA, timing and individual actions.

Bulk reassignment accepts at most 25 distinct task IDs and their selected revisions. The picker returns only another person's eligibility intersection across every selected task and its retained history. Each command rechecks the creator/scoped Legal SME, current matter and source permissions, frozen state, revision and target. It reuses actual task events, notifications and timing-stop behavior. Responses disclose successful IDs and unavailable counts, with no failure identity/reason list. No task selection confirms findings, approves profiles or releases a report.

Unknown results retain the exact command and UUID for an explicit same-request retry while the workspace remains open. Malformed success receipts and unsuccessful retries retain that uncertainty. This browser recovery state is temporary, not a durable batch ledger. Successful rows retain replay keys in task events; an entirely unsuccessful attempt does not consume its UUID. Inspect source history before dismissing an unknown result.

## Authorization and storage

- A task and every retained event contribute source and retained-policy restrictions. Current source relaxation does not remove earlier restrictions.
- Current person names/IDs are projected only while that person remains eligible for the complete retained union. Unavailable people are not guessed or searchable by hidden identity.
- Query counts, filters, pages and exports are prepared from authorized records, then revalidated against all contributing task/event/source state before return.
- Historical mode includes tasks on superseded sources; it shows their latest retained task state and permits no reassignment of those historical tasks.
- The shared grid resets on matter/session/dataset changes, clears selection on filters and changed visible records, suppresses stale exports and handles non-JSON authorization failures. Its automatic refresh waits for an existing draw to finish.
- PostgreSQL bulk commands serialize per actor with a transaction advisory lock, then use the existing Matter/task lock order. SQLite fixtures establish an actual outer transaction before row savepoints so failed final authorization rolls back earlier prepared rows.

No schema migration is included; the application remains at **0038**. Task saved views deliberately remain unavailable: the current database constraints and retained-evidence models support inventory/financial configurations only. A future additive migration must model task history evidence rather than aliasing a task to inventory.

## Implementation locations

- [Task page](../frontend/src/ReviewTasksWorkspace.tsx), [shared grid](../frontend/src/KestrelDataTable.tsx), [source-work deep link](../frontend/src/SourceWorkPanel.tsx).
- [Task query/export/bulk service](../backend/kestrel/services/task_tables.py), [table routes](../backend/kestrel/api/data_tables.py), [strict payloads](../backend/kestrel/schemas/data_tables.py).
- [Task contract tests](../backend/tests/test_task_tables.py), [independent boundary tests](../backend/tests/test_task_data_tables.py).
- [Read-only live smoke check](../scripts/verify_task_tables.py). It uses normal synthetic sign-in, query/export requests and logout; no business decision, assignment change or provider call.

Start/Stop still manage the same real components. Their notices now identify task-grid access and retained assignment history; this feature adds no separate server or console. Existing documents, legal decisions, credentials and logs are retained. Rollback is a code revert and frontend rebuild/restart; no task/event data should be removed.

## Validation and limits

The TypeScript/Vite production build passes. Backend contract and independent SQLite checks pass; final PostgreSQL/browser results are recorded below when completed. The live database had 2 coordination tasks and 17 source versions before restart. This is a functional synthetic demonstration, not a measured 12,000-task performance result. Authorized task counts currently scan the matter's tasks and their bounded retained histories; database indexing/query optimization and workload benchmarks remain a separate scale gate.

The existing inventory and financial grids remain regression baselines. Findings/contracts, admin/audit and the secondary registers follow in separate increments. Manual workflow scripts and genuine SME acceptance remain the final gate; no independent legal approval is performed by the build agent.

Completed task-slice checks (overlapping suites; not one combined run):

- Independent boundary suite: 23/23 SQLite and 23/23 PostgreSQL; the final foreign-matter lock-order adjustment also passed its targeted SQLite case.
- Task contracts plus existing table/saved-view/source-work regression: 39/39 SQLite. PostgreSQL earlier combined run: 38/38, plus the later cross-matter UUID case 1/1.
- Task/reader-clock regression: 17/17 SQLite; actual reader-lease reassignment/stop case 1/1 PostgreSQL. No active time was fabricated.
- Controlled Start/Stop completed with all five components healthy and the database still at 0038. Read-only authenticated live queries, empty search, typed stage filter and Root/bank denial passed.
- Live CSV/XLSX responses correctly included zero of the selected unconfirmed demo task's rows and reported one unavailable. Positive confirmed-source exports and spreadsheet formula safety passed in disposable automated fixtures. The build did not confirm the live source to manufacture an export result.
- Signed-in browser checks: two task rows, eligible-person intersection, filter reducing two rows to one, selection reset, source reader and correctly selected source-work deep link. Existing inventory search reduced nine rows to one. Financial table rendered its truthful empty state without console errors. No live reassignment or legal decision was made during these checks.

Read-only live evidence: `.runtime/task-tables-live-verification.json`. The task-grid preview is retained under `delivery/frontend_preview/` after the final layout build.

Narrow-screen verification at 640 px found and corrected the pre-existing full-height sidebar pushing content below the first screen. The menu now starts collapsed on small screens, expands into a bounded navigation strip, and the workspace remains directly below it. The task table scrolls horizontally within its own region; the matter selector uses the full available width. Desktop and narrow previews are `task-datatables.jpg` and `task-datatables-narrow.jpg`.
