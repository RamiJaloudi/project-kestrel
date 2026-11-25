# Actual versus proposed schema

Audit date: 23 November 2026. Live PostgreSQL schema at Alembic `0025`; metadata only. No data backfill or migration executed.

**Scope:** all 76 proposed entities and all 809 workbook fields. The workbook is a proposed schema, not a claim about deployed tables. See [exhaustive field mapping](workbook_field_mapping.csv). Workbook rows refer to Field_Dictionary, including its first three header/title rows.

Field correspondence totals: {'PARTIAL': 261, 'MISSING': 548}. EXISTING means a compatible deployed field/type/nullability only, not completion of the proposed feature. PARTIAL includes semantic aliases, encoded JSON, type differences and specialized implementations. MISSING means no safe field correspondence; no unrelated-table name matching was used.

UUID strings and UTC epoch seconds are current deliberate contracts. Native UUID/timestamptz conversion is not approved by this audit. Aliases are conceptual mapping candidates, not executable SQL or permission decisions. All joins require matter and exact-version validation.

| Proposed entity | Fields | Status | Existing basis | Gate | Preservation / gap |
|---|---:|---|---|---:|---|
| organizations | 5 | PARTIAL | organizations | 0 | Tenant code exists; richer organization metadata is missing. |
| matters | 10 | PARTIAL | matters | 0 | Client identity belongs to clients, not organization tenancy; frozen boolean is not a timestamp. |
| users | 9 | PARTIAL | accounts | 0 | Retain account IDs, UPN/email distinction, password hashes and sessions. |
| user_role_grants | 9 | PARTIAL | account_role_grants | 0 | role_id joins roles.name; current grants global, not time-bound matter roles. |
| matter_memberships | 8 | PARTIAL | matter_assignments | 0 | Membership plus independent walls; revoked has inverse status semantics. |
| policy_versions | 9 | PARTIAL | governance_versions | 2 | Governance versions filtered by kind; document_policy_versions are resource snapshots, not this registry. |
| document_sources | 12 | MISSING | — | 1 | No corresponding implemented registry/contract. |
| vdr_import_batches | 12 | MISSING | — | 1 | No corresponding implemented registry/contract. |
| vdr_mapping_profiles | 9 | MISSING | — | 1 | No corresponding implemented registry/contract. |
| documents | 11 | PARTIAL | source_versions | 1 | No logical-document row: logical_key+matter groups immutable versions; version ID must not become logical document ID. |
| document_versions | 17 | PARTIAL | source_versions | 1 | Binary stored in SQL, not an object URI; preserve source IDs/bytes and reader contracts. |
| document_relationships | 7 | PARTIAL | source_versions | 1 | Only previous-version chain; no normalized attachments/amendments graph. |
| record_custodians | 12 | MISSING | — | 1 | No corresponding implemented registry/contract. |
| document_custodians | 11 | MISSING | — | 1 | No corresponding implemented registry/contract. |
| document_parties | 7 | PARTIAL | document_review_versions | 1 | One retained counterparty text, not normalized party roles. |
| document_tags | 8 | MISSING | — | 1 | No corresponding implemented registry/contract. |
| document_segments | 15 | PARTIAL | source_versions | 2 | Extraction units are retained JSON; no stable segment IDs, bounding boxes or segment policy. |
| document_checklist_links | 8 | PARTIAL | checklist_coverage_decisions | 1 | Multi-value retained JSON references require validated projection; no independent link ID. |
| checklist_items | 10 | PARTIAL | checklist_versions | 1 | Items embedded in immutable definition_json; title/section/source metadata must be projected by item_id. |
| checklist_versions | 8 | PARTIAL | checklist_versions | 1 | Published state/independent approvals are decision events; actor/time require state=published filter. |
| checklist_coverage | 11 | PARTIAL | checklist_coverage_decisions | 1 | Append-only coverage revisions; applicability and verification are status/kind predicates, not unconditional fields. |
| review_tasks | 18 | MISSING | — | 1 | No corresponding implemented registry/contract. |
| review_task_events | 11 | MISSING | — | 1 | No corresponding implemented registry/contract. |
| review_sessions | 13 | MISSING | — | 1 | No corresponding implemented registry/contract. |
| review_decisions | 12 | PARTIAL | document_review_versions | 1 | Document coverage and finding review are separate; no generic task/QC schema yet. |
| review_clause_answers | 8 | PARTIAL | source_findings | 1 | Risk candidates and document coverage do not implement explicit yes/no/unclear/N/A answers. |
| sla_calendars | 9 | MISSING | — | 1 | No corresponding implemented registry/contract. |
| review_sla_policies | 11 | MISSING | — | 1 | No corresponding implemented registry/contract. |
| document_hot_signals | 12 | MISSING | — | 4 | No corresponding implemented registry/contract. |
| dashboard_saved_views | 9 | MISSING | — | 4 | No corresponding implemented registry/contract. |
| dashboard_aggregates | 8 | MISSING | — | 4 | No corresponding implemented registry/contract. |
| governance_notifications | 13 | PARTIAL | task_notifications | 1 | Playbook impact task notifications only; generic workflow events missing. |
| governance_tasks | 11 | PARTIAL | governance_tasks | 1 | Specialized impact task; do not reinterpret as generic review assignment. |
| audit_events | 13 | PARTIAL | audit_events | 0 | Scoped audit events; SQL records lack per-event hash chain and policy revision. Export hashes are not WORM. |
| security_attributes | 8 | MISSING | — | 2 | No corresponding implemented registry/contract. |
| document_attribute_assertions | 14 | PARTIAL | document_policy_versions | 2 | Resource-level policy snapshots; no segment assertions or confidence/provenance registry. |
| attribute_downgrade_approvals | 10 | PARTIAL | classification_requests | 2 | Existing human classification request workflow; no segment assertion references. |
| access_policy_decisions | 14 | PARTIAL | wall_check_records | 2 | Wall checker audit is not a complete durable PDP decision registry for every operation. |
| ethical_wall_rules | 9 | PARTIAL | wall_controls | 2 | Client/matter/role/relationship rules plus independent decisions; policy_revision is not a timestamp. |
| clean_team_grants | 9 | PARTIAL | clean_team_memberships | 2 | Scope membership plus source_access_grants; revoked boolean is not revocation timestamp. |
| service_authorizations | 9 | PARTIAL | service_tokens | 0 | Token/client scopes; active boolean is not a revocation timestamp, no per-job grant row. |
| content_classification_runs | 12 | PARTIAL | classification_requests | 2 | Suggestion/confirmation workflow is not dedicated per-model classification-run provenance. |
| ai_runs | 14 | PARTIAL | analysis_jobs | 5 | Direct review jobs plus ai_operations/budget reservations; queued timestamp is not true execution start, engine name not model ID. |
| playbook_versions | 10 | PARTIAL | governance_versions | 5 | Filter kind=playbook; retains exact hashes, approval and impact gates; no publish timestamp column. |
| agent_config_versions | 9 | MISSING | — | 5 | No corresponding implemented registry/contract. |
| document_findings | 16 | PARTIAL | source_findings | 1 | Candidate IDs and immutable lawyer revision IDs are different namespaces; select eligible exact revision. |
| finding_reviews | 8 | PARTIAL | finding_reviews | 1 | Preserve candidate disposition events and separate legal_finding_revisions. |
| issue_register | 17 | PARTIAL | legal_finding_revisions | 1 | Risk/consent registers exist, but seller question lifecycle and imported issue identifiers do not. |
| seller_qa_items | 11 | MISSING | — | 1 | No corresponding implemented registry/contract. |
| redaction_projects | 10 | MISSING | — | 2 | No corresponding implemented registry/contract. |
| redaction_marks | 12 | MISSING | — | 2 | No corresponding implemented registry/contract. |
| sanitization_validation_runs | 11 | MISSING | — | 2 | No corresponding implemented registry/contract. |
| release_artifacts | 10 | PARTIAL | release_packages | 2 | Existing report/finding/tracker packages, not arbitrary sanitized source binaries. |
| release_artifact_versions | 10 | PARTIAL | report_versions | 2 | Reports have immutable versions; sanitized binary derivation registry missing. Tracker bytes in tracker_exports only. |
| derivation_lineage | 8 | PARTIAL | policy_sources | 2 | Policy lineage edges exist; no typed segment/redaction transformation manifest. |
| release_approvals | 9 | PARTIAL | release_approvals | 2 | Approval binds release content and policy snapshot hashes, not new artifact-version FK. |
| release_grants | 9 | PARTIAL | policy_recipients | 2 | Explicit recipients plus audience policy; no new artifact action/expiry grant contract. |
| disclosure_incidents | 12 | MISSING | — | 2 | No corresponding implemented registry/contract. |
| indexed_corpus_records | 12 | MISSING | — | 3 | No corresponding implemented registry/contract. |
| search_queries | 11 | PARTIAL | question_answers | 3 | Stored Q&A, not route/strategy latency or indexed query trace. |
| search_result_evidence | 10 | MISSING | — | 3 | No corresponding implemented registry/contract. |
| document_citations | 18 | PARTIAL | source_findings | 4 | Retained evidence_json has units and exact offsets/quotes; not separate typed citation rows or all proposed format anchors. |
| document_reader_sessions | 10 | PARTIAL | audit_events | 4 | Reader access audit only; no active-session state or dwell-time proof. |
| document_comparison_sets | 8 | MISSING | — | 4 | No corresponding implemented registry/contract. |
| financial_entities | 8 | MISSING | — | 3 | No corresponding implemented registry/contract. |
| financial_periods | 8 | MISSING | — | 3 | No corresponding implemented registry/contract. |
| financial_metrics | 7 | MISSING | — | 3 | No corresponding implemented registry/contract. |
| financial_facts | 18 | MISSING | — | 3 | No corresponding implemented registry/contract. |
| financial_statement_lines | 13 | MISSING | — | 3 | No corresponding implemented registry/contract. |
| financial_instruments | 9 | MISSING | — | 3 | No corresponding implemented registry/contract. |
| financial_reconciliations | 13 | MISSING | — | 3 | No corresponding implemented registry/contract. |
| financial_analysis_runs | 11 | MISSING | — | 3 | No corresponding implemented registry/contract. |
| financial_materiality_policies | 9 | MISSING | — | 3 | No corresponding implemented registry/contract. |
| playbook_change_assessments | 10 | PARTIAL | impact_snapshots | 5 | Per-source immutable impact snapshots/diffs; counts require authorized aggregation, not a global assessment row. |
| reanalysis_approvals | 8 | PARTIAL | impact_decisions | 5 | Decisions bind task/snapshot; snapshot hash is not selected-scope JSON. |
| reanalysis_jobs | 9 | PARTIAL | analysis_jobs | 5 | Idempotent approved impact reruns exist; task ID != approval ID, playbook hash != full scope hash. |

## Field mapping interpretation

The CSV preserves proposed type, nullability, key, origin, sensitivity, definition and exact workbook row. A mapped `id` on a related specialized table is PARTIAL; it is never a license to reuse that ID as the primary key of a new logical entity. For example, source version IDs cannot become logical document IDs; release policy IDs are not artifact-version IDs. Boolean revoked/frozen values do not provide historical timestamps.

Existing tables omitted by the proposed workbook remain authoritative: authentication sessions/passwords, clients and compound client/matter validation, wall decisions, OCR jobs/verifications, lifecycle decisions, client submissions, archives, collaboration, tracker exchange, reports, budget reservations and immutable reconciliation records. Do not drop them because no workbook row mentions them.

The workbook itself is not an executable migration: proposed fields sometimes reference registries not fully defined (for example graph/prompt versions, disclosure schedules and structured contract terms). Resolve FK/ownership contracts before DDL. Current checklist statuses and source-restriction unions must survive normalization.
