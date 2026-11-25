# Recovery increment 1: board priorities, lawyer correction and registers

[USER DECISION] Proceed with the requirements-led recovery in docs/37. [BRIEF] Immediate business value is a reviewed view of material risks and customer contracts at risk before the board in week five, with accurate citations and easy lawyer corrections.

## Implemented scope

The Firm portal's Overview, Risk Review and Diligence Trackers now open one matter workspace with Board priorities, Review queue, Contract register, Risk register and Consent/change-of-control views. The old internal overview instructions and tracker placeholder are replaced for authorized legal users. Supporting administration, intake, playbook, release, Resources and audit remain available. Workflow steps are retained in a compact expandable guide and board handoff links.

The board shows permission-filtered received/current source counts, extraction coverage, actual successful engine analysis, explicit whole-document review, OCR gaps, open material high risks and received-wave counts. Week-five board, six-week delivery and week-ten signing are scenario-relative milestones; no actual deal calendar dates are invented. The 12,000-document / 400,000-page end-state figures are planning targets, never received/reviewed denominators. Counts exclude inaccessible clean-team sources and other matters. No findings is not represented as no risk.

Lawyers can review the source beside an editable finding, open the full popup reader, confirm/correct/reject, create manual source-cited findings, record severity/materiality/consent exposure, assign a currently cleared matter owner, set a due date and track an open/in-progress/resolved action. Rejection needs its rationale without requiring a full risk assessment form. Each correction or changed decision is a new retained record; original engine proposal, source/playbook/model evidence and legacy reviews remain. The history view distinguishes the original proposal from current lawyer assessments. Human-only findings do not call an AI provider and can be recorded where AI processing is prohibited.

The contract register stores versioned titles, counterparties, scope and human whole-document review. Complete requires confirmed text-ready sources and decisions on all current engine candidates. An approved finding alone never completes a document. Risk and consent registers use current reviewed assessments; rejected versions are retained in history and omitted from active registers. Legacy findings without severity/action assessments are visibly unassessed, not given invented priorities.

## History and release behavior

Migration 0009 adds append-only legal_finding_revisions and document_review_versions, with database UPDATE/DELETE guards and version uniqueness. Source/candidate bytes and release bodies are unchanged. Revision writes lock the source and require the expected prior assessment version. Owners must have active role, matter/wall and clean-team source clearance.

A correction supersedes the prior finding policy. Packages derived from that prior version retain their summary, approval and history but lose current external eligibility; the release desk labels changed lineage. A new package pins the exact current assessment revision and needs a separate audience approval (plus applicable antitrust approval). A stale browser cannot silently draft against a replacement finding. Manual reviewed findings inherit source restrictions and bank privilege exclusion.

Finding/register access now emits scoped business audit events. New read/write surfaces use the shared authorization service; Root Admin gains no legal source override. The internal board/register endpoints are not exposed to ordinary client or bank accounts. Named Halden clean-team source access remains a separate unresolved recovery requirement, not addressed by weakening these gates.

## Files and operating steps

Changes cover models/migration, diligence service and typed API, integration with findings/release version checks, the new MatterWorkspace component, existing portal navigation/reader, Resources, startup fixture/smoke scripts and Start/Stop messages. A pre-0009 PostgreSQL dump is retained in .runtime/backups. Start applies migrations and initializes the synthetic board fixture once; later starts do not overwrite lawyer work or restore revoked grants. Stop retains all versions and fixture state. No additional process, port or dependency was introduced. Safe rollback stops owned services and restores the retained backup in a controlled recovery; do not downgrade away new decisions as a routine rollback.

1. Open https://firm.localhost:8443/portal as lawyer01@freshfields.example using the existing demo password.
2. Overview opens Board priorities. It shows current authorized scope, coverage and the licence consent action. The existing customer contract has an explicit whole-document review fixture; German licence review remains ongoing.
3. Select a risk or open Risk Review. Inspect the source, correct wording/priority/action/owner and enter a decision rationale. Confirm to save a new version; use Reject for an invalid proposal.
4. Use Add lawyer finding for a missed issue or an AI-prohibited source. Cite a specific original unit/passage. The server rejects fabricated/ambiguous evidence and inaccessible owners.
5. Use Contract register to maintain title/counterparty/scope and review coverage. Use Risk and Consent registers to follow current reviewed issues. Excel import/export and recipient-approved workbook generation are not yet implemented.
6. Release Desk uses reviewed versions. A changed finding requires a new exact package and independent audience approval; the prior body and approval remain in history.

The first-wave board fixture adds a lawyer-authored licence issue and two contract-review records through normal HTTPS APIs. Existing C001 releases are preserved; Wave 2 stays unimported. Shared demo identities simulate role behavior, not real independent professional approval.

## Acceptance and remaining scope

Tests cover append-only corrections, stale edits, exact citations, publication pinned to a new revision, preserved old releases with removed eligibility, human-only review despite AI restriction, whole-document coverage versus single-finding review, unauthorized owners, and restricted scope/counts. Source reader and prior end-to-end release regression tests remain applicable. Interactive browser validation is currently blocked by the computer-use service returning GetCursorPos access denied; build and running HTTPS checks do not replace that visual/interactivity check.

Recorded verification: backend suite 125 passed / 1 PostgreSQL-only skip; focused native PostgreSQL board/workflow/reader tests 16 passed; the four extended diligence cases also passed on native PostgreSQL after adding corrected-version publication and AI-prohibited human-review assertions. TypeScript/Vite build passed and live Alembic check found no schema drift. Real HTTPS smoke checks confirmed lawyer-scope received=4, text-ready=3, OCR-pending=1, analyzed=1, fully-reviewed=1, material-open-high-risk=1 and unassessed-findings=3. The fifth source is clean-team pricing, excluded from that user's scope. Three engine candidates, one lawyer-authored finding, two document review records and the original two audience releases are retained; Wave 2 remains unimported. The known Starlette/httpx test-client deprecation warning remains.

This is the first recovery increment. Report drafting/editing, client comments/questions/uploads, named Halden clean-team source access, configured OCR, researched taxonomy/quality evaluation, Excel import/export, permission-trimmed Q&A, signing/deletion/retention workflows and remaining assessment submission artifacts still require subsequent increments. This increment does not establish production capacity or complete assessment alignment.
