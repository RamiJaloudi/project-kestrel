# Confirmed logging, governance, Resources and AI scope — 20 November 2026

[USER DECISION] START launches backend CMD consoles visibly. Diagnostics and manual restart; no automatic restart. Capture startup/build failures, exceptions, readiness failures and unresponsive services. ALL logs are retained without automatic deletion; do not interpret retention as a verified judicial/antitrust records schedule.

[USER DECISION] Own activity plus designated matter-scoped auditors. Clean-team-wide exports only for an explicitly authorized clean-team auditor or antitrust counsel with active named matter/scope membership. Root Admin has no override. Separate administrative, Legal SME, clean-team and ordinary access categories.

[USER DECISION] JSONL, CSV and HTML exports first; PDF next. Export packages include applied filters, event IDs, timestamps, exporting identity, schema version and SHA256 manifest. Immutable-storage adapter in the next implementation phase; current local append-only guards/manifests are not WORM storage.

[USER DECISION] Sanitized technical logs; potentially sensitive incident evidence must be captured separately under restricted access. Do not log credentials, tokens, prompts, passages or exception messages/locals in ordinary logs. Restricted-evidence workflow is separate follow-on work, not permission to capture it in general files.

[USER DECISION] Synthetic legal playbooks with public-primary-source research, independent Legal SME approval and no licensed Westlaw/Practical Law ingestion. Distinct security/privacy, conflicts, and legal approvers. Root Admin can prepare own drafts but cannot approve them. A Partner title is not an authorization grant.

[USER DECISION] OpenAI API for personal synthetic demo in next phase. Configure secrets outside chat/repository; no automatic paid calls. No enterprise Freshfields approval inferred. Full pipeline remains phased: OCR/ingestion, multilingual classification, ABAC, extraction, lawyer review/release, trackers/reports, impact/reanalysis, monitoring.

[USER DECISION] Resources tab in each portal and administration, with role-specific workflow guides and downloads. Clean-team guide visibility depends on active named scope. Engine status must distinguish actual implementation, synthetic baseline, configured/unconfigured and planned.

Prior confirmed requirements remain: client/matter business uniqueness uses the number pair (leading zeros preserved); composite-number registry migration still outstanding. PostgreSQL is authoritative. DB tracker records, validated Excel import, approved audience-specific exports, Word/PDF report packages and independent package approval are still required.

## This increment's files and acceptance

Launcher/supervisor/console/build wrappers; diagnostics module; audit schema, guard triggers, scoped query and export API; governance schema/service/editor; Resources API/UI; synthetic starter fixture and official-source pointers. Tests: sanitize exceptions, audit ownership/scopes, CT expiry, export digest equality, independent approvers, exact tested hashes, published immutability, append-only SQL audit, environment enforcement and live wall denial. SQL migrations/check/rollback and frontend build. Rollback by stopping owned processes and restoring backed-up dedicated project DB; keep logs, evidence and prior versions. No automatic retention cleanup or public deployment.
