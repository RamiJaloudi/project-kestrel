## Updated local launcher

Use the project-root START_KESTREL.bat / STOP_KESTREL.bat / CREATE_ACCOUNT.bat. See ../docs/21_LOCAL_PREVIEW_AND_CONTROLS.md for three portals, grouped Swagger, HTTP preview and HTTPS login. These controls use .runtime/kestrel-local.db; manual commands below use the configured working-directory database unless overridden.

# S1 local authentication and policy foundation

[IMPLEMENTED] Real local accounts, Argon2id, server sessions with hashed tokens, 30-minute expiry, rotation on login, logout/revoke/reset, host-bound cookies, CSRF checks, fixed-window persistent login throttles, current DB role/matter/wall/clean-team checks, safe validation errors and no-store responses. No default credentials or remote registration. One shared policy service; business routes remain closed.

## Windows setup

Run in this backend folder. If the Windows Store `py` alias is unavailable, use an installed Python 3.12 executable to create the venv.

```powershell
py -3 -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -e ".[dev]"
python -m alembic upgrade head
python -m kestrel.bootstrap create your-local-admin --org firm --roles root_admin
python -m pytest -q
uvicorn kestrel.main:app --host 127.0.0.1 --port 8000 --reload --no-proxy-headers
```

The provisioning command prompts twice for a unique password of at least 15 characters. No password is passed on the command line. It assigns **no matter access**. Matter/clean-team assignment management UI and workflows are later work; tests create isolated fixtures. Local operator DB access is trusted; it must not be exposed to portal users.

Default DB is `sqlite:///./kestrel-local.db`. Set `KESTREL_DATABASE_URL` in PowerShell to override; `.env` is a template and is not automatically loaded. `KESTREL_ENV` must be `LOCAL`. API startup never creates tables or seeds users. PostgreSQL driver/server integration is not installed or verified; migration/DDL portability is tested separately.

## Local HTTPS authentication

HTTP `http://127.0.0.1:8000/health` and `/docs` work for local inspection. Login requires HTTPS and an exact same-origin `Origin` header; secure cookies are never relaxed for HTTP. Use an independently trusted local certificate containing `firm.localhost`, `client.localhost`, `bank.localhost`, and run:

```powershell
uvicorn kestrel.main:app --host 127.0.0.1 --port 8443 --ssl-keyfile C:\path\local.key --ssl-certfile C:\path\local.pem --no-proxy-headers
```

Certificate provisioning/trust changes have not been performed. Resolve those aliases to loopback using local DNS/hosts if your browser does not do so. Browser TLS smoke testing remains outstanding. Tests use HTTPS TestClient requests and perform no network calls. Frontend login/me/logout is now connected; browser certificate acceptance remains a user step.

`firm.localhost` maps to firm, `client.localhost` to Halden, `bank.localhost` to Castlegate. `localhost` and `127.0.0.1` are firm aliases. Public proposed domains are deliberately rejected. Cookies are Secure/HttpOnly/SameSite=Strict, host-only, with `/` path; the server also binds sessions to exact host. Do not enable forwarded-header trust or expose the workstation.

## API flow

- `POST /api/v1/auth/login`: JSON `username`, `password`; exact HTTPS Origin required. Returns CSRF token and host-only cookie.
- `GET /api/v1/auth/me`: verified current ID/org/roles, no password or token hashes.
- `POST /api/v1/auth/logout`: cookie, exact Origin, `X-CSRF-Token` from login. Revokes server session.
- `GET /api/v1/portal/navigation`: only account navigation; no implemented business workflows advertised.
- Protected playbook/inbox/reanalysis stubs: anonymous 401; authenticated requests remain denied (403). POST also requires CSRF. No legal approval or queue action occurs.
- `python -m kestrel.bootstrap revoke USERNAME`: revoke all sessions.
- `python -m kestrel.bootstrap reset USERNAME`: interactive password reset and revoke all sessions.

Login throttles permit ten attempts per normalized username AND loopback peer per 15 minutes, including successful attempts. Persistent account/peer buckets are for one-process local use; atomic distributed throttling, cleanup/retention, edge limits and concurrent load tests are outstanding public gates. Session tokens are cryptographically random and only SHA256 hashes are stored; there is no signing secret to configure.

## Evidence and limitations

`tests/test_auth_policy.py` adds a test-only source route to exercise real auth dependencies and policy denial end to end; this route is **not** shipped. Documents/releases/playbooks/tasks are not yet persisted or served. Policy predicates are foundations, not proof that future routes will enforce themselves. Intapp/Entra/M365/OCR/AI remain unconnected. Existing `domain.py` is a historical pure fixture helper; new routes must use DB-backed services.

Audit records currently cover provisioning/login/logout/reset/revoke only, with safe metadata. WORM/tamper evidence, comprehensive denied-content auditing and audit UI remain future work. No actual data, default accounts, production recall claims, measured throughput or public deployment. The frontend provides real sign-in plus separately labeled design fixtures; unimplemented business workflows stay closed.

Migration rollback: back up any local DB first; `python -m alembic downgrade base` destroys S1 tables and is appropriate only for disposable fixtures. Test suite checks upgrade/schema drift/downgrade/re-upgrade. PostgreSQL DDL compilation is not a live PostgreSQL test.

