# Administration control plane — client/matter validation and ethical walls

[USER DECISION] A separate admin site backed by a SQL database and SQL view, with PostgreSQL acceptable. Interpreted "postures" as PostgreSQL. This control plane is additional to the three organization portals, not a fourth clean-team portal. [DEMO] All records must be synthetic.

## Available now

- Read-only layout: http://admin.localhost:8000/preview
- Real admin login: https://admin.localhost:8443/portal
- Dedicated Swagger: http://admin.localhost:8000/docs/validation (read-only documentation); use HTTPS port 8443 for authenticated execution.
- API prefix: `/api/v1/validation`.
- Existing START/STOP/CREATE_ACCOUNT batch controls apply to the admin site too. The local certificate now includes admin.localhost. No trust-store change or public DNS setup.

Provision a firm `root_admin` account with CREATE_ACCOUNT.bat. Sign in to the admin hostname. Register a synthetic client, open a pending matter, record a validation decision with rationale, then assign existing named accounts or block them with ethical walls. The creator receives a 30-day administration scope on the new empty matter; this is not a source-content or legal-approval override. To grant additional administrators scope, an existing eligible admin can assign another previously provisioned firm root_admin account. Account creation/roles remain trusted local-operator functions.

[IMPLEMENTED] Client registration/list; matter opening/list; pending/validated/rejected decisions; assignment activation/revocation with expiry; wall activation/removal; persisted decision history. Read views use current DB state. Historical decisions are retained. Client deletion, external authoritative conflict searches, automated legal clearance and provider integrations are not implemented. Validation here means an explicit operator decision, not certification that real conflict clearance occurred.

## SQL source

Migration `0002_validation` adds `clients`, `matter_validations`, and `administration_decisions`. Existing `matters`, `accounts`, `matter_assignments`, `ethical_walls` remain normalized source tables.

- `vw_client_matter_validation`: client/matter names and IDs, validation status and revision.
- `vw_matter_access_registry`: current active assignment and ethical-wall status for named accounts, calculated with database time.

The API reads these SQL views using parameterized, matter-scoped queries. The view itself is not the authorization mechanism. Writes go through transactionally guarded service methods to base tables, not arbitrary SQL or view editing. Mutations record actor/time/rationale and increment the matter revision; stale requests return 409. No generic SQL execution endpoint exists.

## Policy effects

- Root Admin required; external users and ordinary lawyers cannot administer the registry.
- Admin list/details/decisions require a current matter assignment and no ethical wall; pending matters can be administered but cannot be used for normal source access.
- Actor is derived from the server session; cookie/HTTPS/CSRF controls apply.
- Missing, pending or rejected validation denies ordinary matter access, including sessions issued before the change.
- Active walls override active assignments. Admins cannot edit their own assignment or wall. A walled admin cannot remove their wall or view that matter's registry detail.
- Root Admin does not authorize source-document access, legal SME approval or clean-team declassification.
- Existing legacy matters without validation remain unavailable for normal access until explicitly mapped and validated. This migration does not silently approve old matters.

## Database choice

Default local source is `.runtime/kestrel-local.db` (SQLite), a real persisted SQL database. Tables and views have SQLite/PostgreSQL migration definitions. To use an already provisioned PostgreSQL database:

```powershell
cd backend
.\.venv\Scripts\python.exe -m pip install -e ".[dev,postgres]"
# Set KESTREL_DATABASE_URL securely in your environment to the chosen
# postgresql+psycopg connection URL; never commit credentials.
# Then run START_KESTREL.bat from the same environment.
```

The launcher now preserves an explicitly provided database URL; account provisioning uses the same environment. Switching DBs does not copy accounts or records. Start migrates the selected DB, so use a dedicated synthetic database and back up any existing data first. No PostgreSQL server has been installed or connected; live PostgreSQL behavior and load/concurrency tests remain outstanding. SQLite integration and migrations are verified. DB operator credentials must remain trusted; production would need restricted DB roles, independent governance, tamper-resistant audit and actual approved wall/validation adapters.

## Verification

Frontend TypeScript/production build passed. API tests cover SQL view-backed creation/read, validation, assignment and wall persistence, stale revision rejection, CSRF/rationale validation, nonadmin/wrong-matter/walled-admin denial, own-access denial and immediate validation revocation of existing session access. Full migration upgrade/check/rollback/re-upgrade tests run as part of the suite. Browser inspected the read-only admin layout and rendered Swagger operations. HTTPS browser sign-in remains subject to the user's local certificate warning; it was not bypassed.

The preview fixture uses example labels only, performs no registry mutations and supplies no authenticated identity. Actual local database is not automatically seeded with demo users or client records. Synthetic data created by tests is isolated in temporary databases.

Final test command: backend\\.venv\\Scripts\\python.exe -m pytest -q — 63 passed, 1 warning in 9.28s (existing Starlette/httpx TestClient deprecation).
