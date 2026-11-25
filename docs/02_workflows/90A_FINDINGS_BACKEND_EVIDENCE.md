# Finding DataTables — backend evidence appendix

Main implementation and separate live/browser evidence: [90_FINDINGS_DATATABLES_IMPLEMENTATION.md](90_FINDINGS_DATATABLES_IMPLEMENTATION.md).

Status: frozen backend implementation passed the final automated checks recorded below. This is a bounded internal finding-grid increment, not completion of every Gate 4 dataset or production acceptance. Root records live restart and browser evidence separately; this file must not imply that an automated fixture is a live legal approval.

## Implemented contract

- `POST /api/v1/tables/findings/query`: server-authorized totals, strict typed filters, literal global/column search, allowlisted stable sort, and pages of at most 50 rows. The baseline counts apply typed filters; global/column search determines the filtered count.
- Finding filters include historical source versions, exact source/record key, review state, topic, severity (including honest `unassessed` candidates), materiality, exposure, workflow status and origin. Typed `register=all|risks|consents` and `status=all|active|pending` reproduce existing register predicates, including pending's candidate-or-unassessed rule.
- `GET /api/v1/tables/findings/{stable-key}?matter_id=...&revision_id=...&historical=false`: fresh selected detail; a changed latest revision returns 409. Legacy deep links first locate the authorized current row using `finding_filters.record_key`, then fetch its exact revision. Cached board findings do not hydrate the editor.
- `POST /api/v1/tables/findings/export`: at most 100 selected internal metadata rows. `finding_versions` is mandatory and must map exactly the selected stable keys to revision IDs. Stale, denied and absent rows contribute only to a safe unavailable count; a newer assessment is never substituted. CSV formula-looking values are escaped and Excel cells are explicit strings.
- `GET /api/v1/tables/findings/source-profile/{source-id}?matter_id=...`: a fresh current-source projection for manual finding and whole-document review flows, with the boundaries below.

Grid/export rows contain stable/revision/source identifiers, current source filename and version, summary, origin/rule, assessment fields, review state, classification, current eligible owner identity, deadline and creation time. Quotes, rationale, original candidate summary, AI contexts and history are excluded from the grid/export. Selected detail retains exact validated original-source spans and rationale under the full authorization check; it withholds original candidate summary and AI contexts.

No finding saved views, bulk legal decisions, audience releases, reruns or automatic approvals were added. Database saved-view checks remain inventory/financial only; task/finding saved-view references are rejected. New null filter fields are omitted from historical saved-view normalization, without rewriting retained hashes. No model, migration or live data changes were made for this increment.

## Full contributing authority

`services/finding_tables.authorize_chain` checks the original candidate, every retained assessment revision of the same finding, their bound policies and complete source-policy lineage, and immutable source bytes/text/evidence offsets. Earlier restrictions are not discarded merely because the current source or latest assessment is ordinary. Authorization uses the canonical document PDP and current identity, matter assignment, person/document walls, roles and named clean-team membership. Root has no source-content override; external roles cannot use the internal grid or metadata export.

Counts and files re-collect the entire permitted baseline, not only the displayed page. Current content, exact revision, source/policy lineage and visible people are compared before emission. Owner/reviewer IDs and names are withheld when the person no longer clears the complete chain. Eligible correction owners are independently checked against that same chain; assignment never grants access.

The same helper now protects legacy `diligence.resolve`, history, owner selection and assessment updates. Legacy board/history/owner reads and `/workflow/findings` re-prepare after fresh authentication to catch changes involving people outside the actor's normal authorization stamp. Assessment saves, whole-document review writes and legacy candidate decisions defer their commit until fresh actor, full scope, source/lifecycle and applicable owner checks pass. Failure rolls back decisions, revisions and policies, rather than merely withholding a response after committing.

## Honest source-review projection

`AnalysisJob` and `DocumentReviewVersion` do not retain the historical handling receipt needed to establish the scope of their old user/AI text. Their old title, counterparty, scope, coverage text, analysis coverage, engine result and human activity are therefore not represented as cleared by the new route or legacy board.

Where all contributing finding chains are readable, the sanitized source projection remains available for a **new** source review:

- Prior review metadata has `metadata_withheld=true`, `coverage_state=unavailable`, current filename as an explicitly new-form default, blank counterparty and scope `other`. Only the actual current revision number is retained as an optimistic-concurrency input.
- Prior analysis has `metadata_withheld=true`, `state=unavailable`, no coverage text, and `has_completed_run=null`; unavailable is never rendered as no analysis.
- Board `fully_reviewed` and `analyzed` aggregates are null when their supporting legacy metadata is withheld. `review_metrics_withheld`, `analysis_metrics_withheld` and a notice explain the limit. Current permitted source/finding counts remain separate.
- Full-source review requires access to **all** contributing finding chains. If one cannot be established, the optional source-review profile is unavailable and whole-document mutation is denied.
- Independently authoring a new finding uses separate `can_create_finding` and `eligible_new_owners` fields under current confirmed source authority. An unrelated inaccessible finding is not copied into that new record. Correcting a selected existing finding uses its separately checked `can_edit` and `eligible_owners`.

`can_edit` is an advisory current snapshot: historical/superseded or frozen sources remain read-only and the server rechecks every command. Saving a new source review preserves old records. Prior review metadata remains withheld even after that save because this no-DDL increment does not invent a historical receipt; the sanitized projection and next new-review action stay available under current authority. A retained metadata extension remains future work.

## Confirmed legacy failures and bounded fixes

Independent authenticated adversarial tests proved these failures before their fixes:

1. A retained clean-team document-review title/counterparty appeared in `/diligence/board` after current source relaxation and membership revocation. The board now uses the sanitized projection.
2. Whole-document completion succeeded while a same-source finding chain was inaccessible, because the old visible-finding list silently omitted it. Source-review writes now require the complete source finding union before and after preparing a write.
3. A legacy candidate-review request committed its decision and returned evidence after the actor acquired a wall mid-request. The route now defers commit and re-authenticates/re-authorizes the complete chain.
4. The legacy finding list returned a prepared owner identity after that account became inactive. The route now re-prepares the permitted content and visible people.

A fifth, independent emission probe enabled the normally governed sharing policy before testing a clean-team assessment followed by an ordinary source/latest revision. A new package could be independently approved without antitrust handling, and an external reader received its retained private canary. The corrected regression failed in 7.98 seconds before the emission fix; an unconfigured sharing gate is not accepted as evidence for this boundary.

`finding_release_guard.denial` now checks immutable exact package references and actual finding nodes, only the assessment prefix through each pinned version, and all contributing original source identities. Privilege and each clean-team scope are separate requirements bound to their original source/version; another source's matching scope cannot satisfy them. Restrictive intermediate policies, named recipients, quarantine/AI restrictions and protective source-label evidence are also retained. Superseded/candidate workflow state alone does not prohibit an ordinary corrected package. The pure helper does not authorize an external actor to read originals and does not rewrite historical links, content, snapshots or approvals.

Package reads and approval decisions use this shared denial, and a small canonical-PDP hook applies it to release roots or ancestors for consistent authorization-checker and derivative behavior. The common package boundary covers report/tracker downloads, permitted fresh and cached answer references, retrieval and collaboration. New package/report creation checks after flushing the draft lineage and before committing, so a denied creation leaves no unreadable draft behind. An unbound artifact can only receive an opaque protective revocation from its current active, assigned, unwalled creator or Legal SME, with exact concurrency hashes; it returns only an ID/revoked receipt. Current session, role, source/PDP, operation-specific rights, environment gate and expected post-mutation snapshot are rechecked before ordinary decisions commit, without treating the operation's own flag changes as a race.

Scoped source-profile receipts are written only during the first preparation. Where a profile/owner aggregate contains contributing finding information, its clean-team partitions also receive scoped receipts. A failed response rolls back those prepared receipts before recording a safe denial.

## Verification receipts

Pre-final receipts (overlapping suites; do not sum these as a single baseline):

- Initial new finding contract tests: 4 failed before implementation; then 4 passed in 9.41 seconds.
- Finding contract plus existing diligence/table/saved-view regression: 32 passed in 70.39 seconds, before the final sanitized board/profile and four legacy route fixes.
- Combined finding/task/table/saved-view/diligence regression: 63 passed in 128.00 seconds, also before those final changes.
- Focused final fixes for legacy board, whole-document review and candidate review: 4 passed in 14.94 seconds. This is a targeted result, not the final integrated suite.

Final independent SQLite security suite: **38 passed in 119.31 seconds** (`backend/tests/test_finding_data_tables.py`), including the four previously failing legacy paths. The test author is a separate agent from the production implementation owner.

Final independent PostgreSQL security suite: **38 passed in 127.00 seconds**, using disposable fixture schemas and the same final source/test file. All four previously failing legacy paths passed on both databases; the process exited successfully and its fixtures completed.

The earlier combined PostgreSQL downstream regression was stopped when the fifth failure was proved. It produced no completed result and is not an acceptance receipt. Final emission and downstream regression receipts are pending the final helper/auth/audit source freeze. The four-path 38-case results above predate that fifth fix and must not be represented as complete release acceptance.

Focused emission development receipts: the initial corrected probe plus first independent emission matrix passed **18 tests in 41.00 seconds**; a subsequent emission/report/document-workflow batch passed **35 tests in 76.07 seconds**, before the final intermediate-lineage/current-session refinements. The implementation owner's separate source-identity, independent restriction and pinned-prefix checks passed **9 tests in 15.80 seconds**. These overlapping intermediate receipts are not a final integrated result.

Final frozen-source smoke: **20 passed in 39.09 seconds** across `test_finding_release_taint.py`, `test_finding_release_guard.py`, `test_reports.py` and `test_document_workflow.py`. Root's corrected independent emission matrix passed **33 tests in 95.60 seconds** on SQLite, including opaque containment authority, exact post-approval concurrency hashes, current-session/wall/role races, old artifact preservation and positive ordinary/sanitized publication.

Final current-source receipts (overlapping coverage; do not add these as distinct tests):

- Root's complete SQLite run: **718 passed, 1 skipped**, all **719** collected cases accounted for, **461.59 seconds** total across four isolated file shards. The runner verified unchanged source hashes. Receipt directory: `.runtime/test-runs/datatables-27cdd6cd98724ef4b5ee8539a8b6c296`.
- PostgreSQL combined parity: **207 passed in 718.74 seconds**, process exit 0. Its 22 files cover the finding contract/security/emission/guard/probe suites, task contract/security compatibility, existing DataTables and saved views, diligence/document review, reports, trackers, review tasks/clocks, lifecycle, DDR evidence/release gates, questions/report AI fixtures, retrieval, named source access and disclosures.
- SQLite's sole skipped dialect-specific case, `test_runtime_queue.py::test_postgres_concurrent_workers_claim_once`, was then run on PostgreSQL: **1 passed in 5.01 seconds**, process exit 0.

The final PostgreSQL processes and fixtures completed before the controlled-restart handoff. A read-only namespace comparison found no new leftover test schemas. Ten pre-existing disposable schemas were left untouched because their ownership was not established; no broad cleanup, live application mutation, migration, provider call or public action was performed.

Root's full integrated suite and live/browser receipts are maintained in the main implementation document; this appendix does not infer their outcome.

## Remaining limits

Exact authorized baselines scan retained histories. Page size and selected exports are bounded, but this is not representative-scale proof for 12,000 documents or 400,000 pages. Throttling remains process-local. Saved views for findings/tasks require a separately governed schema extension. Broader contract metadata grids and other Gate 4 datasets remain separate increments. This work adds no public deployment, legal approval, provider call or claim that all implementation gates are complete.
