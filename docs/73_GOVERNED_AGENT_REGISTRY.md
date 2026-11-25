# Governed agent, model, prompt and tool registry

[DEMO] 24 November 2026. This increment implements retained agent configuration and independent legal publication, plus protected material-change tasks and an explicit new-run bridge. Tests make fictional decisions in isolated databases; they are not professional legal approval, enterprise provider clearance or permission to publish the application.

## Implemented behavior

Assigned, unwalled internal Root Admins create a logical profile and append immutable draft revisions. A revision binds the specialist role, server-known provider/model pair, instruction text, typed output schema, tool manifest, provider timeout and whole-run call/token/concurrency/cost ceilings. No credential, arbitrary URL, executable Python, access-management tool, legal-approval tool or external-release tool is accepted in a definition.

An exact revision passes deterministic static manifest checks, then its author submits it. An independent scoped Legal SME must explicitly review the retained prompt, model, tools, limits and test evidence and approve its exact content hash. A Root Admin can publish only that exact approved version while the independent approver remains active, assigned, unwalled and a Legal SME. Combining Root Admin and SME roles on the author's account does not permit self-approval. Static tests validate configuration/security shape; they do not establish legal accuracy or validate live model quality.

Draft editing creates another retained revision, never an overwrite. Definition diffs expose exact changed paths and before/after values. Published replacements form a single retained chain; a stale publication base is rejected. New runs select the current independently published version. Existing runs can retain an older pinned published version without silently changing instructions. Archiving a version disables future execution, including old pinned use. Publication/archive do not alter prior findings, approvals, report versions or already delivered copies.

The initial provider/model manifest permits `offline / deterministic-reviewed-v1` and the existing application OpenAI model pin. The current DDR application still refuses live graph activation. Registry publication does not activate a paid provider or establish enterprise approval. Fourteen specialist kinds can be described; the actual graph remains the bounded implemented slice documented in [72_DDR_GRAPH_PROTOCOL_AND_TESTS.md](72_DDR_GRAPH_PROTOCOL_AND_TESTS.md). Unsupported execution roles/providers fail closed rather than creating agents dynamically.

## Material change and SME inbox

Publishing a changed replacement scans retained DDR configurations for the exact old `AgentProfileVersion` ID in `config_json.agent_profile_ids`. For each affected run it creates a frozen impact snapshot, exact definition diff, one retained item for every source, an assigned SME task, and in-app notifications. The publisher's response exposes no affected-run/source count. Publication creates **no DDR run, analysis job, rerun approval or external release**.

Task reads, decisions, notification actions, audits and rerun-authority checks apply the union of all captured source restrictions and every source's current canonical PDP. A reviewer who loses clean-team access to one source cannot see a seemingly ordinary audit row, task header, diff or count for the mixed run. Root Admin is not an override. Eligible reviewers are named, currently source-cleared SMEs independent of the target author, publisher and original run requester. A missing eligible reviewer leaves a retained unassigned task; no automatic substitute approval occurs.

Notification read/acknowledgement timestamps are separate from task decisions. Identity and prior read/ack history cannot be rewritten. Approve/reject/revoke decisions bind the exact frozen impact hash and target definition hash. A stale source, reviewed finding, target configuration, or lost reviewer clearance blocks use of an approval. Acknowledgement alone supplies no rerun authority.

`agent_registry.authorize_rerun` returns a server-side revalidation contract with the original run, exact finding references, replacement profile IDs and a decision-bound hash. This JSON is not a client grant. Root's explicit `POST /api/v1/ddr/agent-impacts/{task_id}/rerun` bridge calls that service again, creates an idempotent new governed run under a reserved server key, and leaves the old run/history intact. Generic clients cannot forge the reserved key. Revoking the impact authority blocks an already queued rerun's future execution checks.

Signing freeze closes new drafts/publications/rerun approvals. Read/ack metadata and access-tightening archive/revoke actions remain available. New analysis and report approvals continue through their distinct existing lifecycle gates.

## Source and API integration

New standalone models in `backend/kestrel/models_agents.py` are imported once from `models.py`: `AgentProfile`, `AgentProfileVersion`, `AgentProfileEvent`, `AgentProfileReplacement`, `AgentProfileImpact`, `AgentProfileImpactItem`, `AgentProfileImpactTask`, `AgentProfileImpactDecision`, and `AgentProfileImpactNotification`.

Migration `0037` follows `0036`. It contains frozen SQLite/PostgreSQL DDL, immutable/retention triggers, monotonic notification metadata guards and an all-table downgrade precheck. A retained row prevents downgrade before any new table is dropped. No prior source, finding, policy, release or signed manifest is rewritten. Only isolated fixture migrations were applied by this agent.

The protected router is `/api/v1/agent-registry`, with catalog/list/create, append revision, exact-version action, diff, protected impacts, notification and decision endpoints. Root integrated retained registry objects into signing/retention and the audit resolver. All impact-linked audit records resolve every source through `audit_records`, rather than selecting just the first source or relying on audit category.

`AgentRegistryWorkspace.tsx` provides the existing internal portal with a lazy-loaded screen: exact retained configuration/hash and decision history; a separate draft editor; manual test/submit/approve/reject/publish/archive controls; and a source-restricted impact inbox with distinct read, acknowledge, rerun approval, explicit rerun start and revoke actions. It uses no-store fetches, CSRF writes, abort controllers, identity/matter generation checks and explicit 401/403/409 cleanup. The existing reader opens affected sources with its own authorization checks. No browser action walkthrough or live governance mutation was performed by this agent.

## Verification actually run

From `backend`, with `KESTREL_TEST_POSTGRES=0`:

```powershell
.venv/Scripts/python.exe -m pytest tests/test_agent_registry.py tests/test_agent_registry_rerun.py -q --tb=short
```

Final result: **9 passed in 32.94 seconds**. Coverage includes:

- Provider/model/tool allowlists and bounded budgets/timeouts; bank/cross-matter denial; Root plus SME same-person self-approval denial.
- Exact-version test/submission/content review/approval/publication, immutable history and diff, changed-version conflict and current approver wall denial.
- Material publication creates protected tasks/notifications without an automatic run; read/ack does not approve; only explicit exact-hash SME authority yields a rerun contract.
- Ordinary-plus-clean-team source union on task, decision, rerun and ordinary-category audit visibility after clean-team revocation.
- Explicit bridge creation/idempotency, denial of a client-forged reserved key, and grant revocation blocking queued execution.
- Notification identity retention, refusal of destructive downgrade with all nine tables preserved, and read/archive/revoke containment after signing freeze.
- Runtime configuration preserves approved lower token/output/concurrency/cost ceilings and rejects a profile that removes a tool required by its implemented stage.

`npm run build` passed after final UI integration: TypeScript/Vite, **77 modules**, separate Agent Registry chunk **15.02 kB / 4.90 kB gzip**. The earlier pure graph foundation separately passed its 22 tests and isolated dependency check; those results are in document 72. PostgreSQL and full-application acceptance remain root-owned checks and are not inferred from these SQLite results.

## Limits

The registry caps history at 500 revisions per matter, material impact publication at 500 affected runs, and the visible inbox at 100 permitted tasks. Publication currently builds bounded impacts synchronously; it is not a demonstrated production-scale impact worker. In-app notifications retain priority/deadline/read/ack data; there is no outbound delivery or separate automated escalation worker in this registry slice. No new MFN-specific selector or legal taxonomy was introduced. Semantic model evaluation, additional specialists/providers, enterprise authorization and cloud deployment remain separate acceptance work.


## 24 November provider integration clarification

The earlier activation limitation is historical: docs74 now records the implemented live adapter/aggregate budget and real-SDK mock-transport checks, and the current readiness constant is enabled. Actual paid processing still requires the private provider, processing policy, reviewed evidence and exactly three independently published stage profiles. No paid-call, legal-quality or enterprise-approval acceptance is implied. Other registered specialist kinds are not automatically executable; see docs80. Reviewable unapproved stage instructions are in `delivery/agent_profile_drafts/` and docs83.
