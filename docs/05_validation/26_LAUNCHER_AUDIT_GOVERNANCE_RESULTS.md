# Launcher, audit and governance increment — implementation evidence

## Running surfaces

Launch with START_KESTREL.bat at workspace root. It starts the dedicated local PostgreSQL cluster, compiles the React app, and starts HTTP preview and HTTPS API backends in explicitly shown CMD consoles. Windows may host these in Windows Terminal according to your terminal settings. STOP_KESTREL.bat terminates only the recorded project supervisor/process tree and project PostgreSQL. STATUS remains available in the handoff root. No DNS/public exposure or persistent execution-policy change.

The supervisor remains hidden; the two backend consoles are shown. Their CMD prompts remain available after a backend exit for inspection. A failed/closed backend is not automatically restarted. Health watchdog events record transition to unresponsive after three failed checks, nominally around 30 seconds plus probe durations. A health failure is evidence of unresponsiveness, not proof of deadlock/root cause. No automatic thread dump or process kill is performed for watchdog failures.

Startup transcripts, compiler output and technical JSONL events are under `.runtime/logs`. Build output has its own unique file; a long build emits periodic still-running events with manual recovery only. Compiler output is development evidence, not a user-facing audit feed. Technical exceptions retain type and file/function/line frames plus correlation ID, never message/locals/request body. Uvicorn access logging is disabled by the runner to avoid arbitrary query/header content. Readiness checks query the DB. No files or audit rows are automatically deleted.

## Audit exports

UI: admin site's Audit reports, or Firm/Client/Bank Audit navigation. Swagger: `/docs/audit`. `/api/v1/audit/events` and `/api/v1/audit/export` require real session authentication. Categories: administrative, legal_sme, clean_team, access. Own permitted activity is default; wider scope requires explicit roles. Current matter/wall state and CT membership are rechecked. CT derived artifacts also recheck lineage scopes. Historical logs with insufficient partition metadata are not retroactively classified as certified complete CT records.

Exports contain events.jsonl / events.csv / events.html plus manifest.json in ZIP. Same server policy and filters apply to all formats; CSV formula-injection and HTML escaping protections included. Manifest records event IDs, filters, exporting identity/time, format/schema and SHA256 of data bytes. Maximum 1000 selected events; larger exports return a narrow-filter error rather than silently truncating. Date-range/pagination support remains follow-on work for larger timelines. Technical raw log files are not exposed by these audit APIs.

Audit UPDATE/DELETE is blocked by database triggers; published governance rows are guarded against UPDATE/DELETE. Database owner/migration privileges can still bypass/drop these controls: this is NOT immutable/WORM archival storage or legal certification. Immutable-storage adapter, separate restricted incident-evidence capture, and PDF reports are next phase as requested.

## Policy and playbook editor

Admin has Policies & playbooks; Firm has Playbook Management. Swagger: `/docs/policy-editor`. Create own draft, edit, run legal synthetic tests, submit, independent approve/reject with rationale, publish exact approved hash. Drafts may be duplicated through creating a new draft from their definition; direct editing another author's draft is denied. Optimistic revisions reject stale decisions. Published rows cannot be edited/deleted. Separate grant roles: legal_sme, security_approver, conflicts_approver; matter_auditor and clean_team_auditor for wider audit. Trusted local bootstrap can provision roles; normal portal users cannot grant themselves roles.

Environment definitions use explicit booleans (block_ai/block_cloud/block_external) and approved regions. Independently published restrictions now affect client/matter environment decisions. Multiple published policies combine restrictively; replacement/relaxation/supersession governance is not implemented, so the UI does not promise arbitrary permissive overrides. Wall policy definitions add denies only; publication affects session/principal checks on the next request. Legacy direct wall changes in registry API are now disabled to prevent an approval bypass. Existing registry walls remain effective and may be shown alongside effective policy denies.

Legal baseline: structured rules, separate language/governing-law dimensions, literal triggers, synthetic cases, authority references and draft disclaimer. Exact source offsets/quotes in synthetic test cases are verified by the deterministic matcher. Positive and negative cases must pass for the exact hash before independent SME approval. No model-generated legal conclusion or production recall claim. Publication does not initiate a rerun or release; full diff/impact/inbox/rerun authorization remains a later required workflow.

Starter: data/playbooks/PB-STARTER-GOVERNED-DRAFT.json and matching editor template. Includes synthetic EN/DE CoC/assignment examples. BGB section 398 official text was consulted at https://www.gesetze-im-internet.de/bgb/__398.html on 2026-11-20. It is a receivables-assignment reference, not a universal control-change rule. Official section pointers for BGB 399/GmbHG 15 were found but full-text requests timed out; fixtures explicitly mark verification pending. No automatic jurisdiction applicability or claim of complete research. No startup publication or default approver identity.

## Resources and engine status

Resources exists in each organization portal and admin. Authenticated API `/api/v1/resources` and same-policy guide downloads return role-specific guides. CT material is absent without a current named scope; privileged source examples are not embedded. `/api/v1/resources/engines` reports implemented vs synthetic baseline vs next-phase/planned engines. Anonymous preview loads no restricted guides. No source-document content is present in guide files.

## Verification and limitations

Current code was exercised with the full isolated suite, native PostgreSQL control tests, SQL schema drift check and production frontend build (exact final counts recorded below). Browser verified admin Policy editor, Audit reports and Resources previews. Actual HTTPS browser user login/export was not performed; certificate warnings were not bypassed. Authenticated API paths were verified using TestClient, including live PostgreSQL schemas.

Windows process inspection reported a WindowsTerminal main title for the Kestrel HTTP backend after explicit show-window flags were added. UI automation inventory did not expose the terminal window; its contents were not visually inspected. Both backend health probes reported healthy. Startup/stop/restart and retained startup/build/watchdog files were verified. A Windows cp1252 compiler-output capture error was corrected by using UTF-8 and failing on capture-thread errors; the retained-output build passed afterward.

OpenAI API integration is selected for next phase but NOT configured or called. No API key requested in chat. No cloud spending, live firm integration, full OCR/batch processing, complete tracker/report generation, or public deployment. Composite client-number/matter-number business identifier correction remains in the required backlog. No claim that the whole application is finished.

## Final verification results

- Full isolated suite: `backend\.venv\Scripts\python.exe -m pytest -q --tb=short` → **82 passed, 1 warning in 31.65s**.
- Live PostgreSQL control suite: `KESTREL_TEST_POSTGRES=1`, `pytest tests/test_observability_governance.py` → **6 passed, 1 warning in 7.78s**. Test schemas were isolated and dropped; project records were not used as fixtures.
- PostgreSQL Alembic migration 0004 + schema drift check passed. Local data retained.
- TypeScript/Vite production build through retained-output wrapper passed; Python compile check passed.
- Final start/stop/restart using the current batch target passed. Both local listeners ready; watchdog recorded healthy transitions. No automatic restart or log cleanup.
- One intermediate PostgreSQL test setup overlapped an intentional database restart and failed with database-starting-up; the six-test suite was rerun after startup and passed. No application defect was concealed by a retry policy.

Direct registry wall writes now reject changes to the wall flag. New denials must use the independently approved Conflicts policy flow; effective policy blocks are shown in registry access results. Governed relaxation/removal of published restrictions remains follow-on work, with no permissive fallback.
