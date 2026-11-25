# Project Kestrel

An independent synthetic due diligence application and architecture assessment. Python and FastAPI serve a React and TypeScript interface, with PostgreSQL as the application database. The project demonstrates source citations, lawyer review, separate audience release, ethical walls, named clean-team controls and governed report drafting. It is not a Freshfields service or an approved production deployment.

## Start here

- [Resource library and download index](docs/resources/README.md)
- [Plain English presentation with speaker notes](deliverables/01_Presentation/Project_Kestrel_Plain_English_v3.pptx)
- [Partner note](deliverables/02_Partner_Note/)
- [Updated diagrams](backend/kestrel/data/resource_library/Document_to_Report.svg) and [editable sources](docs/resources/README.md#diagrams)
- [API and schema guide](backend/kestrel/data/resource_library/API_and_Schema_Guide.md)
- [Implemented schema fields](backend/kestrel/data/resource_library/Implemented_Schema_Fields.csv) and [proposed design fields](backend/kestrel/data/resource_library/Proposed_Schema_Fields.csv)
- [Sample reports, ledgers, forms and field definitions](docs/resources/README.md)
- [Local setup and application limits](docs/LOCAL_WORKSPACE_README.md)
- [Resource feature and validation scope](docs/RESOURCE_LIBRARY_20261124.md)

## Schema and deployment status

The code-derived model snapshot has 153 tables and 1,412 fields. The proposed target design dictionary has 809 fields. These have different purposes. Neither proves which migrations have been applied on a server. Field definitions identify where explanations were inferred from names.

This repository is a source and documentation snapshot. Azure restore, HTTPS, shared proxy routing and public activation are separate acceptance work. DNS configuration is not proof of a live application. No runtime credentials, private keys, actual database, uploaded matter records, cloud approval files or Git history are included.

## Development

Use a fresh Python virtual environment and the constraints in `backend/pyproject.toml` and `backend/requirements-tested.txt`. Install the backend from `backend` with the appropriate development/PostgreSQL extras. Use `npm ci` then `npm run build` in `frontend`. The Windows launcher can create private local runtime configuration; review its prerequisites before running it. Linux needs replacements for DPAPI, Windows services and the owner approval boundary.

Run backend tests from `backend` against isolated test fixtures. The resource library change was checked with 37 focused tests plus the production frontend build. This is not a claim that every integration or Azure acceptance test has passed. See the dated documentation for earlier scope and limitations.

Portal downloads require a signed-in account and the permitted organization. Files in this public repository are publicly readable. All included sample reports and ledgers are fictional. Spreadsheet entries do not approve a legal finding or release a report.

## Publication scope

This snapshot includes current source, migrations, tests, deployment templates, authored guides, diagrams, forms, CSV dictionaries and synthetic fixtures. Supplied third-party original documents, private notes, credential folders, local runtime state, caches, virtual environments, build outputs, duplicate old project trees and packaged backup archives are excluded. Freshfields branding is retained on authored assets at the owner's request; no affiliation or endorsement is claimed. No open-source license has been selected.

AI assistance was used to develop code and draft documentation and synthetic examples. Legal conclusions, production security, performance and deployment readiness require independent review.
