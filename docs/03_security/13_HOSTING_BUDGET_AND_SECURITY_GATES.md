# 13 — Local and public synthetic demo, budget and release gates

[USER DECISION] Develop on Windows locally; public authenticated access desired; $50/month target. Three domains are **proposed**, DNS and domain control unverified. No Freshfields access/permission to publish a project-branded prototype confirmed.

## LOCAL
- Python 3.11+ virtualenv, FastAPI bound `127.0.0.1`, PostgreSQL optional with SQLite local-only first steps, React/Vite localhost, seeded synthetic docs/users, `.env` local and excluded. No real firm data. Simple API and UI scaffolds are NOT a public app.
- If Docker Desktop available, optional PostgreSQL/Redis locally; Docker is not required for initial coding. No need for Windows Server until deployment decision.

## PUBLIC DEMO GATE (STOP by default)
1. Explicit candidate/recruiter permission for an optional external hosted *synthetic* prototype, if required by assessment/firm instructions. Ensure no deception or affiliation claims, and no actual branding.
2. Dedicated isolated deployment environment, not home workstation directly exposed. Options: inexpensive managed app platform if actual quote fits budget, or isolated VM with outbound-only protected tunnel; no port forwarding of main Windows PC. Public access might exceed $50 once OCR/model API/storage/egress included.
3. Real authenticated accounts + Argon2id, unique credentials, secure provisioning, host-only cookies, CSRF/rate limit/lockouts, password reset as needed, no header impersonation; hardened reverse proxy HTTPS and exact-host routing.
4. Default deny role/matter/wall/clean-team/bank checks proven with live API negative tests, including direct URL, document downloads, RAG and task notification leakage.
5. Security scanning, logs without secret/client text, backups, fake data proof, alerts/spending limit, deactivate/revoke public sessions, documented teardown and cost alerts.
6. User authorizes public launch only AFTER passing gates. No automatic Codex deploy without separate explicit approval.

## Budget accounting
Track compute, DB, object storage, backup, SSL/domain/tunnel, model tokens, OCR pages and egress; hard budget alerts + optional prepaid credits. Do not promise $50/month for production-scale 400k pages. Design is scaled; demo workload is small.
