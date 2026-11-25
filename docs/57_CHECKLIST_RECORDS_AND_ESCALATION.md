# Gate 1 — Checklist records and scoped SLA escalation

[DEMO] Local increment, 23 November 2026. No paid AI calls, external notifications, legal publication or public deployment were performed.

## Working paths

- Firm → DD Checklist: original A–N request drafting in new immutable scope versions; independent scope approval remains mandatory. Request-specific evidence types now drive the source picker. PARTIAL requires source evidence and a missing-information explanation. Waivers and N/A are distinct requests requiring a different Legal SME.
- Published request → Request log & recorded coverage history: append request, follow-up, reference or note with due date, wave, workstream and jurisdiction. Source-linked entries use current and retained source restrictions; unlinked notes are author-only. A history entry does not change coverage or create a finding. An item-wide revision conflict requires refresh; hidden private entries can prevent another author from appending until coordinated with the author.
- Firm → Reports & Board Pack → Internal checklist coverage: new reports capture exact contributing coverage event IDs. Editing the report copies those exact references; changing coverage afterward does not rewrite earlier reports. Legacy reports have no fabricated backfill. Internal metadata is excluded from external report body/export text.
- Firm → Documents → select document → task → Scoped escalation plans: explicitly bind an independently approved published SLA first. A task creator or scoped SME proposes a warning percentage and named source-cleared recipients. A different scoped Legal SME approves/rejects the exact hash. This is operational authorization, not legal review or audience release.
- Documents → My operational SLA alerts: recipient-only warning/breach inbox. Mark read, acknowledge and close are separate. Acknowledgement needs a rationale; creator/SME closure needs its own rationale. Authorization is checked again on reads and actions. There is no email transport.
- Portal Home links `/docs/checklist-records` and `/docs/sla-alerts`; Resources includes a downloadable escalation guide. START/STOP include the existing API/worker. Start opens Portal Home, not duplicate Swagger/service servers.

## Records and execution

Migration 0029 adds 16 tables: normalized checklist sections/items/coverage/evidence/finding links, request events and evidence links, report coverage snapshots, escalation plans/recipients/decisions, alerts/recipients/read receipts/dispositions, and a technical scan cursor. Raw checklist definitions/coverage decisions remain authoritative and unchanged. Deterministic projections are replay-safe and reject inconsistent existing rows.

Immutable-row database triggers protect retained records. Only the technical scan cursor is mutable. New signing manifests include business records; operational alert reads and the scan cursor are excluded. Signing freeze rejects business changes and worker emission. Stored historical signing manifests are not rewritten. Pending signatures from an earlier manifest schema must be reproposed, rather than silently upgraded.

The existing worker scans at most 20 plans every 30 seconds using a durable round-robin cursor. It rechecks current binding/assignment, latest plan, source snapshot, independent approver authority and each recipient's current/retained access. Superseded or unapproved plans, closed tasks, changed source policy and frozen matters do not emit. A unique plan/level key deduplicates warnings and breaches. A scan already beyond budget emits a breach directly. Scanning can take multiple cycles for a large queue; this is a bounded local baseline, not guaranteed real-time delivery. Exceptions follow the existing sanitized diagnostics/manual-restart behavior.

The live demonstration retains its unsubmitted checklist and SLA drafts. No approving identity was impersonated to activate alerts. There are zero new live alerts without published/bound policies and independent plan approval. Threshold 80% is a proposal-form default, not a published policy.

Imported CSV references may be explicitly confirmed through the request API with an import-row ID and actual linked source versions; exact request/disclosure strings are preserved. CSV preview remains the place to inspect staged references. A one-click governed application of imported assignment/QC and request proposals is not yet provided. No imported name, date or risk label becomes security authority or historical activity automatically.

## Verification

- Full regression: 253 passed, 1 skipped, 364.46 seconds. Existing Starlette/httpx deprecation warning remains.
- PostgreSQL isolated schemas: 9 checklist/escalation tests passed, including scope revocation, no self-approval, stale assignment, no unapproved emission, deduplication and freeze. Final additional projection-immutability/report-edit assertions: 5 checklist tests passed on SQLite. These counts overlap.
- Frontend TypeScript/Vite build passed. Browser verification used normal SME sign-in, inspected original request drafting and task plan controls, checked the explicit SLA prerequisite and the permission-filtered recipient list. Preview: `outputs/gate1-escalation-controls.jpg`.
- Encrypted backup: 85 tables / 14,560 rows restored with matching schema/data inventory before migration. Restored-copy rehearsal and live migration each preserved all 84 prior application-table digests, 17 source versions, 16 logical documents and 17 version links. Identity and checklist backfills replayed twice without changing records.
- Migration SHA-256: e3895ca96c5be15dcd2dab862494f893c7172967a10137514b7c9b9762ffd0d5. Receipts: `.runtime/prompt-audit/gate1-completion-migration-*`.
- Read-only live normal-session check: one existing draft checklist, five legacy report coverage endpoints, both new OpenAPI groups, Resources guide, Root Admin alert-content denial. Receipt: `.runtime/prompt-audit/gate1-live-verification.json`.
- Restart verification exposed a missing supervisor-state file. The launcher now recovers ownership only from the exact project supervisor script/executable and verifies PID start time before stopping; a port or process name alone never authorizes termination. Stop/restart was exercised; existing fixtures and decisions were preserved. Worker pulses report successful SLA scans.

## Safe rollback and next gate

Populated downgrade refuses to discard retained business records. Prefer a forward repair; preserve the verified encrypted pre-migration archive. Restoring it is a separate controlled recovery operation, not an automatic rollback over active data. Runtime files are outside the logical database backup; local DPAPI archives are not portable external WORM storage.

Next: Gate 2 segment attributes, mixed-content disclosure, redaction validation and controlled derivative release, preserving the existing reader and central PDP. React DataTables is still scheduled at Gate 4. LangGraph orchestration remains Gate 5. Checklist replacement publication stays blocked until the material-change impact adapter exists. This increment does not declare the complete application or Freshfields production architecture finished.
