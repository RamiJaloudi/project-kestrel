# 64 — Authorized server-side DataTables

24 November 2026. [DEMO] Local synthetic implementation, no production throughput claim.

The document inventory and financial evidence grids now share a React DataTables wrapper. Paging, sorting, global search, literal column filters and counts execute on the server after current matter, wall, classification and audience authorization. Column visibility is a presentation choice and cannot grant access. The existing popup reader remains the evidence destination.

## Boundaries and operation

`POST /api/v1/tables/{inventory|financial}/query` accepts only typed bounded requests: at most 50 rows per page, allowlisted sort/filter columns, no regex or arbitrary SQL. Inventory queries load metadata rather than source binaries. Financial queries preserve exact decimal strings; this baseline refuses results above 100 permitted matching facts and asks the user to narrow typed filters. It does not silently truncate counts.

Each request reauthenticates before producing its result and checks a fingerprint of relevant authorization inputs after preparation. A changed wall, account, assignment, clean scope, classification, release, financial gate or current approver authority causes the prepared response to be withheld. The detector supplements the canonical PDP; it is never an authorization grant. Unrelated other-matter wall changes do not invalidate a response.

Selected internal metadata exports support CSV and Excel, at most 100 distinct selected records. Every row is rechecked, source classification must be confirmed, and denied rows yield a generic unavailable count without names. CSV formula-looking strings are escaped; Excel values are literal strings, preserving leading zeros and exact amounts. No source passages are included. External publication still uses independent audience-approved packages. Exports return SHA-256 and no-store headers; this does not constitute immutable storage.

Browser requests refresh every 15 seconds. Session/access changes (401/403/409) clear rows, selected IDs and parent evidence panes; explicit reload is required. Export errors have the same clearing behavior. Stale unmounted responses cannot trigger a download. Text cells use React escaping. Per-actor request limiting is local-process protection, not distributed edge throttling.

## Verification and limits

Focused table, wall-checker and entry-point checks: 33 passed. Independent security review: 15 passed, including wall revocation during candidate/compare preparation, clean-team revocation, restrictive labels during export, and bank-gate/current-approver revocation. Earlier PostgreSQL table checks: 7 passed; final saved-view integration and PostgreSQL rerun follow separately. See docs/67_GATE4_SECURITY_REVIEW.md.

DataTables React 2.0.1 and core/style 3.1.5 are pinned MIT dependencies; notices are retained in frontend/THIRD_PARTY_NOTICES.md. No paid extensions or duplicate API servers are used. Existing Start/Stop launchers remain authoritative. Saved configurations and their independent sharing governance are described in docs/65; their integration verification is still in progress at this checkpoint.

Only inventory and financial grids have been migrated so far. Other screens remain existing controls. Row-level filtering/counting is bounded local baseline work, not measured 12,000-document capacity. Browser verification confirmed the inventory search narrowed nine permitted rows to one, and the two-pane English/German evidence reader rendered correctly. Saved-view mutation/sharing was verified in disposable tests; no live sharing decisions were submitted. Rollback retains migrations/data and uses a verified backup; do not delete retained configuration or audit rows.
