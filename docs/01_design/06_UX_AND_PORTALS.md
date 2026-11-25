# 06 — Screens / UX requirements

**One React application codebase**, three hostname-specific shells and role-specific navigation. A fourth public portal is not needed. `demo` footer on all screens; fake company names are clear.

## Firm shell navigation
1. Matter Dashboard — incoming waves, ingestion failures, coverage counters (processed, excluded, awaiting OCR/AI, reviewed, released), board deadline, pending client questions.
2. Documents — grid with type/lang/governing law (confirmed/inferred/unknown), VDR IDs/versions, provenance, clean team labels, OCR evidence and viewer with source passage highlight.
3. Risk Review — candidate findings, source viewer side panel, severity, correction/reject/confirm rationale, audit.
4. Reports — reviewed-only board-ready draft, source citations, caveat/coverage statements, export.
5. Q&A — permission-filtered, cited queries; cannot search across restricted docs on unauthorized identity.
6. Release Desk — target Halden/Castlegate, privilege/clean-team status, sanitized artifact, two-step approval, revocation log.
7. **Root Admin** — user/org/matter admin (only permitted metadata); Playbook Management, playbook version compare/test/propose/publish/archive (only after independent SME approve), notification-routing policies, restricted audit. Not an override of ethical walls.
8. **Legal Governance Action Center** — notifications, work queue, exact diffs, impact assessments, authorization decisions and progress/reconciliation.
9. Clean Team — visible only to named active members; restricted documents/findings and allowed clean-team counsel operations.

## Halden client shell
Dashboard, approved released findings, approved draft reports, comments/questions, own document uploads, named clean-team area only for eligible persons. Does not display confidential firm drafts or privileged data never released. Explicit exposure control on uploaded client docs (not auto-share with bank).

## Castlegate bank shell
Released, approved, sanitized financial/commercial findings only, relevant comments, optional questions solely over bank-approved artifacts, audit for own actions where permitted. No internal legal advice or restricted source documents.

## Playbook management screen
Table search/filter: name, version, jurisdiction, language, document types, owner, status, effective date, last approved; actions Create, Edit Draft, Duplicate, Test, Compare, Submit Legal Approval, Publish (after independent approval), Retire/Archive. Soft-delete only unpublished drafts if allowed; keep published for audit.
Editor tabs: General, Applicability, Detection Rules, Exclusions/False Positives, Evidence/Citations, Risk/Severity, Authorities, Synthetic Test Cases, AI schema/prompt, Governance Approvals, Diff/Audit.
**Do not let root admin edit a published definition in place.** Draft new version; SME approval and publication required.

## Legal SME Action Center — must be interactive
Header: unread/awaiting/action/escalated counts. Queue filter by task owner, urgency, matter, playbook, status. An Action Center notification opens a task, **not an auto-approval**. Task detail tabs:
- **Rule Changes** — exact before/after for each rule: stable rule ID, field path, old/new value, added/removed/modified tag, semantic change classification, provenance.
- **Impact** — eligible affected document versions, reviewed findings, approved findings, released findings, clean-team subsets (only aggregate for non-cleared users), source accuracy + snapshot generated at. Example sample COUNTS (FAKE): 1240 impacted / 186 approved / 32 released / 11 CT; these counts must be generated from fixture/DB, not hardcoded after backend is implemented.
- **Decision** — scoped all-eligible/unreleased-first, mandatory rationale, stale snapshot indicator, approve/reject, independent role/clean-team checks. Reject may require revised scope, not blanket stop critical corrections.
- **Jobs & Reconciliation** — queued/running/completed failures, old-vs-new candidates, attorney re-review, released corrections flagged.
- **Audit** — event type/actor/time/rationale and immutable versions with permitted metadata only.

## Workflow state consistency
`draft -> tested -> legal_review_requested -> legal_approved -> published -> superseded/archived` for playbooks.
`impact_ready -> awaiting_sme -> approved/rejected`; if approved: `queued -> running -> results_ready -> attorney_revalidation -> completed`, plus `failed/cancelled/superseded` with reasons.
Notifications: `unread/read/acknowledged/resolved`, escalation tracked separately; tasks `open/claimed/awaiting_decision/escalated/closed`.

Accessibility: labels, WCAG-aware focus states, plain-language legal copy, keyboard navigation, clear errors, pagination and search for large queues; no client-side-only authorization.
