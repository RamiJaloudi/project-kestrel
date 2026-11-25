# 49 — Canonical document ABAC and ethical-wall enforcement

[IMPLEMENTED, LOCAL DEMO, 22 NOV 2026]

## Scope and acceptance
Consolidate production document authorization without changing grants, API contracts, approval gates or database records. Acceptance: the checker, document-authorization API and workflow enforcement agree on permitted and denied operations; a successful earlier check cannot override a later wall; existing business security tests pass.

## Implementation
- `backend/kestrel/services/policy.py` now owns the canonical `evaluate` decision and `require` enforcement functions. The existing decision rules and reason codes are preserved.
- `services/documents.py` retains SQL-view loading, source lineage and approval snapshots. Its old `evaluate` entry point delegates to canonical policy for compatibility; it contains no independent decision implementation.
- Document workflow enforcement, the document-authorization API and the person/document Wall Checker use canonical policy. Reports, trackers, Q&A, analysis and other consumers using workflow enforcement inherit that entry point.
- The old attribute-only helper was not used by production routes. It is moved to `backend/tests/reference_policy.py` for the existing isolated reference-model tests. It is not included in the installed `kestrel` package. The pure examples in domain.py remain explicitly non-production reference models.

## Decision flow
Authenticated principal (including active assignments and resolved client/matter walls) → canonical document policy → document state and source lineage → action-specific checks → permit/deny. The Wall Checker is a point-in-time simulation; operations still enforce policy at execution time. Server records supply document attributes, not browser-provided permission flags or AI output.

No new permission is granted. Named source grants, clean-team scope checks, bank privilege exclusion, audience publication, independent approval and signing/closing restrictions remain unchanged.

## Files
policy.py, documents.py, workflow.py, wall_checker.py, api/integrations.py and START_KESTREL.bat status wording; tests/reference_policy.py, test_auth_policy.py, test_demo_accounts.py, test_document_abac.py and new test_policy_entrypoints.py.

## Rollback
Move the evaluator implementation back from policy.py to documents.py; restore its domain/clean-scope imports; restore the old helper from tests/reference_policy.py if required; restore previous imports in callers and reference tests. No schema/data rollback is needed. The compatibility evaluator wrapper makes existing external Python imports continue working in this version.

## Verification
Focused authorization suite: 38 passed, one existing Starlette/httpx deprecation warning. Includes nine cross-entry-point decision cases and a new-wall-after-precheck regression. Full backend suite result recorded below after completion. No paid AI calls or real-matter processing are part of verification.

Full backend suite: **207 passed, 1 skipped**, one existing Starlette/httpx deprecation warning (199.66 seconds). Python compile checks passed. Local launch rebuilt the frontend successfully.

Runtime: recovered the exact verified project supervisor ownership record after a restricted process check could not see it; restarted project services using the existing launcher. Startup preserved existing fixtures and decisions. Final HTTPS, HTTP redirect, PostgreSQL and worker health checks passed. No browser or database-tool tabs were opened during restart.
