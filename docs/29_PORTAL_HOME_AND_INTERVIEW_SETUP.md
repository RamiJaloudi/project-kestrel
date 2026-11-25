# Compact Portal Home and requested fictional interview accounts

## Confirmed behavior (supersedes launch-all startup)

START_KESTREL.bat opens only http://localhost:8000/ as the initial browser page. It still starts PostgreSQL and visible backend CMD consoles and automatically opens/reuses pgAdmin and the project psql operator console. Portal Home links open real HTTPS organization login pages, grouped Swagger and Resources in new tabs. Read-only previews are tucked into connection help. Stop closes only owned backends/psql and the project PostgreSQL, retaining DB/logs and leaving browser tabs and pgAdmin open.

Frontend now uses compact enterprise spacing, tighter forms/tables, smaller headings, readable body text and a collapsible sidebar. Main page shows readiness and database connection status. Authentication and backend policy boundaries are unchanged; Portal Home never grants a role or impersonates a user.

## Private .env and accounts

Both inner Start and Stop batch files explicitly point KESTREL_ENV_FILE to the handoff-root `.env`. Values are read literally, without executing shell content. The file is git-ignored and restricted to the local Windows owner. Startup never prints values. `prepare_demo_env.py` generates a strong shared interview password only when missing and preserves existing values. Backend DB rows store independent Argon2id hashes, not plaintext passwords.

Requested accounts (email spelling preserved in .env; login is case-insensitive):
- Chris.MADDEN@freshfields.com.fictonal — firm legal_sme.
- Sumeet.Josh_external@freshfields.com.fictional — firm root_admin.

The shared password is KESTREL_INTERVIEW_PASSWORD in `.env`. DB values are KESTREL_DB_* and KESTREL_DATABASE_URL. The password is not embedded in Portal Home or browser JavaScript. Portal login remains genuine; no auto-login or role-switch bypass. The shared password is an explicitly requested synthetic-demo convenience, not evidence of independent human identity.

A clearly labeled, validated **synthetic interview matter** is created once and assigned to those two accounts for 30 days. No client source data, privileged advice, clean-team membership, Security or Conflicts approval grants are seeded. Root Admin cannot legally approve; Chris cannot self-approve their own playbook. Subsequent startups verify the accounts without silently changing their roles/passwords or restoring revoked matter grants. If an existing account's role/password differs, explicit operator review/reset is required. A missing fixture marker is not a general migration of real deal data.

## Database tools without password entry

`configure_pgadmin.py` writes a protected libpq passfile sourced from `.env` and imports an additional server named **Kestrel interview demo (.env credentials)** into the installed desktop pgAdmin configuration. Existing server registrations are preserved; `--replace` is never used. Subsequent starts refresh the passfile and do not duplicate the registration. A previously open pgAdmin tree may require Refresh to show the new entry; select that entry rather than an old connection using 5432. Host 127.0.0.1, port 55432, database kestrel. psql also obtains credentials locally without command-line passwords. A pgAdmin vault/master-password prompt, if configured by its owner, is distinct and is not bypassed.

Official import format and password-file connection parameters were checked against https://www.pgadmin.org/docs/pgadmin4/latest/import_export_servers.html and the installed pgAdmin source. Password fields are not imported into server JSON; ConnectionParameters.passfile references the protected local file. No actual password values appear in registration metadata or logs.

## Azure handoff

`.env` is sensitive: share only through a private secret-transfer mechanism if needed, never publish/commit it. `.env.azure.example` is a non-secret migration template. Azure requires separately configured host/user/password/SSL, application secrets and deployment hardening. Copying localhost settings is not an Azure deployment. Local pgAdmin automation deliberately accepts loopback DB setup only. No Azure resources, public hosting, external accounts or email messages were created.

## Verification

- Full isolated suite: **84 passed, 1 warning in 16.51s**. Existing Starlette/httpx TestClient deprecation.
- Actual PostgreSQL: both requested users authenticated over HTTPS TestClient; correct separate roles and shared password verified without outputting it.
- New fixture tests verify idempotent account creation, distinct salted hashes, scoped assignments, and literal .env parsing.
- Native psql with password prompting disabled connected using only the generated pgAdmin passfile. Dedicated pgAdmin registration count is exactly one.
- Generated DB/interview secrets absent from built frontend and retained startup/diagnostic logs.
- Production frontend build passed. Browser verified the compact four-card Portal Home, all Swagger links, live service pills and sidebar collapse.
- Actual Stop→Start passed with .env import, account verification, database tools and only Portal Home opened. First Windows PowerShell 5 parsing attempt hit an overload incompatibility; changed to explicit delimiter indexing and reran successfully.

No credential values are included in this document. Existing records/logs are retained. Legal playbook approval, clean-team restrictions, pending engine work and deployment gates remain in force.
