# Understand the API and schema files

Use OpenAPI to see the requests the application accepts today. Use the implemented model dictionaries to understand the tables declared by the code. Use the proposed design dictionaries to discuss the larger target architecture. These are different sources and must not be treated as the same schema.

## Read the files in this order

1. Implemented Schema Tables counts columns in each declared SQLAlchemy table. Implemented Schema Fields lists type, nullability, primary and foreign keys, and the basis for each explanation. This export reads code only. It does not connect to a database or prove that a deployed database has applied every migration.
2. Proposed Schema Fields explains the 809-field design snapshot. Proposed Schema Groups explains its documentation domains. The group field is a documentation category, not an account group or access grant.
3. Schema CSV Column Guide explains the headers in the proposed dictionary. Entity Catalogue and Foreign Key Relationships provide the corresponding target structure.
4. Tech Stack and Linux Portability records why each component was chosen and the work needed to move it from the Windows Azure VM. Portability is an engineering assessment, not a completed Linux test.
5. The Word schema guide tells the field story in a few pages. OpenAPI remains the request and response contract; neither dictionary grants API access or replaces service validation.

## Follow the data story

Identify a person and matter. Retain a document and immutable version. Bind exact evidence to a candidate finding and the playbook used. Record a lawyer decision. Build a report version. Approve a named audience separately. Retain audit history and apply holds and retention rules.

Stable identifiers connect records. Labels describe them. Version and hash fields bind a decision to exact content. Status fields record progress. Approval and release fields express separate decisions. Time and expiry fields bound access. Sensitivity fields help the shared policy engine decide who can act.

## Read definitions carefully

Declared types and keys are extracted facts. Some descriptions are inferred from field names because the source has no separate definition. The definition basis column flags that limitation. Check the relevant service, migrations and tests before changing a constraint. Missing data is not zero, and a pending decision is not approval.
