# Legal SME Action Center

[USER DECISION] Implement the next sprint: persistent SME tasks, playbook comparisons, automatic impact assessment, explicit rerun approvals and comparison against preserved historical findings.

## Delivered workflow

1. In **Playbook Management**, load versions and choose **Create replacement draft** on a published legal playbook. This binds an explicit base ID, independent of names. Edit, test, submit, independently approve and publish the exact hash. The base must still be the current published predecessor. An unchanged replacement cannot publish. A separate playbook may be created without a base; it does not implicitly supersede an existing family. A matching published name requires an explicit base.
2. Publication transactionally stores a unique durable assessment event. The existing PostgreSQL worker processes it before analysis jobs. It walks explicit ancestors and selects the nearest successful prior run for each document version. All definition changes, including test-case-only changes, conservatively request assessment. Rule diffs use stable rule IDs and exact field paths with before/after values.
3. Each source version receives its own immutable impact snapshot and persistent task. The fingerprint binds target/hash, immutable source hashes, original analysis, finding/review/revision states and affected release snapshots. One-document tasks are the approval scope; arbitrary document ID lists are rejected. Active, assigned, unwalled Legal SMEs with source access become recipients, excluding the target author. Clean-team source policy is checked centrally, not inferred from a broad role.
4. In **Action Center**, inspect the document, exact diff, reviewed-finding counts and permitted released-package counts. Lists omit evidence; opening a task loads the permission-checked comparisons and records access. Source passages open the existing PDF/Word/text/Excel reader. Reassess stale undecided snapshots; the previous task is retained as superseded. Newly eligible independent SMEs may enroll through reassessment without gaining any new source permissions.
5. Claim the task. The claimant may return an undecided task with a rationale. Another assigned SME may recover an overdue or no-longer-eligible claim with a rationale; an active, eligible, unexpired claim cannot be taken over. These allocation decisions are retained. A claim starts no analysis.
6. Approve or reject with a nonempty rationale, exact snapshot and idempotency key. Authors and Root Admin without an explicit eligible SME role cannot approve. Snapshot changes return 409; authorization changes deny access. A processing restriction can prevent approval while still allowing a cleared SME to reject a reassessed request. Approval atomically records the immutable decision and creates one bound job. Exact retries return that job; altered retries conflict.
7. The worker rechecks the approval, snapshot, current target, account, matter/walls, clean-team scope, OCR verification and processing policy before execution and before saving findings. The ordinary first-analysis API remains restricted to one initial job per source. Only the approved impact path creates an additional run. OpenAI reruns retain the existing USD 2/run and USD 10/month controls; startup, impact calculation and notification delivery make no paid AI call.
8. Successful reruns produce new candidate findings and immutable comparisons: added, changed, unchanged or not redetected. A missing match does not remove or reject a historical legal finding. Old reviewed findings and packages are not overwritten, revoked or republished by reanalysis.
9. Lawyers confirm/correct/reject every new candidate and record comparison dispositions. Task closure is blocked until every comparison is disposed and every new candidate has a lawyer decision. Affected releases require a recorded separate release-handling action or justified decision to retain the prior package. This narrative is not an audience approval: new publication/revocation uses the existing independently gated Release Desk. Closure rationale and follow-up are retained and shown on the task.

## Notifications, deadlines and recovery

Notifications are distinct persistent rows, restricted to their recipient and current source access. Read, acknowledge and resolve are separate actions. Reading or acknowledgement never approves, rejects or closes a task. A notification cannot resolve while its task remains outstanding. The profile menu shows an unread count and links to the Action Center; it refreshes on focus and the existing visible-page polling cycle.

Initial deadlines are local-demo defaults: 24 hours for released impacts and 72 hours otherwise. An overdue active task receives one retained escalation, critical priority and new unread alerts. The worker rechecks recipient clearance; clean-team escalation may also notify cleared antitrust counsel. Escalation never reruns or closes work. Root cannot use monitoring as a wall/source override. Email delivery, business calendars, configurable escalation schedules and a separate counsel-case system are outside this local increment.

Failed assessment events are visible to scoped SMEs in the processing section and have an explicit manual retry. They never restart automatically. A failed analysis retains the existing job recovery controls and still rechecks its impact approval; live AI requests are never automatically resent. Denied/terminal jobs cannot be edited into successes. A replaced target requires its current successor's assessment.

## Retention and signing

Migration 0022 adds the outbox, immutable impacts/decisions/comparisons/closures and persistent tasks/notifications. PostgreSQL and isolated SQLite have retention triggers. Existing jobs keep their first-analysis uniqueness through a partial index; each impact task may have only one job. The migration preserves published-version and job retention triggers. These database controls are not WORM against a database owner.

Signing checks for pending impact calculation and includes impact snapshots, tasks, decisions, comparisons and closures in the record manifest. Signing freeze blocks task/content changes and automatic escalation of that matter. Notification reading remains possible. Source/finding/task access continues through the shared policy engine and scoped audit categories, including clean-team logging. No log or governance history is automatically deleted.

Start/Stop retain the five real components. The worker console identifies impact assessment and document analysis. The new Swagger group is `/docs/action-center`. Resources includes a downloadable role-specific guide. Start loads the isolated lab once and preserves subsequent user decisions and customized passwords.

## Isolated walkthrough

The lab is **054322-100001**, separate from the principal matter **012345-789012** and the ethical-wall lab. Source files are under `C:\Freshfields-Takehome\Synthetic_Data\Action_Center_Lab`. Main matter coverage, existing approvals and unprocessed Wave 2 files remain unchanged.

Sign in as `sme01@freshfields.example` or the named Chris account and open the Firm Action Center. Lab A has a historical approved Halden package and an urgent open task. Lab B is an ordinary task. The explicit `scripts/verify_action_center_lab.py` smoke test approves, processes, reviews and closes B through genuine HTTPS APIs while leaving A open for the tester. It makes no paid AI calls. A one-time marker prevents scripted approval replay. Scripted accounts sharing a demo password illustrate application role separation, not independent real-world human or legal approval.

## Acceptance and rollback

Tests cover explicit base lineage, exact field changes, no publication-triggered rerun, notification/task separation, snapshot staleness/reassessment, self-author denial, admin denial, clean-team membership changes, wall changes after approval, worker rechecks, idempotency, immutable history, lawyer review/disposition/closure, release follow-up, rejected requests, processing restrictions and escalation deduplication. SQLite and isolated PostgreSQL runs plus TypeScript/Vite and a real HTTPS-to-worker walkthrough are required.

Before migration, retain an encrypted restore-verified database backup. Rollback may stop owned services and restore application files while retaining additive schema/history. The migration refuses a destructive downgrade once tasks exist. Do not restore old credentials or silently replace the live database. External immutable storage, legal quality evaluation and public deployment remain separate gates.


## Verification recorded 21 November 2026

- Full backend regression run: 184 passed, 1 skipped. Additional abandoned-claim, signing and zero-redetection checks passed after the run was collected.
- Final isolated PostgreSQL Action Center/lifecycle run: 13 passed. Earlier PostgreSQL Action Center/queue/lifecycle run: 17 passed.
- TypeScript/Vite build passed through the normal launcher.
- Migration 0022 applied; live Alembic metadata check reported no new upgrade operations.
- Pre-migration encrypted restore verification: 49 tables, 2,812 rows. Post-migration verification: 57 tables, 3,222 rows; row and schema digests matched in an isolated restored database. Backups retained.
- Live HTTPS-to-worker lab B passed approval, offline analysis, source-bound candidate creation, lawyer review, reconciliation and closure. Lab A remains open/urgent; the original released package remains approved. No paid AI call was made.
- Main matter counts matched the pre-migration record: 10 source versions, 20 source findings, 7 audience packages, zero imported Wave 2 sources. No existing main-matter approval was changed.
- In-app browser verification passed: real SME login, task inbox, exact rule diff, current UPN/employee ID/profile details, notification link and original source reader. Preview saved as `outputs/action-center-preview.jpg`; the marked browser tab remains open as the synthetic SME tester. This browser route worked despite earlier native-desktop inventory failures.
- All five owned services restarted; HTTPS readiness passed; pgAdmin and owned psql reopened. Existing accounts/passwords and unprocessed Wave 2 files were retained.
