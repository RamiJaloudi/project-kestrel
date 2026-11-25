# 05 — Low-level design: normalized entities, invariants and APIs

## Relational entities (all use UUID primary keys and UTC times)
`organizations`, `accounts`, `roles`, `account_role_grants`, `matters`, `matter_assignments`, `ethical_walls`, `clean_team_memberships` (scope/expiry/approver), `policy_grants`, `documents`, `document_versions`, `document_pages`, `evidence_spans` (original quote, offset, optional OCR bbox), `document_classifications`, `source_manifests`, `ingestion_jobs`, `playbooks`, `playbook_versions`, `playbook_rules`, `playbook_authorities`, `playbook_test_cases`, `playbook_test_runs`, `playbook_legal_approvals`, `playbook_diffs`, `ai_analysis_runs`, `candidate_findings`, `finding_reviews`, `release_artifacts`, `release_approvals`, `release_recipients`, `report_drafts`, `report_sections`, `qa_sessions`, `comments`, `attachments`, `governance_impact_assessments`, `impact_items`, `reanalysis_requests`, `reanalysis_decisions`, `reanalysis_jobs`, `finding_reconciliations`, `governance_tasks`, `notifications`, `audit_events`, `outbox_events`, `incidents`, `retention_policies`, `freeze_snapshots`, `regulatory_issue_register`.

## Schema examples and constraints
- `playbook_versions(playbook_id, semantic_version, state, definition_json, SHA256, author_id, legal_approver_id, approved_at, published_at)`; unique `(playbook_id, semantic_version)`; **published immutable** enforced by service and DB check/trigger or privileges.
- `candidate_findings(doc_version_id, playbook_version_id, analysis_run_id, evidence_span_id, rule_ids[], state, proposed_severity, reviewer_id, reviewed_at)`; review history separately append-only; no direct mutation to approved history.
- `evidence_spans(document_version_id, page_number, start_offset, end_offset, raw_quote, quote_hash, bbox_json, language)`; validation checks exact normalized extracted document span, not LLM-written text.
- `release_artifacts(source_finding_version_ids[], audience, classification, sanitized_text, state, release_approver_id, clean_team_approver_id, released_at, revocation_at)`; create **distinct sanitized artifact**, never give bank a pointer to restricted source.
- `governance_impact_assessments(id, source_playbook_version_id, target_version_id, diff_hash, affected_set_hash, summary_hash, state, created_at, expires_at, evaluated_by)`; item list fixed/hashed after finalization; immutable snapshot.
- `reanalysis_requests(id, impact_id, requested_scope_json, state, assigned_sme, requested_by, priority, due_at)`; `reanalysis_decisions(request_id, actor_id, decision, rationale, evaluated_snapshot_hash, timestamp)`; unique successful authorization per canonical snapshot/scope with idempotency key.
- `notifications(id, recipient_id, task_id, event_id, is_read, read_at, acknowledged_at, resolved_at, priority, safe_subject)`; recipient-limited, distinct from task.
- `governance_tasks(id, type, matter_id, payload_ref, owner_id, state, due_at, escalation_policy_id)`; no duplicate task for same event and scope.
- `audit_events(id, occurred_at, actor_id, role_id, organization_id, matter_id, action, object_type, object_id, outcome, policy_version, correlation_id, safe_metadata, prev_hash, event_hash)`; append-only in demo, scalable WORM target.
- `regulatory_issue_register(id, matter_id, regime, candidate_fact_questions, status, specialist_owner, authority_refs[], source_refs[], impact, due_date, lawyer_conclusion, reviewed_at)`; never auto-finalize applicability.

## UI/API contracts (all require verified server session unless `GET /health`)
```
POST /api/v1/auth/login; POST /api/v1/auth/logout; GET /api/v1/auth/me
GET /api/v1/portal/navigation
GET /api/v1/matters/{id}/documents; POST /api/v1/matters/{id}/imports
GET /api/v1/documents/{id}/versions/{version}/evidence/{span_id}
GET /api/v1/findings; POST /api/v1/findings/{id}/review
POST /api/v1/releases/propose; POST /api/v1/releases/{id}/approve
POST /api/v1/releases/{id}/clean-team-approve; POST /api/v1/releases/{id}/publish
GET /api/v1/qa/answers; POST /api/v1/qa/ask
GET /api/v1/reports; POST /api/v1/reports/generate
GET /api/v1/admin/playbooks; POST /api/v1/admin/playbooks
PATCH /api/v1/admin/playbooks/{id}/draft; POST /api/v1/admin/playbooks/{id}/clone
POST /api/v1/admin/playbooks/{id}/test; POST /api/v1/admin/playbooks/{id}/submit
POST /api/v1/admin/playbooks/{id}/legal-approve; POST /api/v1/admin/playbooks/{id}/publish
POST /api/v1/admin/playbooks/{id}/archive; GET /api/v1/playbooks/{id}/diff/{a}/{b}
GET /api/v1/governance/inbox; GET /api/v1/governance/impact-assessments/{id}
GET /api/v1/governance/impact-assessments/{id}/items
POST /api/v1/governance/reanalysis/{request_id}/approve
POST /api/v1/governance/reanalysis/{request_id}/reject
GET /api/v1/governance/reanalysis/{request_id}/jobs
POST /api/v1/governance/notifications/{id}/acknowledge
GET /api/v1/governance/audit?object_id=...
```
Never implement role headers for authenticating clients. Requests to approve must not accept acting `user_id` or `role` from client; derive from session.

## Reanalysis approval payload
```
{
  "impact_assessment_id":"IA-001",
  "snapshot_hash":"<exact immutable SHA-256 returned from GET>",
  "target_playbook_version_id":"PB-COC-DE-001:1.3.0",
  "scope":{"mode":"eligible_unrestricted","document_version_ids":[]},
  "rationale":"Expanded indirect-control trigger, requires re-screening",
  "idempotency_key":"<client-generated-uuid>"
}
```
Server recomputes eligibility, denies mismatch/stale hash, and signs approval transaction with worker outbox event. Clean-team scopes require separate authorized task/SME where necessary. Approval is not release.

## Concurrency and consistency
- Approvals use DB row lock/optimistic `ETag`; verify current immutable snapshot and membership **inside transaction** before writing decision + outbox + audit.
- Outbox publisher delivers at least once; worker de-duplicates `(request_id, document_version_id, target_version, job_kind)`, supports retry/backoff and dead-letter.
- Do not overwrite previously reviewed findings. Reanalysis creates a new `analysis_run` and candidate version with explicit reconciliation links. Previously released artifacts remain as historical records until an authorized correction/revocation workflow.
- Trace every client-visible artifact to document and playbook versions, plus reviewer and release chain.
