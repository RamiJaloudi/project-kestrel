# Project Kestrel

An independent synthetic due diligence application and architecture assessment. The system connects retained evidence, lawyer review, governed report drafting and separate client and bank releases. It is not a Freshfields service or an approved production deployment.

## Browse in this order

| Order | Folder | What to open |
|---:|---|---|
| 1 | [Written deliverables](deliverables/README.md) | Plain English presentation, speaker notes, partner note, forms and schema guides |
| 2 | [Architecture diagrams](diagrams/README.md) | System, deployment, API, document, search, DDR, security, operations and data diagrams |
| 3 | [Guides by topic](docs/README.md) | Design, workflows, security, setup, dated validation and future plans |
| 4 | [Sample reports and ledgers](docs/resources/README.md) | Fictional report examples, six ledger formats, field definitions and download index |
| 5 | [Data model](diagrams/04_data/README.md) | Readable data story, core relationships, complete relationship CSV and 17 detailed ER views |

## Architecture and data

The diagram library has **20 architecture diagrams**, with numbered sections and matching SVG, PNG, Mermaid and explanation files. Current code, configured DNS and proposed enterprise design are labelled separately. Earlier supplied images and presentation diagrams are preserved in the source archive with replacement links.

The implemented model snapshot has **153 tables, 1,412 fields and 442 declared foreign keys**. Every table is listed in a detailed data area. The separate **809-field proposed design** is not implemented DDL. Field definitions identify explanations inferred from names. Model structure does not prove which migrations are applied on a server.

## Source layout

| Folder | Purpose |
|---|---|
| [backend](backend/) | FastAPI, shared authorization, business services, models, migrations and tests |
| [frontend](frontend/) | React, TypeScript, portal screens and API links |
| [deployment](deployment/) | Azure and Windows service templates with activation gates |
| [scripts](scripts/) | Local operator tools and reproducible diagram/resource builders |
| [data](data/) | Playbook drafts and fictional source documents |
| [fixtures](fixtures/) | Narrow regression inputs |
| [synthetic](synthetic/) | Specific intake and review exercises |

`diagrams/` is the diagram authoring source. Copies under `backend/kestrel/data/resource_library/` are generated authenticated application downloads. They are not a second diagram library to maintain manually.

## Run and verify

Start with the [local setup guide](docs/04_operations/LOCAL_WORKSPACE_README.md). Install Python dependencies from `backend/pyproject.toml` and the tested constraints, then run `npm ci` and `npm run build` in `frontend`. The Windows launchers remain at the repository root. Linux requires replacements for DPAPI, service control and the owner approval boundary.

Run backend tests against isolated fixtures. Portal downloads require a current signed-in account and permitted organization. Public repository assets are publicly readable. Sample reports and ledger entries create no application approval or audience release.

## Scope and status

This is a source and documentation snapshot. Azure restore, HTTPS, shared gateway routing and public activation require their own real acceptance. Configured DNS is not proof of a live application. See dated validation and remaining plans before relying on a feature.

Credentials, runtime data, private keys, backups, dependency installs, build caches, duplicate old projects, private notes and supplied third-party original forms are excluded. Freshfields branding is retained on authored assets at the owner's request. No open-source license has been selected. AI assistance was used for development and drafting; legal conclusions and production readiness require independent review.
