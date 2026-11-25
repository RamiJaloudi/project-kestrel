# Selected schema companion

Adapted excerpt from the accepted `05_SCHEMA_DESIGN.md`, 24 November 2026. The original source remains unchanged. This portable companion retains the complete normalization examples and all 16 target-field examples. The presentation selects 12 distinct target fields. These are proposed contracts, not DDL applied to the current database. Repository-only links are omitted.

## Concrete normalization examples


The literal tracker columns and requested conceptual examples are distinguished below. `Reviewed_by`, `Assigned_to_past`, `Assignment_time` and `time_open` are **design shorthand**, not claims that those exact headers occur in T1. Actual headers include Assigned Reviewer, Date Assigned, Review Status, Date Reviewed, Days Open, QC Reviewer and QC Status.

| Before / source meaning | After in actual implementation (or explicit target gap) | Why and consequence |
|---|---|---|
|Assigned Reviewer / QC Reviewer; conceptual `Reviewed_by` and `Assigned_to_past` as comma-delimited strings.|Account IDs with `review_tasks` + `review_task_events.assignee_id/actor_id`; legal/document-review records bind `reviewer_id`. API joins `Account.display_name` and `Account.username` as UPN.|Multiple independent tasks/history survive name changes and reassignment. The actual tables are not invented `document_assignments`/`document_reviews` aliases. Assignment cannot grant access.|
|Date Assigned / Date Reviewed / Days Open; conceptual assignment/time-open counters.|Append-only events, session roots/receipts, explicit SLA bindings/calendars; derived queue/acceptance/turnaround and separately observed activity.|Server events establish chronology. Imported dates are proposals; browser-open duration is not productive work. Unsupported/offline intervals stay unknown.|
|Doc Type / Workstream used as a single all-purpose security category.|Mapped source metadata plus additive `ContentLabelAssertion`/decisions and exact range/provenance; coarse source policy and clean-team scope remain separate.|A document can be legal, financial and competitive at once. Typed descriptive catalogues are a target gap; assigning “financial” cannot lower privilege or release content.|
|Doc ID / filename with each revised file treated as an unrelated row.|Logical `documents`; immutable `source_versions`; `document_version_links`; vendor/source/import links and explicit previous-version handling.|Stable business identity does not overwrite evidence. Hash or filename alone does not establish a document match. Preserve source identity/reader references.|
|Change of Control / MFN and requested liability/governing-law questions as one Boolean column per rule.|Versioned playbook rules → cited candidates → lawyer-confirmed/corrected/rejected legal revisions with topic/severity/materiality and evidence.|Meaning and uncertainty are reviewable; new legal questions do not require one new source column each. Liability/governing-law examples are not all literal T1 headers.|
|Financial amount hidden inside Key Findings/Summary or a generic document amount.|Exact fact with entity/metric/period/currency/scale/basis/scope, source or derivative reference, evidence spans and verify/release/revoke decisions.|No float rounding, incompatible sums or LLM numerical authority. Cell formulas/caches remain source evidence, not executed calculations.|
|Custodian assumed to equal Assigned Reviewer or document owner.|Separate `record_custodians` and many-to-many `document_custodians` with source/document keys, provenance and known effective dates.|People/systems can hold the source without reviewing it; several custodians can link to multiple sources. Source custody is not an imported reviewer inference.|
|Risk Rating / Material? / Review Status copied into approved conclusions.|Retain import row; apply through current authorized legal/workflow services with new review/version history.|A spreadsheet status cannot impersonate a lawyer or approve a finding. Legal materiality and operational delay remain distinct.|
|“Sanitized” flag, hidden worksheet or audience column treated as a release.|Separate disclosure plan/review/rebuilt artifact/validation/exact decisions; independent report/release approval path.|The bank searches only authorized released evidence. A feature toggle or presentation field cannot authorize original legal advice.|


## Full 16-field target excerpt


**TARGET SCHEMA EXAMPLE —16 fields selected from the actual v1 workbook, not proposed DDL applied to the live database.** Use two optional appendix slides with eight rows each. Types/keys below are exactly the workbook proposal; the final column states the real implementation difference. Detailed text can remain in notes, with concise aliases in slide cells.

| Proposed field | Proposed type / key | Why it illustrates the design | Actual implementation basis / gap |
|---|---|---|---|
|`documents.id`|`uuid` PK|Stable logical identity.|`LogicalDocument.id`: UUID-formatted `String(36)`.|
|`documents.matter_id`|`uuid` FK / lookup|Scoped ownership.|Actual FK to `matters.id`; service validates matter context.|
|`document_versions.document_id`|`uuid` FK / lookup|Version belongs to identity.|Actual linkage through `document_version_links`, not a direct `SourceVersion.document_id` column.|
|`document_versions.sha256`|`char(64)`|Immutable byte integrity.|`SourceVersion.bytes_hash` `String(64)` plus retained binary.|
|`document_versions.binary_object_uri`|`text`|Separate content location.|Target only; actual `SourceVersion.data` is SQL binary. No deployed blob store claimed.|
|`users.upn`|`varchar(320)`|Readable identity distinct from key.|Actual API joins employer-qualified `Account.username` (`String(128)`); no `accounts.upn` column.|
|`document_custodians.custodian_id`|`uuid` FK / lookup|Many-to-many provenance.|Actual `DocumentCustodian.custodian_id`→`record_custodians.id`, with source/document scope.|
|`review_tasks.assigned_to_user_id`|`uuid` FK / lookup|Assignment is an identity relationship.|Actual current/historical assignee derives from `ReviewTaskEvent.assignee_id`, not a root-task column.|
|`review_task_events.event_at`|`timestamptz`|Auditable event chronology.|Actual `occurred_at` integer server UTC epoch seconds.|
|`document_attribute_assertions.asserted_value_json`|`jsonb`|Additive assertion values and provenance.|Actual validated `ContentLabelAssertion.labels_json` text plus scope/range/provenance; no universal JSONB attribute store.|
|`document_findings.playbook_version_id`|`uuid` FK / lookup|Legal interpretation pins rule version.|Candidate `SourceFinding.playbook_id`→`governance_versions`; reviewed revision retains/validates origin and evidence.|
|`document_findings.evidence_citation_id`|`uuid` FK / lookup|Traceable exact source evidence.|Actual finding/revision `evidence_json` with validated version/unit/offset/quote data; no universal citation-row FK.|
|`financial_facts.numeric_value`|`numeric(30,10)`|Typed exact quantity.|Actual `amount` uses PostgreSQL `NUMERIC(38,12)` / Decimal and canonical `amount_text`; SQLite fixtures use exact strings.|
|`financial_facts.period_id`|`uuid` FK / lookup|Comparable reporting period.|Actual explicit `period_start`/`period_end` ISO date strings plus evidence/context; no deployed `financial_periods` catalogue inferred.|
|`release_artifacts.audience`|`text`|Audience is bound to a product.|Actual disclosure plan/policy audience and separate release package policy; physical product classes differ from target aliases.|
|`release_approvals.snapshot_hash`|`char(64)`|Approval pins its decision basis.|Actual `ReleaseApproval.snapshot_hash` for package policy; disclosure uses exact `bundle_hash` decisions instead. Do not substitute one hash contract for the other.|

