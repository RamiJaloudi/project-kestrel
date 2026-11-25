# Resource library and schema downloads

The portal Resources view now has a searchable project library above the existing role-specific Excel workflows. The library separates guides, diagrams, ledgers, sample reports, forms and API/schema documentation. Portal Home places schema downloads beside the API explorer. Swagger pages link to the current portal's schema category. Reports, Financial Evidence and tracker exchange provide contextual sample links.

All library API requests require a current authenticated session, including on LOCAL. An explicit manifest names the allowed files and organizations. Downloads are prepared in memory, checked against the recorded SHA256 and size, then the existing Resources helper rechecks current identity and guide eligibility before returning them. Paths from request parameters are never used as filesystem paths. No public static mount serves these assets. Failure is closed. Cache storage is disabled.

The library contains authored documentation and synthetic examples only. It does not export live sources, findings, approvals, releases or audit events. Firm-only dictionaries and internal report examples return 404 to external organizations. Halden and Castlegate have different fictional report examples. The library does not create a matter entitlement or an application decision. Static samples in a public GitHub source repository remain publicly readable, independently of the portal's sign-in requirement.

## Schema provenance

- Implemented model snapshot: 153 tables and 1,412 columns on 24 November 2026. Exported from SQLAlchemy metadata without a database connection. It is not proof that a deployed database has applied those migrations.
- Proposed target design: 809 fields, retained as a distinct design dictionary. Its group column is a documentation domain, not an account group or access grant.
- Definitions distinguish declared model documentation, observed foreign keys and explanations inferred from names. The service and migration code remain authoritative for business behavior.

## Asset maintenance

`scripts/export_implemented_schema.py` exports structure with the backend environment. `scripts/build_resource_library.py` builds authored guides, the canonical architecture and data diagrams, six ledger formats, their column dictionary, three Word report examples and copies of selected authored deliverables, including the presentation companion bundle and partner note. It reads no original supplied reference forms. A SHA256 manifest is rebuilt with each asset change. The optional authored deliverables live in the sibling workspace Deliverables folder; already bundled assets remain in the Python package.

The three Word samples were rendered with the bundled document renderer and their one-page layouts visually inspected. They include explicit fictional status and pending review/release decisions. Financial ledger debits and credits balance at EUR15,000.00, including a separate balance check for each journal entry.

## Validation

The focused resource library, role-specific workbook and preview suite passed 37 tests on isolated SQLite fixtures. The TypeScript/Vite production build passed. Tests cover signed-out denial, disabled accounts, all manifest file hashes, organization-specific report visibility, denied internal dictionaries, unknown paths, changed bytes, model dictionary provenance and ledger balance. This is not PostgreSQL parity or Azure deployment acceptance. No Azure service, proxy, certificate, consent or firewall state was changed for this feature.

Browser verification used a separate loopback HTTPS server and a disposable synthetic SQLite account. Category filtering, the schema shortcut and a real CSV download were verified. The fixture mapped localhost to the firm shell because the browser could not resolve the test subdomain; no deployed hostname map was changed. The temporary server was stopped afterward.


## Canonical diagram library

The top-level `diagrams/` folder is the authoring source: 20 current and target architecture views, plus 17 detailed model areas. SVG and PNG exports support reading and slides; Mermaid supports editing. Generated copies in the backend supply authenticated downloads. The library currently has 89 downloadable assets across all formats. Older supplied images and embedded diagrams are archived with replacement links.
