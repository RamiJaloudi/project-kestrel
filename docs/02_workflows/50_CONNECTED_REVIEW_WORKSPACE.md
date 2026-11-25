# 50 — Connected document-review workspace

[IMPLEMENTED, LOCAL DEMO, 22 NOV 2026]

## Delivered
- Risk Review selects a permitted document and filters its findings. A selected finding collapses the queue and brings highlighted original text beside the correction/decision form. Exact evidence still opens the authenticated multi-format reader.
- Each visible source has separate analysis, finding-decision and whole-document review progress. The eight-risk checklist reports the last completed engine run, identifies offline baselines and shows missing categories as unassessed. It does not equate no engine finding with legal clearance.
- Whole-document review is available in the same workspace for all permitted source types. Existing server rules still require confirmed text, verified OCR where relevant and decisions on outstanding candidates before completion. Sign-off does not approve audience release.
- Overview links outstanding finding decisions, whole-document sign-offs and packages awaiting release approval. Counts are limited to the current account's visible scope.
- A shared URL selection helper preserves the permitted matter across Documents, Review, Reports, Questions, Collaboration, Uploads, Clean Team, Signing/Retention, Playbooks and tracker screens. An unavailable requested matter is not silently replaced with another. Audit initializes its optional filter from the current matter. Action Center remains a cross-matter task inbox.
- Sidebar navigation updates the view URL; workflow links carry the matter. Documents links directly to review of the same source. Existing source, finding and release APIs still authorize every operation.
- Resources' lawyer guide explains the connected review and sign-off stages. Start/Stop descriptions reflect the new workflow; no service topology changed.

## Implementation
New frontend/src/matterSelection.ts and DocumentReviewPanel.tsx; updates to MatterWorkspace, WorkflowWorkspace, PortalApp, WorkflowSteps, ReportsWorkspace, QuestionsWorkspace, CollaborationWorkspace, CleanTeamWorkspace, ClientUploadsWorkspace, LifecycleWorkspace, PolicyWorkspace, TrackerExchange, AuditWorkspace and compact.css.

Backend services/diligence.py adds permission-filtered per-source progress to the existing board response. api/resources.py updates guide text. tests/test_diligence.py verifies independent analysis/decision/sign-off stages and external denial; existing clean-team test also checks sources remain excluded.

## Verification
- TypeScript/Vite build passed (46 modules), including final accessibility label and unavailable-matter message changes.
- 31 tests passed in the focused suite: diligence, document workflow, canonical policy entry points, observability/governance and reports. One existing Starlette/httpx deprecation warning. The full backend suite was not rerun for this increment.
- Live browser: authenticated sme01, non-default synthetic tracker lab matter. Verified document selection, all eight checklist categories, sign-off rationale gate, highlighted text beside corrections, reader popup and retained matter on Reports and Questions navigation. Overview showed scoped pending actions. A deliberately unavailable matter showed no document data and did not fall back to another matter.
- Browser checks made no legal decisions, sign-offs or releases. No uploads or paid AI operations were initiated. Mutating review behavior was tested against isolated test databases.
- Live preview: outputs/connected-review-preview.jpg.
- Existing services restarted using the project launcher with -NoOpen; fixtures and decisions preserved. No database migration required.

## Rollback
Pre-change copies of frontend TSX files, compact.css, diligence.py and Start/Stop scripts: .runtime/ui-backups/connected-review-20261122-191839 (original relative directory structure). Restore those files, remove the two new frontend modules if desired, restore the previous resources guide wording and rebuild. Restart local services after restoring backend code. No data rollback is needed. The backup does not contain resources.py or the added test; revert those separately.

## Remaining scope
This completes the connected review increment. Deeper report-section/findings navigation, version comparisons and item-level client/bank collaboration remain the next delivery increment. Retrieval quality improvements and external immutable storage remain separate work. This prototype is not evidence of readiness for the real matter's document volume.
