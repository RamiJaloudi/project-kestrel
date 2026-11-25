# Local previews and Windows controls

[IMPLEMENTED] One FastAPI application, three host-selected organization shells and a central launch page. The compiled React application and locally bundled Swagger assets are served from the same origin. No public sites, DNS records, hosting subscriptions or machine certificate trust settings are created.

## Double-click controls

From `C:\Freshfields-Takehome`:
- `START_KESTREL.bat`: builds the frontend, applies migrations, creates a local self-signed certificate if absent, launches hidden local listeners and opens the launch page. Checks readiness and refuses occupied ports. A second start opens the existing preview instead of duplicating it.
- `STOP_KESTREL.bat`: stops the recorded process tree only after matching PID start time, executable and project root. It does not kill all Python/node processes or delete your accounts/database.
- `CREATE_ACCOUNT.bat`: interactive create/reset/revoke, with no default credentials. Run Start once before creating accounts so the schema exists.
- Inner project also contains `STATUS_KESTREL.bat`.

The same controls exist inside `Freshfields_Codex_Handoff`. Nested duplicate handoff is untouched. Batch wrappers invoke Windows PowerShell with process-scoped ExecutionPolicy Bypass; no persistent policy change. First setup needs Python 3.11+ and Node compatible with Vite 8 (20.19+ or 22.12+; verified Node 24.18). Missing dependencies may require registry access. The checked-in npm lockfile and tested Python requirements snapshot support reproducibility.

## URLs

| Surface | Read-only/design preview | Swagger |
|---|---|---|
| Launch page | http://localhost:8000/ | http://localhost:8000/docs |
| Firm | http://firm.localhost:8000/preview | http://firm.localhost:8000/docs |
| Halden | http://client.localhost:8000/preview | http://client.localhost:8000/docs |
| Castlegate | http://bank.localhost:8000/preview | http://bank.localhost:8000/docs |

Each host also has `/portal` (sign-in page) and `/docs/auth`, `/docs/portal`, `/docs/admin`, `/docs/governance`. Group-specific schemas are under `/openapi/{group}.json`; all routes remain one backend. Documentation is not a permission grant. Admin/governance business routes remain closed.

**Real authentication:** change protocol/port to `https://HOST:8443/portal`; Swagger can execute authenticated requests at `https://HOST:8443/docs`. Cookies are Secure/HttpOnly/host-only and bound to the exact hostname. HTTP port 8000 is read-only: all authenticated API paths reject requests there. Its form cannot submit credentials. Neither listener binds a public interface; proxy-header trust is disabled. Local `.localhost` browser resolution was verified in the embedded browser; no hosts file edits were made.

The self-signed certificate has SANs for all local aliases. A browser security warning is expected at each HTTPS hostname. The user must handle that warning; Codex did not bypass it, install trust, or weaken validation. Browser HTTPS login is not claimed verified; backend HTTPS TestClient login/CSRF tests pass. Embedded browser read-only portals and Swagger rendering were verified.

## Account provisioning

`CREATE_ACCOUNT.bat` prompts for action, username, organization and role list; Python securely prompts/confirm passwords. Valid examples:
- organization `firm`: `root_admin`, `firm_lawyer`, `legal_sme`, `antitrust_counsel` (space-separated if needed).
- organization `halden`: `client_user`.
- organization `castlegate`: `bank_analyst`.

Use distinct accounts for author/admin and independent SME. Root admin confers no matter-content or legal approval authority. Bootstrap assigns no matter grants; those workflows are future work. No passwords or accounts were generated automatically for this preview.

The launcher and account tool use `.runtime/kestrel-local.db`, independent of the earlier ad-hoc backend working-directory DB. `.runtime` also stores TLS material, safe server logs and lifecycle PID state; excluded from git. Stop preserves it. Trusted local operator controls these files. No email reset service exists; local reset revokes sessions. Login page session reload requires re-authentication to renew its in-memory CSRF token. Swagger login stores CSRF only in page memory for subsequent state-change requests.

## Design previews versus implemented behavior

`/preview` serves static synthetic interface fixtures without making an authenticated identity or granting API permissions. Firm's Legal Governance tab preserves the supplied illustrative diff/impact/decision UI; its actions are explicitly visual only. Other unfinished sections show status rather than fake live results. Organization portals connect real login/me/logout over HTTPS. Restricted documents/findings/releases/playbook publication/SME inbox/reanalysis are not yet implemented. The UI is not a production due-diligence platform.

## Verification — 20 November 2026

- Baseline S1: 56 tests passed.
- Final `backend\.venv\Scripts\python.exe -m pytest -q`: **58 passed, 1 warning in 6.92s**. Warning is the existing Starlette/httpx TestClient deprecation.
- `npm.cmd run build`: TypeScript + Vite 8.3.8 + local Swagger asset copy passed.
- After starter Vite vulnerabilities were identified, patched dependency install reported **0 vulnerabilities**. npm audit advisory service was accessed for that check.
- Lifecycle: start, stop both owned listener trees, restart, status and duplicate-start protection executed successfully. PowerShell scripts required execution outside the sandbox's local network restrictions; no Windows elevation/UAC or public binding was configured.
- Embedded browser verified launcher, all three organization login shells, firm design/governance navigation and grouped Swagger API definition rendering. Fixed an initial Swagger interceptor error on schema GETs and rechecked its rendered operations.
- No real firm integrations, public deployment, browser security-warning bypass, production performance claim or default credentials.

Rollback: Stop, revert preview source changes in review, and keep/restore a backup `.runtime` database. Remove generated runtime files only if intentionally discarding your local accounts; stop does not do that. See docs/19 for the remaining implementation sprint plan.
