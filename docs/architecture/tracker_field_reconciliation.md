# Tracker field reconciliation

23 November 2026. All 30 Review Log and 14 Issues List row-2 headers match the proposed mapping exactly. Row data and synthetic example contents are intentionally excluded. This is an associate workflow template, not proof of a VDR vendor export.

Workbook formulas: Dashboard 182, Review Log 1,000, Issues List 600. Current general XLSX ingestion rejects formulas. Do not send this source tracker through that path or silently strip formulas: build a dedicated mapping/import preview, import allowed values, derive joined/calculated fields server-side, and retain original template/hash privately.

## Review Log

| # | Exact header | Proposed destination | Existing support / work required |
|---:|---|---|---|
| 1 | Doc ID | documents.external_tracker_id | PARTIAL: source_versions.logical_key; separate immutable logical document and external tracker IDs required. |
| 2 | VDR Index # | document_sources.vdr_index_number | MISSING: dedicated vendor/workflow mapping required. |
| 3 | VDR Folder Path | document_sources.folder_path | MISSING: dedicated vendor/workflow mapping required. |
| 4 | Document Title | documents.canonical_title | MISSING: dedicated vendor/workflow mapping required. |
| 5 | Doc Type | documents.document_kind / document_tags | PARTIAL: document_policy_versions.resource_type; contextual tags must remain separate from access restrictions. |
| 6 | Workstream | document_tags(tag_family=workstream) | MISSING: dedicated vendor/workflow mapping required. |
| 7 | Counterparty | document_parties.party_name | PARTIAL: document_review_versions.counterparty; normalized party roles missing. |
| 8 | Doc Date | document_versions.doc_date | MISSING: dedicated vendor/workflow mapping required. |
| 9 | Date Added to VDR | document_sources.vdr_added_at | MISSING: dedicated vendor/workflow mapping required. |
| 10 | Assigned Reviewer | review_tasks.assigned_to_user_id -> users(upn,display_name) | MISSING: dedicated vendor/workflow mapping required. |
| 11 | Date Assigned | review_tasks.assigned_at / review_task_events | MISSING: dedicated vendor/workflow mapping required. |
| 12 | Review Status | review_tasks.status / review_decisions.review_status | PARTIAL: document_review_versions / finding_reviews; generic review/QC task history missing. |
| 13 | Date Reviewed | review_decisions.reviewed_at | PARTIAL: document_review_versions / finding_reviews; generic review/QC task history missing. |
| 14 | Days Open | derived: review_tasks + review_task_events + sla_calendars | MISSING: dedicated vendor/workflow mapping required. |
| 15 | Change of Control | review_clause_answers(clause_code=change_of_control) | MISSING: dedicated vendor/workflow mapping required. |
| 16 | Anti-Assignment | review_clause_answers(clause_code=anti_assignment) | MISSING: dedicated vendor/workflow mapping required. |
| 17 | Consent / Notice Req'd | review_clause_answers(clause_code=consent_notice) | MISSING: dedicated vendor/workflow mapping required. |
| 18 | Exclusivity / Non-Compete | review_clause_answers(clause_code=exclusivity_noncompete) | MISSING: dedicated vendor/workflow mapping required. |
| 19 | MFN | review_clause_answers(clause_code=mfn) | MISSING: dedicated vendor/workflow mapping required. |
| 20 | Termination for Convenience | review_clause_answers(clause_code=termination_convenience) | MISSING: dedicated vendor/workflow mapping required. |
| 21 | Expiry / Renewal Date | document_tags(date expiry_renewal) / structured_contract_terms | MISSING: dedicated vendor/workflow mapping required. |
| 22 | Material? | document_findings.materiality_status | PARTIAL: immutable legal finding revision fields; imported IDs, ownership and seller-Q&A mapping must be explicit. |
| 23 | Risk Rating | document_findings.risk_rating | PARTIAL: immutable legal finding revision fields; imported IDs, ownership and seller-Q&A mapping must be explicit. |
| 24 | Key Findings / Summary | document_findings.approved_text / candidate_text | PARTIAL: immutable legal finding revision fields; imported IDs, ownership and seller-Q&A mapping must be explicit. |
| 25 | Follow-Up Req'd? | issue_register / seller_qa_items | PARTIAL: source_findings / legal_finding_revisions; preserve candidate versus approved revision. |
| 26 | Request List Ref | document_checklist_links -> checklist_items | PARTIAL: retained checklist definition and append-only coverage links; normalized reference projection missing. |
| 27 | Disclosure Schedule Ref | document_tags / dedicated disclosure_schedule_links | MISSING: dedicated vendor/workflow mapping required. |
| 28 | QC Reviewer | review_tasks assignment_type=qc / review_decisions | PARTIAL: document_review_versions / finding_reviews; generic review/QC task history missing. |
| 29 | QC Status | review_decisions.review_status | PARTIAL: document_review_versions / finding_reviews; generic review/QC task history missing. |
| 30 | Comments | review_decisions.review_notes / governed comments | PARTIAL: document_review_versions / finding_reviews; generic review/QC task history missing. |
## Issues List

| # | Exact header | Proposed destination | Existing support / work required |
|---:|---|---|---|
| 1 | Issue ID | issue_register.source_issue_id | PARTIAL: source_findings / legal_finding_revisions; preserve candidate versus approved revision. |
| 2 | Related Doc ID | issue_register.document_id | PARTIAL: source_findings / legal_finding_revisions; preserve candidate versus approved revision. |
| 3 | Doc Title (auto) | documents.canonical_title (joined) | MISSING: dedicated vendor/workflow mapping required. |
| 4 | Workstream (auto) | document_tags(workstream) (joined) | MISSING: dedicated vendor/workflow mapping required. |
| 5 | Issue Description | issue_register.description | PARTIAL: immutable legal finding revision fields; imported IDs, ownership and seller-Q&A mapping must be explicit. |
| 6 | Risk Rating | issue_register.risk_rating | PARTIAL: immutable legal finding revision fields; imported IDs, ownership and seller-Q&A mapping must be explicit. |
| 7 | Proposed Mitigation | issue_register.proposed_mitigation | PARTIAL: immutable legal finding revision fields; imported IDs, ownership and seller-Q&A mapping must be explicit. |
| 8 | Mitigation Type | issue_register.mitigation_type | PARTIAL: source_findings / legal_finding_revisions; preserve candidate versus approved revision. |
| 9 | Raised By | issue_register.raised_by_user_id -> users | PARTIAL: source_findings / legal_finding_revisions; preserve candidate versus approved revision. |
| 10 | Date Raised | issue_register.date_raised | PARTIAL: source_findings / legal_finding_revisions; preserve candidate versus approved revision. |
| 11 | Request Sent to Seller | issue_register.seller_request_sent_at | PARTIAL: source_findings / legal_finding_revisions; preserve candidate versus approved revision. |
| 12 | Seller Response | seller_qa_items.response_text / seller_response_id | MISSING: dedicated vendor/workflow mapping required. |
| 13 | Status | issue_register.issue_status | PARTIAL: immutable legal finding revision fields; imported IDs, ownership and seller-Q&A mapping must be explicit. |
| 14 | Owner | issue_register.owner_user_id -> users | PARTIAL: immutable legal finding revision fields; imported IDs, ownership and seller-Q&A mapping must be explicit. |

Source columns classified VDR in the proposed workbook are index, folder, document title and VDR added timestamp. Assignment, lawyer answers, QC and comments are governed workflow inputs; Days Open and auto-title/workstream are derived. Never let an import assign a role, clear a wall, mark an AI result attorney-approved or publish externally. The MFN column explicitly means Most-Favored-Nation; the separate phrase “MFN changes” remains unresolved.
