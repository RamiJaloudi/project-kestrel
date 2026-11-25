# Implementation plan — 20 November 2026

[BRIEF] Original assessment text read in full, including practicalities and panel requirements. No production access or public hosting permission inferred. [USER DECISION] November 24 submission; standalone handoff only. Working root is the outer handoff folder; nested duplicate is not a dependency.

## Ten architectural decisions
1. Reuse approved firm tools/M365 for real Week 1; new external application remains security gated.
2. One API and shared service policy; three portal hosts select organization context, never authority.
3. Local provisioned accounts, Argon2id, opaque hashed server sessions; no identity headers.
4. Recheck current roles, assignments, walls and clean-team terms on every request.
5. Deny unknown labels/actions/hosts; admin is not a matter-content or legal-approval override.
6. PostgreSQL-compatible SQLAlchemy types and Alembic migrations; SQLite isolated local/test execution.
7. Lawyer validation, audience release and any required antitrust declassification are distinct gates.
8. Published legal versions and historical findings immutable; independent SME approval required.
9. Material changes create scoped impact tasks; explicit SME authorization precedes any rerun.
10. Versioned original-language evidence supports batch coverage; RAG is a separate scoped query path.

## Five external questions
- Seller/VDR owner: which exports/APIs and processing rights are permitted?
- Knowledge lawyer/German counsel: initial taxonomy, evidence rubric and materiality thresholds?
- Deal/antitrust counsel: named clean-team roster and bank-safe release conditions?
- Security: approved M365 configuration, model endpoints and external onboarding requirements?
- GC/records counsel: board coverage expectations, signing freeze and retention/hold/deletion scope?

## S1 file and test plan
`models.py`, `database.py`, Alembic: organizations/accounts/roles/grants/matters/assignments/walls/CT/sessions/login throttles/audit. `repositories/identity.py`, `services/auth.py`, `services/policy.py`, `api/auth.py`: DB-backed identities, login/session rotation/logout, CSRF, exact host mapping, deny-first policy. `bootstrap.py`: local interactive account provisioning without default credentials. Existing business routes remain closed. Tests cover login, invalid credentials, throttling, revoked/expired sessions and accounts, wrong portals, forged headers, CSRF, live role/grant revocation, walls, expired CT, bank privilege, unknown labels and admin/self-approval boundaries. Migration upgrade/downgrade smoke and PostgreSQL DDL compilation.

## S2 file and test plan
Proposed `schemas/evidence.py`, `repositories/documents.py`, `services/ingestion.py`, `services/evidence.py`, `adapters/vdr.py`, `api/documents.py`, migration `0002_evidence`, tests `test_evidence.py` and `test_ingestion_access.py`. Mock manifests, immutable source/version/page hashes, original-language spans, explicit classifications and policy-gated source reads. Verify duplicate imports, German quotes, offset/page/version mismatches, traversal/size limits and denied source metadata. No real OCR/vendor connection assumed.

## Milestones / scope lock
Nov 20: S0/S1 foundation and tests. Nov 21: S2 evidence, preserve time for HLD/LLD and partner note. Nov 22: narrow S3/S4 lawyer review and recipient release if P0 gates pass. Nov 23: prioritize assessment narrative, limited S5 governance only if feasible, rehearse and record actual evidence. Nov 24: submission review/disclosure; no automatic public deployment. S6/S7 breadth deferred rather than risking assessment quality.

## Assumptions and rollback
[ASSUMPTION] Local single-process development only; persistent DB throttling supplements future edge limits. HTTPS local aliases (`firm.localhost`, `client.localhost`, `bank.localhost`) supported by test client; browser TLS proxy configuration deferred. Plain HTTP loopback may be used for health/docs only; secure auth cookies are not weakened. [DESIGN] Public mode fails startup until separately implemented and approved. No existing DB is migrated automatically. Roll back source changes from review and restore a backup DB; use Alembic downgrade only on disposable local data. No infrastructure/DNS changes. First reviewable change is schema + auth/policy regression tests, followed by minimal routes. No git commit presumed without a repository.
