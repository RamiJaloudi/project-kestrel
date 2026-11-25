# 70 Governed profiles organization gate and durable hot alerts

24 November 2026. This extends document 68's read-only intelligence projection. Migration **0035** adds nine immutable tables without rewriting sources, findings, approvals, task history or historical signed manifests. No live feature setting is enabled by the migration or these tests.

## Independent bank feature gates

Castlegate financial access requires **both organization and matter switches**, followed by every existing individual disclosure/fact release and canonical PDP check. Missing settings are off. `GET/POST /api/v1/financial/organization-gate` is limited to authenticated firm Root Admin and always targets Castlegate; POST uses strict expected revision, boolean enabled and rationale fields. Changes append administrative revisions and audit events. No source, clean-team or legal approval privilege is granted.

Financial read/query, intelligence and table authorization-change detection now check this switch. Disabling the organization blocks future bank financial retrieval even if a matter switch stays enabled. Both enabled switches still cannot expose original-source financial facts or another audience's derivatives. `FinancialGate.tsx` shows organization and matter controls separately.

Existing fixtures that require bank access explicitly enable both. Test-only `test_financial_workflow.enable_org(http, root_csrf)` reads the organization revision and enables it through its authenticated API. The ordinary test environment does not globally enable it. No live setting was changed to satisfy a test.

## Versioned deterministic profiles

`IntelligenceProfile` captures matter/name/version/author, canonical definition/hash, rationale, request key and timestamp. Definitions retain every domain/component weight, alert threshold, minimum observed weight, named recipients and an explicit task assignee. Supplied domain maps must contain every allowed component with strict integer weights from 0 to 100 totaling exactly 100. Formulas, arbitrary components and boolean weights are rejected.

Root Admin or a scoped SME may draft configuration. Another current Legal SME must approve the exact hash; Root Admin/SME can then publish it. Authors cannot approve, reject or revoke their own version, and administrative privilege cannot replace SME authority. Publication and subsequent use recheck the approving principal. Changes create immutable new versions rather than changing a published profile or reassigning old alerts. Configuration access grants no source access.

```text
GET  /api/v1/intelligence/profiles?matter_id=...
GET  /api/v1/intelligence/profiles/people?matter_id=...
POST /api/v1/intelligence/profiles
POST /api/v1/intelligence/profiles/{id}/decisions
POST /api/v1/intelligence/query  optional explicit profile_id
```

The authorized configuration people list contains active, unwalled matter legal identities, not source counts or clean-team scopes. The default profile is document 68's transparent demo calculation. Unknown components stay null; observed weights are disclosed and no inputs means UNKNOWN. Profiles cannot fabricate financial thresholds, infer legal findings from lexical topics, or combine delay/legal/financial into an undisclosed total. Bank users cannot select internal profile IDs to retrieve internal recipients/configuration.

## Governed source-bound overrides

An override binds one source, published profile, domain, deterministic base hash, source snapshot, expiry, requester and rationale. The base includes the profile, source policy snapshot, component values/evidence and underlying task/finding/fact revision fingerprint. A task transition invalidates the old base even if its numerical score stays unchanged.

Proposal requires current source-cleared legal authority. Another source-cleared SME must approve the exact hash; approval recomputes the base and refuses stale evidence. Applying the override rechecks current scope, retained labels, expiry, profile approval and approving SME clearance. Expired, rejected, revoked or stale proposals do not apply.

The deterministic score remains unchanged. The UI separately labels an **approved operational priority** with rationale and expiry. This does not confirm a candidate, change a reviewed finding, approve a report or release content. UNKNOWN base components stay UNKNOWN; alert eligibility still requires sufficient observed evidence weight.

```text
GET  /api/v1/intelligence/overrides?source_id=...
POST /api/v1/intelligence/overrides
POST /api/v1/intelligence/overrides/{id}/decisions
```

## Durable alerts follow-up tasks and disposition

An explicit authenticated `POST /intelligence/profiles/{id}/scan` evaluates only the requester's current authorized sources under a published independently approved profile. It rechecks the approving SME and each named recipient against each source. Root configuration power cannot bypass source checks. Scans are bounded and manual; no scheduled hot-alert worker is claimed.

An eligible threshold crossing atomically creates an immutable `IntelligenceAlert` with retained restrictions, source snapshot, profile and complete signal components; one existing source-bound `ReviewTask` for the explicit assignee; named alert recipients; and the normal durable task notification records. These are operational follow-ups, not legal decisions or release approvals.

The unique dedupe hash binds profile hash, source snapshot, domain, underlying revision and applicable override ID. Repeating a scan creates no duplicate task/alert. New underlying revisions can produce new alerts. Time alone does not multiply an existing alert. Tasks already linked to intelligence alerts are excluded from scoring, preventing recursive alerts about their own follow-up tasks; the exclusion uses real linked alert records rather than a user-controlled request-key prefix.

Inbox access requires named recipient identity, current source clearance, retained restrictions and linked task/history access. Neither another matter lawyer nor Root Admin receives a blanket inbox. Bank/client users cannot read internal hot alerts. A read receipt is durable and distinct from acknowledgement, escalation, closure or task completion. Disposition appends revision-checked history and rationale; only the alert creator or scoped SME may close it. Closing an alert does not complete the linked task or finding.

```text
GET  /api/v1/intelligence/alerts?matter_id=...
POST /api/v1/intelligence/alerts/{id}/read
POST /api/v1/intelligence/alerts/{id}/dispositions
```

The UI supplies profile drafting/selection, independent decisions, explicit scan, recipient timeline, read receipts and disposition. Selecting a source's signal details exposes its override proposal/review controls. Profile configuration also appears in the existing administrative financial feature workspace without exposing source data.

## Retention signing and audit

The seven matter/source-bound profile/decision, override/decision, alert/recipient/disposition models join future signing manifests and the before-flush guard. Historical manifests remain unchanged. New content, scans/tasks and dispositions fail after signing. Scoped profile/override revocation is a containment exception; immutable read receipts remain operational after freeze. The global organization toggle remains administrative access control, not a blanket content grant.

Audit resolution preserves retained unions: an override decision includes its original override; an alert/recipient/disposition includes the original alert, linked task and task-event history. A later label downgrade cannot remove historical clean-team restrictions from an audit export. Events contain bounded IDs/scopes rather than source passages. Every new table rejects SQL UPDATE and DELETE. Downgrade refuses to drop any populated retained table.

## Verification and limits

Targeted SQLite regression: **50 passed in 160.50 seconds** across intelligence, governance, financial workflow, saved views and table security. The focused governance suite then ran **5 passed in 18.26 seconds** after exact task-revision and parent-retained audit checks. Final isolated **PostgreSQL: 14 passed in 33.03 seconds** for intelligence and governance, using temporary test schemas and the current additive migration head. TypeScript and the Vite production build passed with 75 modules. Tests never enable a live gate or migrate the live application schema.

Coverage includes organization default-off independent of matter setting; root/SME separation; immutable profiles; released derivative-only bank retrieval and revocation; deduped task/alerts; read versus disposition; freeze/walls; retained audit parent union; explicit override display; and stale revision rejection.

Limits remain explicit: default formula constants are demo navigation assumptions, not measured legal quality. There is no autonomous hot-alert scheduling, generated paid AI explanation, calibrated risk probability or external alert publication. Overrides do not alter legal findings. Wider public-host, DPAPI, migration and security gates still apply.

## Final response freshness hardening

All intelligence governance profile/people/override/inbox/action routes now authenticate again after response preparation and recheck their exact current configuration/source/recipient capability. Internal governance endpoints reject bank/client callers before preparing metadata. Read routes also compare the canonical authorization-input stamp; configuration routes preserve scoped Root Admin access rather than using a legal-source-only guard. Actions recheck current authority without comparing a stamp invalidated by their own authorized immutable write. If a later wall/role/scope change withholds a response, the application does not falsely claim that an earlier committed authorized transaction was rolled back. Denial audits contain no supplied object IDs or confidential text.

Focused response-freshness and existing governance regression: **10 passed in 91.21 seconds**, covering the reported profile metadata wall race, mid-role removal, root people metadata, revoked clean-team scope after alert preparation and bank denial before internal projection. Final isolated **PostgreSQL response-race suite: 6 passed in 12.99 seconds**, including the additional post-write wall case. No PostgreSQL test process from this task remained active when root began the coordinated backup/migration rehearsal.
