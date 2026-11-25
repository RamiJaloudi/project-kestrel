# Sprint 1 results — 20 November 2026

## Scope and status

[IMPLEMENTED] Local account/session foundation and shared DB-backed authorization policy. Working root: outer `Freshfields_Codex_Handoff`. Nested duplicate untouched. Original assessment text, AGENTS, docs 00–18, master and S1 prompts read. JD used only for technology expectations. No old exports imported; no cloud resources/DNS/public hosting configured.

- SQLAlchemy models and frozen Alembic 0001 for organizations/accounts/roles/grants/matters/assignments/walls/clean-team memberships/server sessions/throttles/safe audit records.
- Interactive local provisioning; Argon2id password hashing, role/org validation, password reset and all-session revocation. No default credentials, automatic seeded accounts, remote signup or role headers.
- Login, me, logout, minimal portal navigation; session rotation, opaque 256-bit random tokens stored as SHA256, CSRF secret hashes, 30-minute absolute expiry, current account status/role recheck.
- Exact local host/org mapping and server-side replay checks; Secure/HttpOnly/host-only/SameSite=Strict cookies; state changes require HTTPS exact Origin and CSRF after login. No CORS grants. Loopback-only peers and public-mode startup block.
- Shared deny-first policy handles matter term/revocation, ethical walls, matter-specific named clean-team scope, privilege/audience/review/publication and independent SME predicates. Explicit scoped source grant required for client CT access.
- Authenticated business stubs still return 403; no unimplemented approval creates a job. Anonymous legacy routes remain 401. New test-only source route is defined inside the test fixture, not the app.
- No-store and safe validation/unhandled-error responses; no raw submitted password echo. Authentication/provisioning audit only; full content-access audit is not yet implemented.
- Frontend disclaimer updated to exact requested wording; visual fixture remains disconnected.

## Commands actually run

Baseline from backend:
`C:\Users\RJalo\miniconda3\python.exe -m pytest -q` -> **32 passed, 1 warning**.

The `py -3` Store launcher failed to start. Created `.venv` using installed Python 3.12. First sandbox dependency installation failed DNS; authorized elevated installation of declared dependencies succeeded. Exact tested versions are in `backend/requirements-tested.txt`; no secrets there.

Final from backend:
`.\.venv\Scripts\python.exe -m pytest -q` -> **56 passed, 1 warning in 6.52s**.

Warning: FastAPI/Starlette TestClient deprecates its httpx transport. Tests use installed httpx; no suppression or untested dependency switch. An intermediate added-test run had a misplaced test block/NameError; fixed and entire suite rerun to the final result above.

Migration tests call upgrade head, Alembic schema check, downgrade base, re-upgrade on an isolated temporary SQLite DB. All S1 tables also compile using the PostgreSQL dialect. This does **not** establish live PostgreSQL migration or concurrency behavior. No default workspace database/accounts created through migrations during verification.

## Remaining limits and public blockers

- Frontend build and browser TLS/login smoke not run. Local certificate provisioning/trust and portal DNS setup not changed. HTTPS TestClient is verified; README explains local TLS startup. Secure cookies have not been weakened to support plain HTTP login.
- No live PostgreSQL service/driver integration, multiworker load test, atomic distributed throttle, edge limits, idle-expiry policy, online self-service password-reset or MFA. CLI reset/revoke available to trusted local operator. Public mode refuses startup.
- Matter/CT provisioning UI is not present. Tests establish DB fixtures; account bootstrap assigns no matter. Policy service is covered via test-only routes; real evidence routes must explicitly call it in S2.
- Audit is basic safe DB inserts; not tamper-evident/WORM or full read/deny coverage. Retention/cleanup of sessions/throttles/audit is future work. DB operator is trusted.
- No real Entra/Intapp/iManage/M365/VDR/OCR/model provider connections. Current DB walls are synthetic local policy, not a live Intapp integration. Structured provider ports/contract tests remain future implementation.
- No source ingestion, citations, playbook CRUD/legal approvals, impact snapshots, SME inbox/reruns, attorney finding review or audience-release workflow implemented in S1. Original domain fixture helpers are not production services.
- Raw source/release policy must later include persisted classification/lineage and antitrust declassification decisions. Current predicate tests do not certify future routes.
- Public launch still requires explicit approval, isolated hosting, TLS, security review, complete P0 workflow tests and hardening. No exposure changed.

## Next sprint

S2: mock VDR manifest -> immutable document version/hash/page -> original-language exact evidence -> shared-policy source endpoint, with negative download/metadata/citation tests. Preserve Nov 24 assessment priority and refer to docs/19 for phased schedule. Do not expand into broad AI or public hosting before evidence/security gates.
