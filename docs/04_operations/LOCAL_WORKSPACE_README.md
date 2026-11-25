# Project Kestrel — local candidate demonstration

Updated 24 November 2026. This standalone repository contains the assessment design and the optional synthetic application. Do not import older V1/V2/V3/V4 exports. The assessment brief remains authoritative; the prototype is not a Freshfields service or a production deployment.

## Run locally

Double-click `START_KESTREL.bat`. It starts PostgreSQL, the shared HTTPS API/portals, HTTP redirector, synthetic worker and health monitor in labeled consoles. It opens Portal Home at https://localhost:8443/ and the configured database tools. Open the Firm, Halden, Castlegate or Administration portal and grouped Swagger from Portal Home. Each portal verifies its own authenticated session and data permissions.

Use `STOP_KESTREL.bat` to stop owned services while retaining data and logs; `STATUS_KESTREL.bat` checks status. Credentials remain in the ignored private `.env` and local credential exports. `CREATE_ACCOUNT.bat` provisions a local account. Do not expose these services or configuration publicly. See `docs/04_operations/21_LOCAL_PREVIEW_AND_CONTROLS.md` and `docs/04_operations/30_HTTPS_CONSOLES_AND_QUEUE.md`.

## Current build

Working local baselines include authenticated accounts/profile, PostgreSQL and SQL views, centralized document ABAC and person/client/matter walls, scoped OAuth, governance approvals, synthetic document intake/OCR/reader, cited findings and lawyer decisions, audience releases, reports/board packs, client collaboration, trackers, checklist/task/SLA coordination, audit exports, signing/closing controls and verified local database recovery. Resources in each portal describes permitted workflows and implementation limits. `/preview` is a separate static design surface.

Latest verified local database: **0038**, including source/passage labels, sanitized disclosures, BM25/semantic retrieval, exact financial evidence, saved server-side table queries, organization/matter bank gates, review-intelligence profiles/alerts, durable bounded LangGraph report runs and a versioned agent registry. Each increment was rehearsed on a restored encrypted backup; source identities and previous records were preserved. The new internal financial context/evidence/decision/staging records preserve underlying fact restrictions. See docs/58 through docs/83 for actual checks, the acceptance audit and limitations.

DDR Runs uses reviewed finding versions, private opaque checkpoints, durable deduplicated attempts, independent exact-report review and separate audience approval. Edited report versions require new internal review; old approved packages remain retained. The offline path and the live graph adapter are implemented. Live use requires an enabled private OpenAI key, independently published stage profiles, current processing permission and the shared aggregate $2/run and $10/month ledger. The SDK/provider path has been tested through mocked HTTP, including PostgreSQL; a real paid-provider acceptance run has not been performed in this build.

Resources contains role-specific downloadable workflow guides and current engine status. Inventory and financial grids provide server-side paging/filtering/counts, internal metadata exports and governed saved configurations. Review Intelligence groups only permitted rows and separates delay, legal and financial signals. Bounded XLSM, XBRL/iXBRL and EML staging preserve exact evidence without executing macros, formulas or document instructions.

Remaining work includes broader legacy conversion, controlled candidate promotion, instrument-aware query/reconciliation integration, additional runnable specialist roles, broader operational grids, final live-provider verification and external immutable storage/operational assurance. A separate PUBLIC_DEMO owner/proxy gate and closed Azure template are prepared; actual target security, services, DNS/TLS and owner approvals remain pending. See docs/05_validation/80_GATE_ACCEPTANCE_STATUS.md for the precise active-prompt gaps. An installed registry entry does not implement a specialist. There is no production-capacity or legal-accuracy claim. Permission-aware search remains distinct from batch diligence.

## Assessment and development workflow

1. Read all five pages of `source/Legal Solutions Architect - Assessment Brief.docx`, `AGENTS.md` and `docs/01_design/00_SOURCE_AND_SCOPE.md`. Distinguish brief requirements, confirmed decisions and proposed design.
2. Follow `C:/Freshfields-Takehome/Prompts-repository/CURRENT_IMPLEMENTATION_PLAN.md` in order. Review existing implementations and checkpoints before changing a gate; retain source versions, approvals and access controls. Do not replay the initial scaffold sprint over the working application.
3. Start the application with the supplied launcher. Use Resources and authenticated Swagger to test actual behavior. Demo data and approvals are distinct: startup never impersonates an independent legal approver.
4. Process local Wave 2 documents through normal intake when ready. `fixtures/wave2/financial-evidence-synthetic.txt` is an additional local financial exercise; it is not automatically ingested. Existing synthetic waves remain under `data/synthetic_waves`.
5. Assemble the partner note, architecture, rollout/conflict decisions, presentation and AI-assistance disclosure using `docs/01_design/16_DELIVERY_AND_PRESENTATION.md` alongside development.

## Two deliverables and rollout

The authoritative design assessment concerns a fictional M&A matter: first wave next week, 12,000 documents / approximately 400,000 pages over six weeks, approximately 20% German, Halden board in five weeks and signing in ten. A new external-login application's security review takes 4–6 weeks. Real first-wave operations should reuse approved firm tools/M365 guest access; this prototype does not satisfy that review.

The optional Windows-first application uses one shared API and organization-specific portals. It uses synthetic data and mock enterprise integrations. A public/Azure demonstration remains a separate permission and hardening gate. The current personal Azure demo target is approximately $100/month. The proposed Windows VM, disks and IP have a verified $79.66/month base estimate; usage, backups, AI and taxes remain additional considerations. This does not define the real-firm production budget.

## Current decisions
- Development: Windows local first; controlled public synthetic demo later if approved.
- Personal Azure demo target: approximately $100/month, Windows Server with local PostgreSQL; actual quote and public hardening/launch approval remain gates.
- Three portal entrypoints: firm / Halden / Castlegate. No separate clean-team portal. A cross-portal centralized policy engine is mandatory.
- Real user accounts and passwords (public demo); avoid header-based identities and role-switch security.
- Root Admin playbook CRUD/draft operations; **independent Legal SME approval for legal publication**, no self-approval.
- Material playbook edits trigger an automatic impact assessment, persistent SME inbox and **SME-approved rerun only**; historical results immutable; new findings require lawyer review and audience release approval.
- No real iManage, M365, Entra or Intapp subscription for your prototype. Provide mock adapters with stable interface contracts.
- Retrieval and batch clause review are distinct; multilingual original-language citation; governing law ≠ document language.
- Westlaw Next available but Practical Law templates are not included. Never import proprietary Westlaw full text into Codex/RAG without permission; use own research notes and authorized public primary law.

## Source-of-truth order
`source/brief` > `docs/00` interpreted requirements > confirmed user design decisions in `docs/01` > proposed design docs > optional `reference/previous_design_notes` (historical, non-authoritative). **Never demand older ZIPs.**

## Guardrails
- Fictional and synthetic documents only. No actual VDR integrations, actual law-firm data, or unauthorized branding.
- External login portals require full security review in the real matter; cannot be promised next week.
- Public candidate demo: do NOT expose dev scaffold or your main workstation; require genuine login and authorization, HTTPS, throttling, secrets protection, audit, no test bypasses, manual approval to go live.
- [USER DECISION] Use neutral Project Kestrel branding and fictional data. Keep candidate-demo/non-affiliation context in project documentation; do not restore repeated UI disclaimers.


Admin registry: https://admin.localhost:8443/portal ; Swagger https://admin.localhost:8443/docs/validation. The separate /preview route is static. See docs/02_workflows/22_ADMINISTRATION_REGISTRY.md for SQL views, permissions and PostgreSQL option.

Current database: dedicated local PostgreSQL managed by the batch controls. See docs/05_validation/23_CONFIRMED_ABAC_TRACKERS_REPORTS.md and docs/05_validation/24_ABAC_FOUNDATION_RESULTS.md for confirmed requirements, new Swagger groups, tests and incomplete reference-parity features. Earlier SQLite instructions are historical/fallback only.

Latest: START now opens CMD backend consoles (may be hosted by Windows Terminal). Logs are retained in .runtime/logs with no automatic deletion. Admin has Policies & playbooks, Audit reports and Resources. See docs/05_validation/25_LOGGING_GOVERNANCE_DECISIONS.md and docs/05_validation/26_LAUNCHER_AUDIT_GOVERNANCE_RESULTS.md for current scope, roles and limits.

Current startup: Portal Home only (https://localhost:8443/), plus backend CMDs, PostgreSQL, pgAdmin and psql. Start/Stop read the private .env. Requested fictional interviewer accounts and compact styling are documented in docs/04_operations/29_PORTAL_HOME_AND_INTERVIEW_SETUP.md. Do not commit or publish .env.

Current runtime, certificate trust, five component consoles, synthetic queue and retained diagnostics: docs/04_operations/30_HTTPS_CONSOLES_AND_QUEUE.md (supersedes earlier launcher descriptions).
Numbered client/matter registry, 33 role-testing accounts and shared-password operator setup: docs/02_workflows/31_NUMBERED_REGISTRY_AND_DEMO_ACCOUNTS.md. Username/role directory: .runtime/demo-accounts.json; configured passwords remain in .env.
Remembered portal sign-in, saved usernames and browser password-manager support: docs/02_workflows/33_REMEMBERED_SIGN_IN.md. Select Remember for 30 days; Sign out revokes the session, and Forget saved username clears the saved name.


## Current frontend and service recovery

The user-selected square Freshfields wordmark and gold/brown/charcoal palette are shared across the frontend. Home, authenticated Firm Documents and Administration were browser-verified; screenshots are in `delivery/frontend_preview`. Start builds and serves these assets, so no separate branding service or extra browser tab is needed. LOCAL supervision now tracks Python processes directly, retains safe bootstrap/exit events and requires fresh run-bound heartbeats for all five real components. Seven focused supervisor checks and a coordinated local restart passed; data and approval records were retained.
