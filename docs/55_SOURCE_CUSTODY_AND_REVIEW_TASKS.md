# Gate 1: source custody and parallel review tasks

23 November 2026. Local synthetic prototype increment. Alembic head `0027`. This completes the custody/parallel-task foundation; clocks, SLA calendars and the remainder of Gate 1 are still pending.

## Working behavior

Firm **Documents → Custodians & review assignments** now lets an authorized lawyer choose an exact source version and:

- Record multiple origin custodians: people, shared mailboxes, departments or systems. Each has provenance and optional known effective dates. A custodian can be linked to multiple source versions using its stable ID, provided both the original record and new source are permitted. No reviewer is inferred to be a custodian.
- Record contracting parties separately from source custody. These records capture manually entered assertions/provenance; they do not constitute a finding or legal approval.
- Create parallel document-review, QC, specialist-legal, financial-review and AI-coordination tasks. Assignees are existing firm account IDs with current matter membership, eligible legal roles, no wall and the required source/clean-team access. Assigning a task never grants a role or source entitlement.
- Accept, start, pause, resume and complete the assignee's own coordination task. The task creator or a scoped Legal SME can reassign, cancel, reopen or change a deadline. The server validates state/revision and records rationale. Each stage/task remains independent.
- Open the existing evidence popup. For an assignee, an explicit opening event is recorded automatically; opening requires no invented explanation and does not count as active work.
- Inspect immutable task history and own permitted in-app notifications. Marking a notification read creates a retained receipt, not a task decision. Notifications are neither email delivery nor legal publication.

Task completion does **not** confirm a finding, sign off whole-document legal review, authorize AI, approve reanalysis or release anything externally. Those existing workflows remain separate. An AI-coordination task does not run an agent or enqueue a paid call.

## Data and authorization

Eight additive tables: `record_custodians`, `document_custodians`, `custodian_link_retirements`, `document_parties`, `review_tasks`, `review_task_events`, `review_task_notifications`, `review_notification_reads`. Relevant source/inbox and uniqueness indexes support lookups, request idempotency, revision serialization and duplicate receipt prevention. Existing sources, findings, approvals, account associations, versions and VDR mappings were not rewritten.

Task identity and every state change are append-only. Custody link retirement appends a separate record; it does not delete the prior attribution. Party assertions are append-only in this increment. Correcting/superseding party assertions is not yet a separate workflow; do not use direct SQL updates.

Every implemented endpoint uses normal authenticated sessions and the canonical policy service. Root Admin alone and external users cannot access internal source work. Target-user eligibility is checked before assignment/reassignment; an account ID or task assignment cannot bypass a wall. Reads and notification queries recheck current permissions, including revoked grants and superseded versions.

Source-bound records retain the classification/clean-team scope from creation. Current source authority **AND** those retained restrictions are evaluated through the canonical PDP (`require_retained`). A source relaxation does not declassify its older task history, custody record or notification. Linking a custodian also requires access to its original source and retained restrictions. Lists return only permitted rows and make no completeness assertion about hidden work.

Clean-team audit events resolve task/custody records back to their sources and retained restriction unions. Audit rows contain actions/IDs, not document passages, UPN lists or task rationale. Rationale and provenance live in the restricted business records. All logs/records remain retained; no deletion schedule was introduced.

Future signing snapshots use `kestrel-signing-manifest-4`, including custody, parties, tasks, events and persisted notifications. Historical signing payloads remain unchanged. Frozen matters block new source-work content and decisions. Own notification read receipts remain operational after freeze and are excluded from signed business-content hashes.

## Timestamps and honest limits

The server records UTC event times for assignment, reassignment, acceptance, opening, start, pause, resume, completion, cancellation, reopening and deadline changes. Initial notification time means persisted in-app notification creation, not external delivery. A timeline can be examined without fabricating a prior human review date.

Queue age is elapsed server time within the latest assignment cycle, ending at completion/cancellation where applicable. Active seconds, idle seconds and business-day calculations are explicitly **unmeasured/null**. Browser-open time is not treated as productive work. No heartbeat, session-duration claim, holiday calendar, five-day SLA or escalation threshold was silently assumed.

Current local bounds: up to 100 visible records per source panel, up to 500 events per task, a bounded own notification query and first 30 notifications in the UI. DataTables/server paging remains a later gate. Existing VDR Assigned Reviewer, Date Assigned/Reviewed, QC and Days Open values remain retained proposals; this migration neither converts names into grants nor invents workflow timestamps. A reviewed finding owner is not an assignment backfill source.

## Try the walkthrough

1. Run `START_KESTREL.bat`; sign in to the Firm portal as `lawyer01@freshfields.example`.
2. Select matter `012345-789012`, open **Documents**, then choose `REVIEW-WORK-LAB-001 · v1 · coordination-contract.txt` in **Document version**.
3. Inspect two custodians and two separately recorded instrument parties. The underlying text explicitly identifies these fictional entities/inventory entries.
4. The lawyer's review task and `sme01@freshfields.example` QC task run independently. Enter a reason before state changes. Inspect **History, reassignment and deadline** for actor IDs, assignee UPNs and UTC events.
5. **View evidence & record opening** launches the existing authenticated reader. In the browser verification the lawyer accepted the review task and opened its source; QC remained assigned. No finding, classification or release was approved.
6. Use **Your review notifications** and **Mark read** to inspect own permitted receipts. Use **Resources** for the role-specific guide and [Workflow Swagger](https://firm.localhost:8443/docs/review-work) for the ten operations.

`scripts/seed_review_work_demo.py` uses normal HTTPS test-account sign-ins and stable request keys. It creates one clearly synthetic source, two custodians, two contracting parties and two assignments once. Repeating it preserves later task decisions rather than resetting them. No account, wall, approval or provider configuration is changed. Source fixture: `synthetic/review-work-demo/coordination-contract.txt`; live IDs are in `.runtime/review-work-demo.json`. These test records are separate from older matter content.

## Verification and preservation

- Full backend suite: **235 passed, 1 skipped, 1 warning**, 318.81 seconds. Warning is the existing Starlette/httpx test-client deprecation.
- Earlier targeted matrix: **30 passed**. Final new workflow/migration/audit subset: **18 passed**. Isolated PostgreSQL workflow tests: **9 passed**.
- Tests cover independent stage histories, request replay, stale revision rejection, illegal/forged events, current assignee versus manager actions, walled/bank/admin recipients, immutable rows, clean-team audit resolution, classification relaxation, restricted inboxes, changing signing snapshots and post-freeze receipt acknowledgment.
- Frontend TypeScript/Vite build passed. Browser checks exercised the real lawyer session, two-source-custodian/two-party display, independent acceptance, unchanged QC task, evidence popup and retained opening history. Screenshot: `outputs/review-workflow.jpg`.
- Encrypted backup restore verified **70 pre-migration tables / 14,274 rows**, including schema/constraints and content digests. Rehearsal applied migration twice to a restored copy and replayed the existing identity backfill twice.
- Rehearsal and live migration each preserved **all 69 existing application-table digests**, 16 source versions, 15 logical documents and 16 links, with zero identity projection orphans. The walkthrough source was added afterward as an explicit synthetic fixture.
- The migration file hash is pinned in the rehearsal receipt and checked before live application. Migration `0027` adds eight tables and does not drop or alter older ones. Populated downgrade refuses to discard retained work; rollback means disable the new UI/routes and preserve data or apply a forward repair. There is no automatic destructive downgrade/restore.
- Owned services were restarted. Start/Stop BAT descriptions, Resources and Portal Home Swagger grouping were updated. The shared API serves `/api/v1/review-work`; no additional server, worker, login scheme or public deployment was introduced. No paid AI call or legal approval was performed.

Evidence: `.runtime/prompt-audit/review-work-*`, `scripts/verify_document_identity_migration.py --target 0027`, and `backend/tests/test_review_work.py`.

## Next increment

Continue Gate 1 with explicit reader/active/idle/pause sessions, bounded idempotent activity receipts, versioned time-zone/holiday/business-hour SLA calendars, honest queue/acceptance/turnaround measures and scoped escalation. Then finish normalized checklist/request/coverage and governed import proposals before Gate 2 segment ABAC/redaction. The assumed five-day demo threshold, idle timeout and offline-review treatment remain configurable/open decisions, not measured historical facts.

React DataTables remains planned for Gate 4, including server-side paging/filtering, per-row bulk authorization and permitted exports. Reader popup and charts are preserved.
