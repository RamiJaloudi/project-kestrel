# AGENTS.md — binding instructions for Codex

You are the lead architect and implementation engineer for Project Kestrel. **This folder is standalone**. Do not ask for earlier exports or invent requirements from them.

## Read in this order
1. This public snapshot intentionally omits supplied third-party original briefs and forms. Read `docs/01_design/00_SOURCE_AND_SCOPE.md` for the recorded scope; obtain authorized originals separately if required for source verification.
2. `docs/01_design/00_SOURCE_AND_SCOPE.md`, `docs/01_design/01_REQUIREMENTS_AND_DECISIONS.md`, `docs/01_design/02_CONFLICTS_ROLLOUT.md`.
3. Read `docs/README.md` and `diagrams/README.md`. The numbered design, workflow, security and operations sections retain their original document identifiers.
4. `docs/08_development/prompts/01_MASTER_PROMPT.md` and current sprint prompt.

## Task hierarchy
- Ship the **design assessment** (4–6 hours suggested in the brief) and a **focused optional demo**. Do not sacrifice the legal/technical presentation to an enormous codebase.
- Keep `[BRIEF]`, `[USER DECISION]`, `[DESIGN]`, `[OPEN]`, `[DEMO]` provenance visible.
- Build tests first for security boundaries: matter assignment, ethical wall, clean-team, organization audience, unreleased draft, citation source access, admin ≠ legal SME approval, signed-in user identity.
- Use one shared policy engine in service layer. Hostname selects the UI shell but never grants authorization; disallow cross-portal account access. External cookies host-only (no wildcard domain), `Secure`, `HttpOnly`, `SameSite` and CSRF controls as appropriate. Avoid permissive CORS.
- Disallow unreviewed AI candidates from external release. Distinguish attorney legal finding approval, audience publication, and **separate antitrust counsel approval for clean-team declassification** where policy requires.
- Root administrators manage infrastructure/configuration but may NOT self-approve legal playbooks, their own changes, or automatic reanalysis, and have NO blanket privilege to view walled matter content.
- Published playbook versions immutable. Every finding binds document version, playbook version, model config, taxonomy version, original-language evidence span and reviewer status.
- Material playbook change -> immutable diff -> impact snapshot -> protected SME inbox/task -> explicit scoped SME authorization -> idempotent background rerun -> new candidates only -> attorney re-review -> separate release. No silent replacements. A rejection must have rationale and audit.
- User notifications and tasks are distinct, durable records. Viewing a notification does not approve a task. Escalations require appropriate scope and least-privilege message contents.
- No confidential source material in logs, errors, browser cache or unauthorized summaries; safe error paths and default denial.
- Permit synthetic demo local fixture/mocked AI; never claim measured production recall, accurate legal results or actual Azure service connectivity.
- Never claim German corporate/competition/FDI/UK listing rules mandatorily apply without evaluating relevant triggers; use official public sources, identify current version, escalate to counsel. Language of a contract is not governing law.
- Westlaw Next access does not include Practical Law. Never scrape or index proprietary Westlaw text without a suitable license.
- Do not connect to the Internet unless necessary to build; never commit secrets. Add `.env.example`; keep local secrets out of git.
- Do not publicly deploy until acceptance tests + consent + security checklist and user approval. Never expose `X-Demo-User` or bypass auth in public mode.

## Coding standards
Windows-friendly Python 3.11+, FastAPI/Pydantic, SQLAlchemy + Alembic, PostgreSQL production target (SQLite only in isolated tests/local prototype if needed), `pytest`; React/TypeScript/Vite. Use `api -> services -> repositories -> adapters` with dependency injection; create typed schemas and generated OpenAPI. For public demo use password hashing (Argon2id), server sessions with hashed tokens/rotating sessions, CSRF protection where needed, rate-limits/lockout, secure provisioning and password resets, session revocation. Reject any use of headers to assert user identity. Use transactions + idempotency keys for approvals/jobs and an outbox pattern for notifications/audits where useful.

## Reporting
At the start of each sprint: print chosen scope, files to change, acceptance tests, assumptions and safe rollback. After: show tests actually run, results, remaining limitations and next sprint. Do not claim functionality exists until implemented and verified. All demo interfaces and screenshots should clearly identify fictional data.

## Repository organization

Use `diagrams/` as the canonical architecture and data diagram source. Generated copies in the resource library support authenticated downloads. Documentation is grouped under numbered topic folders; consult `docs/DOCUMENT_PATH_MAP.csv` for earlier locations. Keep executable backend/frontend/deployment paths stable. Archive older diagram inputs rather than presenting them as current implementation.
