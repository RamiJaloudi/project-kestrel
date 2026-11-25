# Gate 1: opt-in reader timing and approved operational SLA

23 November 2026, America/New_York. Local prototype increment, Alembic `0028`. Existing document, custody, task, legal-review and release workflows are preserved.

## What works

- An assignee starts their coordination task, opens its exact evidence source and explicitly enables interaction timing. Opening a tab or starting a task alone does not create productive-time credit.
- The reader sends a bounded observation every 15 seconds. Only server timestamps are used. A gesture-supported interval can contribute active **estimates** only when its server gap is at most 30 seconds. Duplicate request keys/sequence checks prevent duplicate interval credit. A backwards server clock is rejected.
- A visible session without recorded interaction remains unobserved initially, then contributes idle observations after its pinned threshold. The demo default is five minutes; approved SLA versions can specify 1–15 minutes for newly started sessions. Quiet reading may be unobserved or classified as no-interaction idle; these are not verified human-work, productivity or billing records.
- The browser records only a boolean interaction flag for trusted pointer-down, keyboard or wheel events. It sends no key contents, mouse coordinates, source passages, client timestamps or claimed elapsed seconds. Native PDF plugin interactions may not reach the parent reader; missing input is not fabricated.
- Hiding/unfocusing the reader, closing it, stopping timing, pausing/completing/cancelling/reassigning the task, expired authority or a connection problem stops observation or invalidates its lease. No missing interval is credited as active. Technical leases expire after 90 seconds and permit one active observation session per account across tasks/tabs.
- Readable measures include latest assignment age, time to accept, completed turnaround, observed interaction/idle seconds, unobserved session time and, when explicitly configured, business-day SLA time. Missing observations remain unknown/null; restricted measures are not exposed to ordinary coworkers.
- Current source/matter/wall and retained task/receipt restrictions are checked on clock operations. A later source relaxation does not declassify previously restricted timing receipts. Precise timing is available to the assignee or an appropriately scoped designated matter auditor with source access; Root Admin alone cannot read task-specific activity.

## Operational SLA governance

Admins and Legal SMEs can open **Administration → Review SLA**. SMEs also have a configuration disclosure in **Firm → Documents → Custodians & review assignments**.

1. Create an immutable calendar version: IANA timezone, explicit weekdays, local business hours and explicit holiday dates. No national holidays are inferred. Overnight schedules are outside this increment.
2. Create a draft policy for a review stage, exact calendar version, business-hour budget, pause exclusion and idle threshold.
3. Submit the draft. A different scoped Legal SME approves or rejects its exact revision/hash. Publish the approved version. Drafting, independent approval and publication are retained as separate decisions.
4. A task creator or scoped SME explicitly attaches a published same-matter/stage version to the current assignment with a reason. The budget starts at that binding, not retroactively at an old assignment. Reassignment/reopening creates a new cycle requiring a new explicit binding. Publishing a replacement never rewrites old bindings.

Business-time calculations handle configured weekends/holidays and timezone offsets, including daylight-saving transitions. Calendars pin the installed `tzdata` package version (`2026.6` in this build); a changed timezone dataset requires a new calendar/version rather than silent retrospective recalculation. Repeated local hours use the first occurrence (`fold=0`); nonexistent boundary times fail calculation rather than invent hours. Calculations/projected deadlines are bounded to a one-year interval. Out-of-bound or unsupported calculations show `calculation_unavailable`; retained task history stays readable.

Explicitly paused business time is excluded only when the pinned policy says so. Manual task deadlines remain separate. Projected SLA due dates assume no future pauses and are unavailable while the task is paused. These are coordination budgets, not substantive legal obligations or legal-risk scores. Automated SLA escalation/alert delivery is not yet implemented.

The suggested London Monday–Friday 09:00–17:00, five-business-day budget is an **unsubmitted draft only**, with no holidays entered. No independent approval, publication or task binding was performed by this build. The calendar/budget and five-minute idle question remain configurable preferences; no answer was treated as approval. The prepared draft can be inspected using the existing admin/SME accounts and changed by creating another version.

## Try the reader

1. Sign in as `lawyer01@freshfields.example`, open **Firm → Documents**, and select `REVIEW-WORK-LAB-001` in **Custodians & review assignments**.
2. Enter a reason and resume/start the assigned review task. The synthetic task was paused at the end of verification; the parallel SME QC task remains independent.
3. Use **View evidence & record opening**. Click **Enable interaction timing** in the popup. The reader must be visible and focused.
4. Use the source normally. Observe interaction estimates, idle observations and unobserved time separately. Stop timing before closing or signing. A loss of connectivity stops local observation; an uncertain server lease expires within 90 seconds.
5. Refresh source work and expand task history for the scoped timing measures. SLA remains **unconfigured** until an exact published policy is explicitly attached.

Swagger: [Timing and operational SLA](https://firm.localhost:8443/docs/review-clocks), eight operations. The shared API serves `/api/v1/review-clocks`; no new backend process or public endpoint exposure was introduced. Start/Stop descriptions, Portal Home Swagger grouping and role-specific Resources were updated.

## Storage, signing and preservation

Seven additive tables: `sla_calendars`, `review_sla_policies`, `review_sla_decisions`, `review_sla_bindings`, `review_sessions`, `review_session_receipts`, `review_session_leases`. All configuration, bindings, session roots and receipts have immutable SQL guards. The account-unique mutable lease is only an operational pointer; it is not the retained evidence or a signing artifact. Its expiry/deactivation never deletes receipts.

Future signing manifests use schema `kestrel-signing-manifest-5` and include the retained clock/configuration/binding records plus an explicit timing cutoff. Signing is blocked while an unexpired observation lease exists. Subsequent receipt changes invalidate the proposed snapshot. Frozen metrics use the retained snapshot cutoff rather than continuing to accrue. Legacy frozen workspaces use a recorded legacy proposal timestamp when available; where no cutoff exists, timing is unavailable. Historical signing payloads remain unchanged.

No existing sources, versions, findings, approvals, accounts, custody events or task history were rewritten. No source text or typed key contents enter runtime diagnostics. Timing/audit records are retained without automatic deletion. Shared run/month AI spending limits and provider credentials were not changed; this increment made no paid calls.

## Verification

- Full regression run: **242 passed, 1 skipped**, 287.89 seconds. This run preceded the final bounded-SLA fallback and two additional timing cases; the final scoped recheck below covers those changes. Counts are overlapping, not additive unique totals.
- Main targeted migration/lifecycle/checklist/workflow matrix: **32 passed**. Final timing recheck: **9 passed**, including retained receipt restrictions and frozen cutoff stability. Final PostgreSQL isolated-schema pass before the last receipt-specific test: **8 passed**.
- Tests cover duplicate receipts, stale sequence, concurrent account leases, gap bounds, idle threshold, pause invalidation, walls, private precise metrics, exact policy approval, self-approval denial, explicit binding, pause exclusion, new assignment reset, weekends/holidays/DST, immutable rows, signing closure/cutoff and long-term readability.
- Frontend TypeScript/Vite production build passed. Live browser verification used normal sign-in, started the synthetic task, opened its existing reader, explicitly enabled timing, performed a source search, observed a 15-second interaction estimate and separately unobserved time, then explicitly stopped timing. The screenshot is `outputs/review-reader-timing.jpg`. These are synthetic UI observations, not legal review or verified employee productivity.
- Encrypted backup restored and verified **78 pre-migration tables / 14,437 rows**, with schema/constraint and data hashes. Migration rehearsal and live application each preserved **all 77 existing application-table digests**, 17 source versions, 16 logical documents and 17 version links, with zero identity projection orphans. Upgrade and the existing identity backfill were replayed safely on the restored copy.
- Migration SHA-256 was pinned in the rehearsal receipt and verified before live application. Populated downgrade refuses to discard retained clock/SLA evidence. Rollback preserves old paths and data or uses a forward repair; no destructive restore over the active database was performed.

Evidence: `.runtime/prompt-audit/review-clocks-*`; `scripts/prepare_review_clocks_demo.py` prepares drafts only; `scripts/verify_review_clocks_live.py --pause-demo-task` verifies the synthetic walkthrough and pauses its coordination task without a legal decision. `scripts/verify_document_identity_migration.py --target 0028` supports isolated rehearsal and explicit application.

## Remaining Gate 1 work

Finish normalized checklist/request/coverage projections and governed application of legacy tracker assignment/QC inputs without inventing historical timestamps. Add scoped, deduplicated SLA escalation and durable alert disposition before claiming automated review monitoring. Offline review time remains unmeasured, not backfilled from browser-open or imported dates.

Then continue Gate 2 segment attributes, redaction validation and derivative release. React DataTables remains at Gate 4 with server-side paging/authorization; the existing reader and charts remain preserved.
