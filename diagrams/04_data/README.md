# Implemented data model

This model snapshot contains **153 tables, 1412 columns and 442 declared foreign keys**. It describes code structure, not an inspected deployed database. No row data was read.

[Readable data overview](16_the_data_story.md) · [Visual core ERD](17_implemented_core_erd.md) · [Core entity relationships](18_core_entity_relationships.md) · [Complete foreign key CSV](all_foreign_key_relationships.csv)

The detailed views show primary and foreign key fields. Drawing types are simplified; exact declared types and other attributes remain in the [implemented field dictionary](../../backend/kestrel/data/resource_library/Implemented_Schema_Fields.csv). Cross-domain parent tables appear as key-only context. Cardinality uses nullability and single-column primary/unique flags. A solid identifying relationship means the child foreign key belongs to its primary key. Composite uniqueness and service rules still require the model and migrations. References inside JSON payloads are not invented as database foreign keys.

| Area | Owned tables | Relationship view |
|---|---:|---|
| Identity And Access | 21 | [Open diagram](areas/01_identity_and_access.md) |
| Document Evidence | 17 | [Open diagram](areas/02_document_evidence.md) |
| Findings | 5 | [Open diagram](areas/03_findings.md) |
| Review Work | 19 | [Open diagram](areas/04_review_work.md) |
| Checklists | 10 | [Open diagram](areas/05_checklists.md) |
| Sanitized Disclosures | 5 | [Open diagram](areas/06_sanitized_disclosures.md) |
| Agent Registry | 9 | [Open diagram](areas/07_agent_registry.md) |
| Ddr Execution | 10 | [Open diagram](areas/08_ddr_execution.md) |
| Financial Evidence | 10 | [Open diagram](areas/09_financial_evidence.md) |
| Review Intelligence | 8 | [Open diagram](areas/10_review_intelligence.md) |
| Saved Views | 6 | [Open diagram](areas/11_saved_views.md) |
| Tracker Exchange | 3 | [Open diagram](areas/12_tracker_exchange.md) |
| Vdr Intake | 3 | [Open diagram](areas/13_vdr_intake.md) |
| Collaboration | 4 | [Open diagram](areas/14_collaboration.md) |
| Governance And Analysis | 13 | [Open diagram](areas/15_governance_and_analysis.md) |
| Reports And Releases | 6 | [Open diagram](areas/16_reports_and_releases.md) |
| Lifecycle And Audit | 4 | [Open diagram](areas/17_lifecycle_and_audit.md) |
