# Findings DataTables and retained review authority

24 November 2026. This is the second bounded increment under the user's DataTables priority. The Excel workflow-script walkthrough remains the final gate. It does not complete the admin/audit or secondary-register rollout in [docs/88](88_DATATABLES_ROLLOUT_PLAN.md).

## Implemented scope

The Firm portal's Review queue, Risk register and Consent/change-of-control register use the shared official React DataTables wrapper. Counts, paging, named sorting, global/column search and typed filters are server-authorized. Register and status presets preserve existing semantics: reviewed risks; reviewed change-of-control/assignment/termination consents; active versus pending versus all findings. Filtering a page in the browser is not used to calculate totals.

Selecting a finding opens a newly authorized **exact assessment revision**, its evidence and eligible owners. The grid does not hydrate the editor from cached board arrays. Legacy deep links first locate an authorized stable key, then fetch its pinned revision. New source-only/manual finding flows use a separate current-source profile. Historical sources are read-only. Dirty editor text survives background authority checks; stale/denied authority clears the protected detail, reader and history.

Selected internal CSV/Excel exports pin every selected stable key to its `revision_id`. A changed, unavailable or denied revision contributes only to the unavailable count; it cannot silently export a newer legal assessment. All spreadsheet values remain literal text. Finding saved views and bulk legal decisions/releases are not introduced. Existing immutable assessment decisions, the original-language reader, history and separate audience-release controls remain distinct.

## Full retained scope

The new finding service authorizes the original candidate, every same-record assessment revision, each contributing policy, its source lineage and exact immutable source evidence. A later ordinary assessment does not relax a retained clean-team partition. Current owner identity is masked if that person no longer clears the full chain. Query/export signatures and exact-detail reads repeat their prepared authorized projections before returning, including visible people and off-page contributing records.

Source-wide review requires authority over **all** finding chains on that source. A filtered/hidden set of visible candidates is insufficient for whole-document completion. A new independently authored finding uses its own current-source authority and separately eligible new owners; it does not grant access to unrelated restricted assessments.

## Proven older-route gaps addressed

Independent disposable-fixture tests first demonstrated four failures. These were not live data changes:

1. The old board returned private document-review title/counterparty text after a clean-team source was relaxed and the actor lost the retained scope.
2. Whole-document review could be marked complete while a hidden same-source finding chain remained outside the actor's authority.
3. The older candidate-review route could commit and return evidence after an ethical wall was added during its prepared request.
4. The older finding-list route could return an assigned owner's stale identity after that account became ineligible during preparation.

Narrow fixes cover the existing diligence/workflow routes as well as the new grid. Source-review and candidate-review writes defer commit until fresh actor/current source/full-chain/lifecycle checks. Older board/history/owner/list reads prepare again before returning. Ordinary source access does not stand in for retained assessment access. No global PDP bypass, new role grant or change to released historical packages is introduced.

## Older review and analysis metadata

`DocumentReviewVersion` and `AnalysisJob` do not contain a complete retained handling receipt for their old free text/result bodies. This increment does not manufacture one. The board and source profile therefore withhold prior title/counterparty/scope and analysis coverage where those records lack proof. Original rows remain unchanged.

A cleared current-source profile supplies explicit **new review defaults** (current filename, blank counterparty and Other scope) and the optimistic revision needed to append a review. It labels prior review/analysis metadata as withheld; an unavailable run is not called “no analysis.” Unprovable whole-document/analyzed totals are nullable and displayed **Unavailable**, rather than zero or completed. Source-wide uncertainty may withhold the whole-document panel while a separately authorized selected finding remains usable.

Appending a new review does not backfill old handling receipts. A future structured retained-metadata extension is required to restore complete historical review/analysis projections. This is a material bounded-prototype limitation, not a claim that all prior metadata/history is readable.

## Locations and rollback

- [Finding grid](../frontend/src/FindingsDataTable.tsx), [matter/editor integration](../frontend/src/MatterWorkspace.tsx), [document review panel](../frontend/src/DocumentReviewPanel.tsx), [shared table](../frontend/src/KestrelDataTable.tsx).
- [Retained finding service](../backend/kestrel/services/finding_tables.py), [table routes](../backend/kestrel/api/data_tables.py), narrow diligence/workflow service/API hooks.
- [Contract tests](../backend/tests/test_finding_tables.py), [independent adversarial cases](../backend/tests/test_finding_data_tables.py), [read-only live check](../scripts/verify_finding_tables.py).

No models, schema migration, public deployment, genuine approval or provider call is included. Application schema remains 0038. Start/Stop notices identify the new register and retained assessment versions; no additional server/console is started. A code rollback must retain all stored versions and audit records and must not re-enable the four demonstrated access gaps.

## Verification

The frontend TypeScript/Vite production build passes (84 modules). Final broad SQLite, PostgreSQL and signed-in browser results will be recorded after the final protected-route source freeze. Earlier passing subsets do not constitute those final integrated results. There is no measured production-scale performance claim. Contract inventory, admin/audit and secondary lists still require their own conversions; reader tables keep literal source order.

Independent task/finding backend evidence is retained in [docs/90A](90A_FINDINGS_BACKEND_EVIDENCE.md).

### Additional release-containment finding

The 38-case finding suite passed on SQLite and PostgreSQL. A corrected downstream release probe then proved a fifth gap: an ordinary latest finding revision could omit a prior clean-team revision from the audience package's physical lineage. With the isolated fixture's normal sharing policy enabled, independent package approval and external read could emit the retained canary without antitrust handling. The earlier probe had been masked by the missing sharing policy and is not evidence of containment.

The broad SQLite run and combined downstream PostgreSQL run against the earlier source were stopped after this proof. Their partial progress is not a final pass. Root's partial log remains `.runtime/logs/pytest-datatables-full-eaf69e0abf0b4d0790a83800ac82eaa1.log`. No fixture or log was deleted.

The scoped [pure package guard](../backend/kestrel/services/finding_release_guard.py) is now implemented, with common package/decision gates and a narrow canonical-PDP hook for package roots/ancestors. It validates exact references and the pinned prefix, original source/version identity, privilege and individual clean-team scopes, restrictive intermediate lineage and named-recipient coverage. It never appends old policies, grants source access, retrospectively declassifies data or rewrites snapshots/approvals. Ordinary corrected findings remain releasable; a properly approved sanitized transcript remains separate from original-source access.

New unbound draft/package/report creation is rejected before commit. Bound legal release decisions reauthenticate current sessions/roles/matter/source authority and recheck the prepared state before commit. A creator or current scoped Legal SME may protectively revoke an unbound already-released artifact using correct concurrency evidence, receiving only `{id,revoked}`; other accounts gain no blind control or content access. Scoped revocation audits include retained intermediate partitions.

[Independent release-emission checks](../backend/tests/test_finding_release_emission.py) passed **33/33 SQLite**, 95.60 seconds, on the final frozen source. These include legacy approved/pending packages, both audiences, report download formats, cached answers/scope-only references, fresh corpus, collaboration, the document checker, creation rollback, intermediate restrictions, stale hashes, minimal containment receipts and permission/session changes before commit. Original artifact bodies/history/approval hashes remain unchanged during denied reads. A test-only pre-approval snapshot mistake was corrected before this final run; the preceding 31/33 run is not reported as a pass.

The final whole-suite run used [four isolated SQLite file groups](../scripts/run_sqlite_regression.py): **718 passed, 1 skipped; all 719 collected cases accounted for**, 461.59 seconds overall. All four processes exited zero, and before/after hashes confirm no application/test/script source changed during the run. The single skip is `test_runtime_queue.py::test_postgres_concurrent_workers_claim_once`, which requires the PostgreSQL dialect; that selected check is scheduled after the current PostgreSQL parity run. Retained plan, source hashes, per-group logs and `result.json` are in `.runtime/test-runs/datatables-27cdd6cd98724ef4b5ee8539a8b6c296/`.

The runner adds no dependency, touches no live matter records and verifies each collected case is accounted for; interrupted earlier runs are retained separately. PostgreSQL parity, controlled restart and signed-in finding UI verification remain pending at this checkpoint.

### Completed integration checkpoint

- Final current-source PostgreSQL parity: **207/207 passed**, 718.74 seconds, plus the separate PostgreSQL concurrent-worker claim case **1/1 passed**, 5.01 seconds. No test process remained active before restart. The ten pre-existing test schemas were retained; no unowned schema was deleted.
- Controlled Stop/Start completed and all five real components passed the local health check. The app remains at schema **0038**, with **154 tables including Alembic**, **17 source versions** and **2 existing review tasks**. Startup verified its 33 dummy accounts; the database currently contains 37 total accounts including the pre-existing additional identities. No total-account before/after comparison is asserted.
- Read-only HTTPS smoke checks passed for **21 permitted findings**, server empty-search counts and consent preset, exact pinned detail, stale-detail refusal, Root/bank denial, and CSV/Excel inclusion of one permitted exact revision with matching file checksums. `.runtime/finding-tables-live-verification.json` contains the sanitized result. No legal decision, assignment change or provider call was made.
- Signed-in browser verification covered 10-row paging across 21 findings, cross-page selection and successful selected CSV status, typed change-of-control filtering (four matching rows), selection clearing, four reviewed consent rows, fresh row-to-editor mapping, manual input on a zero-finding source, draft preservation across the background authority interval, PDF citation text highlighting, German Word presentation and original-language evidence. Prior-review metadata remains explicitly withheld rather than represented as zero or unreviewed.
- Frontend-only refinements after the frozen backend run passed TypeScript/Vite builds and the browser checks: concise three-line summary previews with an explicit Open review action; collapsed prior-metadata explanation; derived form values clear on selection/scope changes; revision URL parameters clear on navigation/matter changes; initial matter loading preserves deep links; explicit stale revision links show a refusal while valid pinned links reopen correctly. No backend/test/script changes followed the final regression freeze.
- Narrow verification at 640 px showed no page-level horizontal overflow; the table scrolls inside its own region and the menu starts compact. No browser console errors were observed. The in-app browser did not paint the native original PDF pane, so native PDF rendering is not claimed as visually verified there; extracted PDF evidence/highlights and the Word reader were verified. Native-browser PDF inspection belongs in the final manual workflow gate.

Previews: `delivery/frontend_preview/finding-datatables.jpg`, `finding-datatable-editor.jpg`, `finding-datatable-narrow.jpg` and `finding-word-reader.jpg`. Task previews/evidence remain in docs/89. Contract inventory is prepared but still unwired under docs/92; admin/audit remains planned under docs/91. This is a completed task/findings increment, not completion of every requested DataTable or expanded application gate.
