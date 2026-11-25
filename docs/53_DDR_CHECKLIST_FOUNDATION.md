# 53 — DDR checklist foundation (P1.1)

[IMPLEMENTED, LOCAL SYNTHETIC DEMO] 23 November 2026. First implementation batch from docs/52_LANGGRAPH_DDR_PHASE0_PLAN.md. This is the deterministic checklist foundation, not a running LangGraph agent engine.

## Delivered

- Shared API group /api/v1/checklists, documented at /docs/checklists.
- DD Checklist page in the Firm portal and the Root Admin / Legal SME Administration navigation. The page uses authenticated matter choices and existing same-origin sessions/CSRF.
- Audited A–N section metadata and source checksum, plus one independently authored request, KESTREL-G-CONTRACTS-001, mapped to section G/page 10. It is explicitly an original abstraction rather than a copied numbered source item.
- Draft → submit → independent Legal SME approve/reject → publish exact hash. Published definitions cannot be edited; replacement drafts are new immutable records.
- Append-only coverage decisions: NOT_REQUESTED, REQUESTED, RECEIVED, UNDER_REVIEW, VERIFIED, GAP and NEEDS_CLARIFICATION. N_A_APPROVED_BY_HUMAN is produced only by an independent SME decision on an applicability request, never by a normal status submission.
- Optional source/finding links and a cleared legal owner. Received/review/verified require responsive linked source types; reviewed finding links are checked against actual current policy and matter.
- Verified requires confirmed, text-ready, whole-document-reviewed sources, verified OCR where applicable and no unresolved candidates. It does not approve legal conclusions or audience publication.
- Current source hashes and exact finding revision/policy snapshots are checked against retained coverage bindings. Changed evidence is flagged NEEDS_CLARIFICATION; denied evidence is omitted from the permitted view rather than replaced with a misleading older receipt.
- Later coverage decisions retain the union of earlier source restrictions. Recorded clean-team scope still applies after source relabelling and membership revocation. An ordinary status update cannot remove it.
- Clean-team coverage events enter the scoped audit stream. Multi-scope events are indexed per scope; audit export checks the complete retained and current source restriction union.
- New signing manifests use schema kestrel-signing-manifest-2 and include checklist definitions, publication decisions and coverage decisions. Existing stored signing records are not rewritten. Checklist mutations stop after signing.

## Important limits

The imported taxonomy contains section headings, not the full set of request items. The initial registry has fourteen section descriptors and one original scoped request. Custom original draft items can be supplied through the typed API; a comprehensive item editor and professionally approved UK/German checklist are not claimed.

A default GAP means no responsive evidence has been explicitly linked to this scoped request. It is not a finding of noncompliance, a claim that a company document does not exist, or an automatic N/A decision. The UI and API state that the view is permission-filtered.

Root Admin has scope-metadata authority, not source-content or coverage access. External accounts cannot read internal checklist definitions or coverage. All roles remain subject to current matter grants and walls.

Replacement **publication** is deliberately blocked when a published version already exists. The material-change impact/SME task adapter must be implemented before a changed checklist can become active. Initial publication and independent review work; no automatic reanalysis or external publication exists here. No registered tool IDs can be activated before their catalog/approval batch.

No LangGraph/LangChain dependency, graph/checkpointer, AI agent, provider failover or paid model call has been introduced. P1.2 evidence/tool services and P1.3 durable runs remain next, followed by the Phase 2 graph. The proprietary source PDF stays at its original private location; only the summarized taxonomy, provenance and original request are used by this foundation.

## Storage and contracts

Migration 0025 adds checklist_versions, checklist_version_decisions and checklist_coverage_decisions. All three have database UPDATE/DELETE guards. Version numbering and decision revisions have unique constraints; requests support idempotency keys, with bound input hashes. A repeated creation key cannot be reused for a different draft. Matter/version locks and optimistic expected_revision values guard decisions.

Coverage snapshots include source-policy hashes, exact finding revision references and retained classifications/scopes. They do not contain original source passages. Reads, writes and audit export reauthorize the actor; no browser-supplied identity or model-provided permission fields are accepted.

API routes:
- POST /api/v1/checklists and GET ?matter_id=...
- GET /api/v1/checklists/{version_id}
- POST /{version_id}/submit|approve|reject|publish with expected revision, exact content hash and rationale
- GET /{version_id}/coverage
- POST /{version_id}/coverage/{item_id}
- POST /{version_id}/coverage/{item_id}/na-requests
- POST /{version_id}/na-requests/{request_id}/approve|reject

Definition corrections create new drafts; there is no in-place edit or destructive delete endpoint. Human decisions are separate retained rows. The first batch has no dedicated Action Center notification adapter; submitted versions remain durable in DD Checklist pending review.

## Validation actually performed

- Tests were added before implementation: the first six cases failed because the new routes did not exist.
- Focused checklist/migration/lifecycle suite: 16 passed.
- Focused checklist/audit/governance/archive suite after the audit integration refinement: 23 passed.
- Full backend regression: 220 passed, 1 skipped, one existing Starlette/httpx deprecation warning; 384.03 seconds. No production throughput claim follows from these tests.
- Frontend TypeScript/Vite build passed, 49 modules, including final spacing/copy refinement.
- Tests cover authentication, wall/cross-matter/external denials, independent approval and revoked approver authority, exact hashes/revisions, draft idempotency, source provenance, evidence receipt requirements, clean-team revocation and derivative restrictions, changed finding snapshots, immutable SQL records, independent N/A and signing snapshot invalidation/freeze.
- Before migration: encrypted PostgreSQL backup and isolated scratch restore verified 61 tables / 14,157 rows plus matching schema; backup retained. The active database was not restored over.
- Existing launcher applied additive migration 0025 and restarted real services with -NoOpen. No new service or duplicate API server was introduced. Existing fixtures, approvals, findings and releases were preserved.
- Browser verification under admin01@freshfields.example: actual authenticated page, initial draft creation, A–N expansion with correct page spans, one original request, draft status and rationale-gated submission. A v1 draft was created in synthetic matter 012345-789012. It remains unsubmitted, unapproved and unpublished; no legal/publication approval was performed.
- Read-only live API script scripts/verify_checklist_foundation.py verified the draft, fourteen sections, one original request, Root coverage denial, unpublished coverage block and external denial. Its sessions were logged out. No credential values were printed.
- Local API, HTTPS redirect, PostgreSQL and worker health checks passed.
- Screenshot: outputs/ddr-checklist-foundation.jpg. No claim is made that published coverage controls were browser-tested; their authorization and decisions were exercised in isolated backend tests.

## Files and rollback

New: schemas/ddr.py; services/checklists.py; repositories/checklists.py; api/checklists.py; migration 0025; test_ddr_checklists.py; ChecklistWorkspace.tsx; verify_checklist_foundation.py. Updated: models.py, main.py, preview.py, auditing.py, lifecycle.py, resources.py, PortalApp.tsx, Administration.tsx, compact.css and Start/Stop descriptions. The launcher topology and private configuration are unchanged.

Source backups preserving relative paths: .runtime/ui-backups/checklist-foundation-20261123-090856. Restore those copies and rebuild/restart for a code rollback, retaining the additive schema and records. A populated checklist registry blocks destructive downgrade; do not discard the new draft or audit records to force a rollback. The encrypted pre-migration backup is for an explicitly governed recovery, not an automatic restore over newer matter data.

## Next batch

P1.2: typed EvidenceRef snapshots and registered policy-enforcing tools for reviewed findings. Include original-language spans, source/finding/playbook versions, OCR provenance, purpose-bound execution context and deterministic citation checks. The LangGraph vertical slice follows after these controls and durable run/budget support; it does not replace the existing evidence/release services.
