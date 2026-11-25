# Project resource library

Authored documentation and fictional examples. Portal downloads require sign-in. Files in a public source repository are publicly readable.

## Guides

- [Find and use project assets](../../backend/kestrel/data/resource_library/Resource_Library_Guide.md) — Resources brings together workflow guides, diagrams, sample ledgers, report examples, forms and technical dictionaries.
- [Read sample reports and ledgers](../../backend/kestrel/data/resource_library/Report_and_Ledger_Guide.md) — Every sample is fictional and separate from live matter records.
- [Plain English presentation and companions](../../backend/kestrel/data/resource_library/Presentation_and_Companions.zip) — PPTX with speaker notes and its linked schema and tracker companions. Extract the folder before opening the presentation.
- [One page partner note PDF](../../backend/kestrel/data/resource_library/Project_Kestrel_Partner_Note.pdf) — Plain-language partner briefing from the written deliverables.

## API and schema

- [Understand the API and schema files](../../backend/kestrel/data/resource_library/API_and_Schema_Guide.md) — Use OpenAPI to see the requests the application accepts today.
- [Implemented schema fields](../../backend/kestrel/data/resource_library/Implemented_Schema_Fields.csv) — Code-derived table, column, type, key and nullability snapshot, with definition basis. No database rows.
- [Implemented schema tables](../../backend/kestrel/data/resource_library/Implemented_Schema_Tables.csv) — Code-derived table inventory and field counts. Not proof of deployed migrations.
- [Proposed schema fields with definitions](../../backend/kestrel/data/resource_library/Proposed_Schema_Fields.csv) — All 809 proposed fields, group meanings, definition basis and portability notes. Not implemented DDL.
- [Schema CSV column guide](../../backend/kestrel/data/resource_library/Schema_CSV_Column_Guide.csv) — Explains the 21 headers in the proposed schema dictionary.
- [Tech stack and Linux portability](../../backend/kestrel/data/resource_library/Tech_Stack_and_Linux_Portability.csv) — Component versions, purpose, selection reasons and Windows-to-Linux migration work.
- [Tech stack and schema story](../../backend/kestrel/data/resource_library/Tech_Stack_and_Schema_Guide.docx) — Concise Word guide to the field families and portability limits.
- [Proposed schema groups](../../backend/kestrel/data/resource_library/Proposed_Schema_Groups.csv) — Definitions and counts of documentation domains. These are not account groups.
- [Proposed entity catalogue](../../backend/kestrel/data/resource_library/Proposed_Entity_Catalog.csv) — Entity purpose and design domains in the proposed target schema.
- [Proposed foreign key relationships](../../backend/kestrel/data/resource_library/Proposed_FK_Relationships.csv) — Target schema relationship design; check actual migrations before implementation.

## Sample ledgers

- [Document review ledger](../../backend/kestrel/data/resource_library/Document_Review_Ledger.csv) — Fictional example rows. This file is not an application export or approval record. Column meanings are in Ledger_Field_Definitions.csv.
- [Financial transaction ledger](../../backend/kestrel/data/resource_library/Financial_Transaction_Ledger.csv) — Fictional example rows. This file is not an application export or approval record. Column meanings are in Ledger_Field_Definitions.csv.
- [Findings and open issues ledger](../../backend/kestrel/data/resource_library/Findings_and_Issues_Ledger.csv) — Fictional example rows. This file is not an application export or approval record. Column meanings are in Ledger_Field_Definitions.csv.
- [Approval and decision ledger](../../backend/kestrel/data/resource_library/Approval_Decision_Ledger.csv) — Fictional example rows. This file is not an application export or approval record. Column meanings are in Ledger_Field_Definitions.csv.
- [Audience release ledger](../../backend/kestrel/data/resource_library/Audience_Release_Ledger.csv) — Fictional example rows. This file is not an application export or approval record. Column meanings are in Ledger_Field_Definitions.csv.
- [Audit event ledger](../../backend/kestrel/data/resource_library/Audit_Event_Ledger.csv) — Fictional example rows. This file is not an application export or approval record. Column meanings are in Ledger_Field_Definitions.csv.
- [Ledger field definitions](../../backend/kestrel/data/resource_library/Ledger_Field_Definitions.csv) — Column meanings for all six synthetic ledger formats. This dictionary describes examples, not database import contracts.

## Sample reports

- [Internal due diligence report example](../../backend/kestrel/data/resource_library/Internal_Due_Diligence_Sample.docx) — Short internal draft with a fictional citation, assumptions, team recommendation and pending decisions.
- [Halden report example](../../backend/kestrel/data/resource_library/Halden_Due_Diligence_Sample.docx) — Client-format action summary using fictional facts; no source material or application release.
- [Castlegate commercial report example](../../backend/kestrel/data/resource_library/Castlegate_Commercial_Report_Sample.docx) — Commercial-format status update with explicit missing financial impact and no privileged legal analysis.

## Diagrams

- [From a VDR document to a report](../../backend/kestrel/data/resource_library/Document_to_Report.svg) — Implemented workflow overview. Each stage retains its source and version. Search answers a question over permitted evidence. It does not prove that every document was reviewed. This diagram describes the code workflow; it does not prove acceptance on the Azure VM.
- [From a VDR document to a report editable source](../../backend/kestrel/data/resource_library/Document_to_Report.mmd) — Implemented workflow overview. Each stage retains its source and version.
- [How access and release are checked](../../backend/kestrel/data/resource_library/Access_and_Release.svg) — The hostname chooses the screen. The server decides whether the person may act. Root Admin has no blanket legal or source-reading privilege. Notification read is not approval. The Resource library contains authored examples only; it does not expose live matter exports.
- [How access and release are checked editable source](../../backend/kestrel/data/resource_library/Access_and_Release.mmd) — The hostname chooses the screen. The server decides whether the person may act.
- [Azure portal deployment](../../backend/kestrel/data/resource_library/Azure_Deployment.svg) — DNS configured on 24 November 2026. HTTPS and application activation have separate acceptance gates. Configured hostnames are not evidence of a live public application. Do not bypass the CLOSED gate. Linux requires replacements for DPAPI, Windows service control and the owner approval boundary.
- [Azure portal deployment editable source](../../backend/kestrel/data/resource_library/Azure_Deployment.mmd) — DNS configured on 24 November 2026. HTTPS and application activation have separate acceptance gates.
- [The schema follows the review](../../backend/kestrel/data/resource_library/Schema_Story.svg) — Use implemented dictionaries for model structure and proposed dictionaries for target design. The proposed dictionary contains 809 fields. Its group column is a documentation domain, not an access grant. The implemented model export reads structure only; applied database migrations need separate verification.
- [The schema follows the review editable source](../../backend/kestrel/data/resource_library/Schema_Story.mmd) — Use implemented dictionaries for model structure and proposed dictionaries for target design.
- [How the API connects the application](../../backend/kestrel/data/resource_library/API_Architecture.svg) — One typed API supports the portals. Calling an endpoint never creates permission. OpenAPI describes current request and response contracts. Model CSVs describe the code-declared structure. The proposed 809-field design is separate. Enterprise integrations remain design or mock adapters where stated.
- [How the API connects the application editable source](../../backend/kestrel/data/resource_library/API_Architecture.mmd) — One typed API supports the portals. Calling an endpoint never creates permission.
- [How a cited question is answered](../../backend/kestrel/data/resource_library/Search_Architecture.svg) — Search uses the evidence the signed-in person may currently read. A ranked answer does not establish complete diligence or lawyer approval. Missing evidence stays unknown. Provider-backed semantic search remains subject to processing policy and the shared cost cap.
- [How a cited question is answered editable source](../../backend/kestrel/data/resource_library/Search_Architecture.mmd) — Search uses the evidence the signed-in person may currently read.

## Forms and trackers

- [Project Kestrel DDR Checklist](../../backend/kestrel/data/resource_library/Project_Kestrel_DDR_Checklist.csv) — Authored synthetic checklist or associate review tracker. Not an original Freshfields form.
- [Project Kestrel DDR Checklist](../../backend/kestrel/data/resource_library/Project_Kestrel_DDR_Checklist.pdf) — Authored synthetic checklist or associate review tracker. Not an original Freshfields form.
- [Project Kestrel DDR Checklist](../../backend/kestrel/data/resource_library/Project_Kestrel_DDR_Checklist.xlsx) — Authored synthetic checklist or associate review tracker. Not an original Freshfields form.
- [Associate VDR Review Guide](../../backend/kestrel/data/resource_library/Associate_VDR_Review_Guide.pdf) — Authored synthetic checklist or associate review tracker. Not an original Freshfields form.
- [Project Kestrel Associate VDR Tracker](../../backend/kestrel/data/resource_library/Project_Kestrel_Associate_VDR_Tracker.xlsx) — Authored synthetic checklist or associate review tracker. Not an original Freshfields form.
