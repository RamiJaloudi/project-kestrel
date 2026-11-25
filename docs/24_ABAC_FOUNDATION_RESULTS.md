# Document ABAC / PostgreSQL foundation — implementation evidence

## Confirmed scope

See docs/23_CONFIRMED_ABAC_TRACKERS_REPORTS.md. All user selections are requirements, not optional alternatives. This is one bounded implementation increment; the complete tracker/report product and reference parity are not claimed complete.

## Implemented

- Dedicated native PostgreSQL 18 project cluster at `.runtime/pgdata`, loopback 127.0.0.1:55432, SCRAM password authentication. Does not change the installed Windows PostgreSQL service. Generated credentials stored in ignored `.runtime/database.json`, restricted to local Windows owner. No credentials printed or committed. SQLite file retained; earlier source contained zero accounts.
- Start/stop batch scripts now start/stop the owned cluster alongside portals. Account bootstrap and application use the configured PostgreSQL URL. Explicit supplied DB URLs remain supported. Local cluster owner is currently a development administrative identity; separate migration/runtime/read-view DB roles remain a public-hardening requirement.
- Migration 0003 adds document-version policy metadata, source-lineage links, optional unique normalized account emails, OAuth clients and hashed bearer tokens, and `vw_document_policy_state`.
- Deterministic ABAC decisions load stored version attributes through the SQL view, not requester-supplied classification/approval flags. Supports type/classification, human-confirmation status, review, recipient release, quarantine, supersession, signing freeze, AI restriction, scoped clean team, matter/ethical-wall checks, and source-lineage inheritance.
- Published external package eligibility binds to a snapshot hash covering its attributes and source versions. Changed metadata/source hash invalidates eligibility. Bank privilege cannot be bypassed with a generic sanitized flag. Clean-team-derived ordinary sanitized artifacts require antitrust approval. Snapshot approval workflow itself remains future work; no API accepts forged approval booleans.
- Signing freeze preserves authorized reading and blocks mutation/analysis/re-export operations. Historical reading is an internal action. Editing reviewed/released material requires a new version.
- Local OAuth client-credentials endpoint with HTTP Basic client authentication, Argon2id client secrets, opaque hashed short-lived tokens, active-client/account checks at API usage and per-endpoint scopes. Browser sessions remain supported. No Keycloak/Entra integration is claimed. This is a local authorization server implementation, not a certified OAuth provider or completed enterprise deployment.
- Client/matter validation, ordered raw-array batch validation (1–100), and per-normalized-email wall-check compatibility endpoints. Validation preserves the distinction between matter validity and environment authorization. Unknown/unauthorized identity/matter does not disclose names. Explicit assignments/deny precedence are retained; permissive allow-all reference modes are not imported.
- Firm portal has distinct Diligence Trackers and Reports & Board Pack navigation, with agreed workflows and output formats visibly marked planned. These are scope previews, not spreadsheet import/export or document-generation features.

## Routes and Swagger

- `/api/client-matter-validations` → `/docs/client-matter-validations`
- `/api/client-matter-validations/batch` → same Swagger group; raw array request/response, ordered results.
- `/api/ethical-walls` → `/docs/ethical-walls`
- `/api/v1/document-authorizations` → `/docs/document-authorizations`
- `/oauth/token` → `/docs/oauth`

Read Swagger at http://admin.localhost:8000/docs/GROUP. Authenticated execution is HTTPS port 8443. Document decision requests accept only `document_version_id` and `action`; subject is the verified session or service client's bound account. Service scope is necessary but never replaces account/matter/wall/content checks. Authorization is not document download: no file-serving or AI pipeline consumes these decisions yet, and unfinished protected routes remain closed.

## Service client provisioning

Use CREATE_ACCOUNT.bat first to create a dedicated firm service account (appropriate roles; email optional). Use the admin registry to grant only required matters. In backend with the venv Python:

`python -m kestrel.service_bootstrap create SERVICE_NAME --account ACCOUNT_NAME --scopes ClientMatter.Validate EthicalWalls.Check Documents.Authorize`

The command prompts twice for a client secret of at least 32 characters; it prints no secret. `python -m kestrel.service_bootstrap revoke SERVICE_NAME` disables the client and makes issued tokens unusable. Token endpoint takes Basic credentials and form `grant_type=client_credentials`, optional narrower `scope`; lifetime 300 seconds. Keep client credentials on server integrations, never browser code. No default clients/secrets created by launch. Tokens are opaque; JWT/JWKS/Keycloak compatibility is not asserted.

## Reference parity still outstanding

The original ethical-walls-matter reference contains richer environment flag-policy administration, separate active-client/matter lifecycle controls, availability simulation, structured error envelopes/correlation, and restricted SQL read-only API identity design. Our compatibility endpoints preserve principal request/response structures but are not yet a complete replacement. **Environment authorization currently fails closed with workspaceAllowed=false** until explicitly configured policies are implemented. The AI restriction marker is conservatively Y in this interim adapter, not evidence of a configured matter flag. Do not use it to authorize real workspaces.

Additional outstanding work: versioned policy editing/publication and independent approval UI, real document ingestion/citations, immutable audit storage, AI classification proposals/tightening, tracker row persistence and filtering, validated Excel imports, approved recipient-specific workbook exports, Word/PDF reports, package approval/revocation and existing-release reconciliation. Live service clients need operational rotation, distributed throttles, abuse limits and production-grade authorization server review. No public exposure permitted.

## Tests actually run

- Full SQLite-isolated suite: **76 passed, 1 warning in 13.08s**.
- Live PostgreSQL: `KESTREL_TEST_POSTGRES=1`, pytest `tests/test_document_abac.py tests/test_administration.py`: **18 passed, 1 warning in 7.90s**. Each fixture used a generated isolated test schema, removed after testing; project registry data was untouched.
- Live PostgreSQL Alembic upgrade + schema drift check: successful; three SQL views readable, no schema drift.
- Frontend TypeScript/Vite production build passed. Browser verified tracker/report navigation and planned-state content. HTTPS certificate warning was not bypassed.
- Existing warning: Starlette/httpx TestClient deprecation. Migration tests also verify SQLite upgrade/downgrade/re-upgrade; an initial SQLite email-constraint migration failed due to dependent views, was corrected to an additive unique index, and the suite passed after correction.

Rollback: stop owned services and restore a backed-up project PostgreSQL database if reverting migration. Keep earlier SQLite data intact. Never downgrade a populated database casually. No real firm systems, confidential documents, production recall measurements, external hosting or public launch.
