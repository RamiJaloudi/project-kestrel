# Architecture diagram library

Start with the system context, application containers and data story. Each diagram has a readable SVG, a PNG for slides, an editable Mermaid source and a short evidence page. **Current code**, **configured DNS** and **target design** are labelled separately.

| Order | Diagram | Status |
|---:|---|---|
| 01 | [System context](01_system/01_system_context.md) | CURRENT CODE |
| 02 | [Application containers](01_system/02_application_containers.md) | CURRENT CODE |
| 03 | [Azure DNS and deployment](01_system/03_azure_dns_and_deployment.md) | CONFIGURED DNS / GATED DEPLOYMENT |
| 04 | [API architecture](01_system/04_api_architecture.md) | CURRENT CODE |
| 05 | [Authenticated request sequence](01_system/05_authenticated_request_sequence.md) | CURRENT CODE |
| 06 | [Document evidence lifecycle](02_workflows/06_document_evidence_lifecycle.md) | CURRENT CODE |
| 07 | [Permission first search](02_workflows/07_permission_first_search.md) | CURRENT CODE |
| 08 | [DDR graph execution](02_workflows/08_ddr_graph_execution.md) | CURRENT CODE |
| 09 | [Report review and release](02_workflows/09_report_review_and_release.md) | CURRENT CODE |
| 10 | [Financial evidence and decisions](02_workflows/10_financial_evidence_and_decisions.md) | CURRENT CODE |
| 11 | [Playbook change and approved rerun](02_workflows/11_playbook_change_and_approved_rerun.md) | CURRENT CODE |
| 12 | [Access and audience boundaries](03_security_operations/12_access_and_audience_boundaries.md) | CURRENT CODE |
| 13 | [Sanitized source disclosure](03_security_operations/13_sanitized_source_disclosure.md) | CURRENT CODE |
| 14 | [Durable work and failure handling](03_security_operations/14_durable_work_and_failure_handling.md) | CURRENT CODE |
| 15 | [Audit backup and retention](03_security_operations/15_audit_backup_and_retention.md) | CURRENT CODE |
| 16 | [The data story](04_data/16_the_data_story.md) | CURRENT CODE |
| 17 | [Implemented core ERD](04_data/17_implemented_core_erd.md) | CURRENT CODE |
| 18 | [Core entity relationships](04_data/18_core_entity_relationships.md) | CURRENT CODE |
| 19 | [Enterprise integration boundaries](05_target_design/19_enterprise_integration_boundaries.md) | TARGET DESIGN / NOT IMPLEMENTED CONNECTIONS |
| 20 | [Additional specialist roadmap](05_target_design/20_additional_specialist_roadmap.md) | TARGET DESIGN / FUTURE SPECIALISTS |

## Data model

[Open the complete data diagram index](04_data/README.md): 153 tables, 1412 fields, 442 declared foreign keys, and 17 detailed area ER views. A table-to-diagram CSV makes every table findable.

## Earlier inputs

[Source archive and replacement map](99_source_archive/README.md) preserves the five supplied PNGs, the older presentation Mermaid files and earlier resource diagrams. These are dated inputs, not additional current architecture claims.

## Updating diagrams

Edit `scripts/build_architecture_diagrams.py`, rebuild the SVG/Mermaid/evidence pages, then render PNGs with `scripts/render_architecture_diagrams.mjs`. Review the diagrams before updating the generated portal download copies. No database, service or Azure setting is changed by authoring diagrams.
