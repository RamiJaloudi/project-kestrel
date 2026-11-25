# 51 — Reports, finding snapshots and section discussions

[IMPLEMENTED, LOCAL DEMO, 22 NOV 2026]

## Delivered
- Internal report sections expose the exact retained finding summary, revision ID, assessment revision and contributing source version used in the saved report. The existing source reader opens the retained citation. A separate link opens current finding review; it does not replace the historical snapshot.
- Saved versions in the same report history can be compared field by field. Comparison uses saved bodies and only versions already authorized for the current account. It reports changed text fields and annex differences; it is not a legal redline or an AI assessment.
- Unsaved report edits are identified. Switching saved versions requires save/discard, and audience approval remains disabled while edits are unsaved.
- Released report versions expose whole-package or section-specific discussions directly in Reports. Collaboration offers the same package/section views and links back to the exact report version.
- The reusable PackageDiscussion component handles questions, comments, parent replies and independent approval of firm drafts. Section replies inherit their parent's context; cross-package or conflicting-section replies fail closed. Existing antitrust, audience, wall, lineage, signing and revocation checks remain in force.
- Navigation clears obsolete report/discussion context when changing screens or matters. The selected report is retained in its page URL.
- Resources and Start/Stop wording explain the connected report flow.

## Schema and API
Additive migration 0024 adds nullable collaboration_messages.section_index. Existing messages remain whole-package messages. The section index is validated against the exact report release before writing or filtering. It is an index into immutable saved section order; no report text or section structure is changed by discussion.

GET /api/v1/collaboration accepts optional section_index. POST accepts an optional section_index; existing payloads remain valid. Message output includes the context. Immutable message guards also prevent changing section context after creation.

Internal report output adds section_findings and previous_id. External report output excludes these, source-reader citations and unpublished report contents. Public report_key already groups authorized versions. Comparison never fetches an inaccessible predecessor.

## Verification
- Frontend TypeScript/Vite build: passed, 48 modules, including final context-navigation changes.
- Full backend suite: 209 passed, 1 skipped, one existing Starlette/httpx deprecation warning (196.98 seconds).
- Focused reports/collaboration/migration suite: 9 passed after correcting empty-database downgrade behavior. The later added immutable-section-context assertion passed in a 3-test collaboration rerun.
- Coverage includes independent publication, external hidden drafts, bank denial, invalid section indexes, section filtering, inherited reply context, incompatible section denial, retained finding snapshots, version lineage, migration/model alignment and rollback protection.
- Pre-migration encrypted PostgreSQL backup and scratch restore verified: 61 tables / 14,132 rows and matching schema. Backup retained; active database was never restored over.
- Local launcher applied migration 0024 and restarted services without opening tabs/tools or initiating paid AI. Existing fixture approvals and decisions were preserved.
- Read-only live API verification found five internal report versions and validated their section/finding mappings. Tested Halden and Castlegate accounts had no currently visible released reports; no release was created or approved to manufacture a live result. External audience behavior was exercised in isolated backend tests.
- scripts/verify_report_connections.py uses normal synthetic sign-in, prints only counts, performs no paid calls or business decisions and logs out its verification sessions. Local credentials are read privately from .env, never printed.

## Visual limitation
Live rendered visual verification could not run: browser/desktop initialization returned Windows access denied (GetCursorPos). No fresh report screenshot is claimed. Build and API verification succeeded; browser interaction and layout QA remain pending when desktop access returns.

## Files and rollback
New frontend/src/PackageDiscussion.tsx and ReportComparison.tsx; updates to ReportsWorkspace, CollaborationWorkspace, MatterWorkspace, PortalApp, matterSelection.ts and compact.css. Backend models.py, api/collaboration.py, services/reports.py, api/resources.py; migration 0024; report/collaboration tests and live verification script. Launcher descriptions updated.

Pre-change source copies: .runtime/ui-backups/report-collaboration-20261122-215040, preserving original relative paths. For a code rollback restore those copies, rebuild and restart, retaining the additive column/migration and its data. Downgrade refuses to drop populated section context; an archival plan is required before any such schema rollback. No automatic deletion of discussions, reports, audit or backups is introduced.

## Next
Visual QA of the connected report views and a human-led release/discussion walkthrough. Permission-aware retrieval quality and item-level audit navigation remain subsequent increments. No public deployment or production-readiness claim is made.
