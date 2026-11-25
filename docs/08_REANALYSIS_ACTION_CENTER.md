# 08 — Playbook version diff, impact analysis, notifications and SME-approved reanalysis

## Preconditions / event chain
1. Root Admin / knowledge editor authors *new draft*; tests and submits to an independent legal SME.
2. SME reviews and approves that **specific immutable version hash**; authorized publisher publishes.
3. A material change publication creates `playbook.version.published` and `impact.assessment.requested` outbox events. Impact engine computes affected **document-version** set based on playbook applicability, rule changes and prior analysis lineage, including approved findings and released artifacts. Produces immutable snapshot with hash and as-of timestamp.
4. System creates `governance_task` for assigned SME(s) and corresponding `notification` in user's account, with no sensitive passages in email/notifications. Critical released impacts also create independent urgent counsel task; optional email is secondary.
5. Assigned SME opens task and sees **exact before/after rule-field diff**, number and list of affected docs they are authorized to see, approved and released finding counts and restricted-subset aggregate where not cleared. System always re-evaluates access before showing underlying rows.
6. SME selects permitted scope, records mandatory nonempty rationale, approves or rejects. Backend re-derives actor from authenticated session; denies self-approval, missing matter grant, wall, clean-team mismatch, stale impact hash, old version or inconsistent scope. Rejection records rationale; no job.
7. On approval server atomically records decision, immutable audit and idempotent queue event. Worker obtains scoped data access (not a general admin identity), reruns only approved doc versions under approved target playbook and model config.
8. New findings are **candidates** linked to old runs. `finding_reconciliation` compares old approved/released result vs new candidate; attorneys validate; any release/correction remains separate and gated, with antitrust review for restricted content when required.
9. Task closes only after review disposition and required correction/workflow steps or an authorized justified closure. Notification can be read or acknowledged earlier without silently resolving task.

## Data/authorization rules
- Hash impact snapshot of sorted document version IDs, affected finding IDs, prior release IDs, target playbook version hash and diff hash. Recompute in transaction; stale -> HTTP 409 and new assessment.
- No requester-supplied `actor_id`, `role` or arbitrary `document_ids` can bypass scope; server enforces independent actor and authorization.
- Separate clean-team work queue; unauthorized SME sees safe aggregated info but no restricted passage/metadata; cannot approve restricted rerun without explicit role and membership.
- At-least-once queues require durable dedupe by `(impact_hash, target_version, approved_scope_hash, job_kind)` and per-item processing key.
- Release changes require review of already-delivered content (cannot undo downloaded docs), not just recomputing model output.

## Task/notification states
Task `open -> claimed -> awaiting_decision -> approved|rejected -> in_progress -> pending_attorney_review -> closed`; independent `escalated`, `superseded`, `failed` transitions with authorized rationale.
Notification `unread -> read -> acknowledged -> resolved`. **Read ≠ approved** and `acknowledged ≠ decision`; pending tasks stay visible in outstanding work and bell badge. Configurable deadlines/escalation by priority and information classification.

## Minimum tests
- Approved material change creates one impact snapshot and one SME notification (per scoped recipient), no automatic rerun.
- Only assigned eligible SME can approve with rationale; self-author cannot, Root Admin cannot, walled user cannot, external users cannot.
- Duplicate submit with same idempotency key creates one job; stale hash 409; scope tamper 403.
- Exact diff includes added/removed/modified rules; counts match seeded backing data and no leakage to unauthorized viewer.
- Newly processed results do not replace approved or released history, no automatic external republish.
- Clean-team impact has restricted subtask and appropriate approver; privileged content never in unauthorized notification.
- Rejected decision emits audit event and no queue item; can create revised scope via fresh assessment only.
