# Gate 4 independent security review

[DEMO] 24 November 2026. This review covers the inventory and financial DataTables boundaries, selected internal metadata exports, the existing reader comparison increment, and the saved-view integration points. It is evidence for the local synthetic prototype, not an Azure migration, public-deployment approval, legal approval, or production capacity claim.

## Review scope and changes

The independent reviewer read the authoritative assessment brief, repository instructions, design/security requirements, the reusable React DataTables prompt, the cross-domain security regression prompt, the shared policy/identity/wall/content-label/disclosure services, table API/schema/service, reader comparison API/service, and React table/reader/comparison components. The saved-view API/service/schema were also inspected while integration was in progress.

The initial review wrote `backend/tests/test_table_security_review.py` and this report. The coordinating agent then explicitly assigned this reviewer `frontend/src/SavedTableViews.tsx` and `frontend/src/KestrelDataTable.tsx` to implement the saved-query interface. Other production fixes were reported to and implemented by the coordinating agents. No secret files were inspected or printed. Tests used disposable synthetic SQLite fixture databases. The live matter, local operational database, cloud resources, paid AI services, and public deployment were not used. Fixture execution began only after the coordinating agent confirmed migration `0034` was stable for isolated tests.

## Findings and disposition

1. **Authorization-denied export left stale client state.** The export handler originally converted HTTP errors into a plain `Error`, losing status and leaving previously rendered rows, selection, and related reader state until the next poll. The coordinating agent changed it to preserve status, immediately block/unmount the table, clear selection, and call the same denial callback for 401/403/409 used by table queries. It also avoids downloading or updating state after component unmount. The updated handler was inspected; this review did not independently run browser automation.
2. **Reader candidate/comparison metadata lacked a final current-scope check.** Their original single cached principal could survive an ethical wall added after the first resource read. That could return prepared IDs, titles, and coordinates even though a later actual reader GET would deny. The coordinating agent added fresh beginning/end authorization checks, with safe denial audit and rollback. Both new in-flight wall regressions passed. The comparison picker also clears rows, selection and panes on explicit 401/403/409.
3. **Saved-view queries need a second current ACL/version resolution.** The ordinary table fingerprint does not itself include saved-view/share records or every saved-view owner/reviewer identity. The backend now independently resolves the entitled saved version before and after the table scan and rejects drift. The frontend also sends the loaded version hash, so a newer version created between requests cannot silently run different filters behind old controls. Configuration API response validators recheck current ACL, version integrity and evidence binding. The backend agent owns the added saved-view integration regressions.
4. **PDF-renderer portability regression blocked fixture setup.** The first bank-fixture run failed before security assertions because `adapters/disclosure.py` imported a removed `report_export.RUNTIME` symbol. The portability agent corrected the caller. All three affected bank security cases then passed. This was an integration failure, not an observed authorization failure.

## Independent regression coverage

`backend/tests/test_table_security_review.py` contains 15 parameterized cases:

| Boundary | Cases | Required observable behavior |
|---|---:|---|
| Selected matter versus a second matter the same actor may read | 1 | Query counts/search stay in the requested matter; mixed selected export returns only its permitted matter row and a safe unavailable count; comparison omits the other matter's ID/title/location. |
| Session revocation, account deactivation, legal-role removal, matter-assignment revocation during table scan | 4 | 401/403; no prepared IDs, file names, counts, or attachment headers. |
| New restrictive content assertion introduced through the actual independent SME workflow during query/CSV/XLSX preparation | 3 | 409; no prepared rows, counts, or file. |
| Revoked clean-team candidate used as cursor | 1 | Opaque 404; no denied ID/name; a fresh page still returns the ordinary permitted source. |
| Exact comparison offsets with an astral Unicode character | 1 | Offsets and anchor length use Unicode characters; an invalid bounded location returns only a generic unavailable pane. |
| Approved bank financial row loses its approving SME role, approving SME matter assignment, or bank feature gate during scan | 3 | No prepared exact amount, fact/artifact/original IDs, or counts. |
| Ethical wall introduced after first reader resource read | 2 | Candidate and comparison responses withhold all prepared private metadata. Both passed after the guard patch. |

Existing tests independently owned by the coordinating agents cover allowlisted sort/filter contracts, denied-row counts, exact Decimal ordering, confirmed-only metadata exports, per-row partial export, original raw-export restrictions, formula-looking CSV/XLSX strings, clean-team revocation, unrelated other-matter walls, bank source denial, and source/derivative citation separation. This report does not substitute those earlier results for execution of the new cases.

## Executed checks

From `backend`, with `KESTREL_TEST_POSTGRES=0`:

```powershell
.venv/Scripts/python.exe -m pytest tests/test_table_security_review.py -k 'not reader_responses_withhold' -q
```

Initial result: **10 passed, 3 failed, 2 deselected**, 26.06 seconds. All three failures were the PDF-renderer import integration issue described above.

After that caller fix:

```powershell
.venv/Scripts/python.exe -m pytest tests/test_table_security_review.py -k 'external_financial_counts' -q --tb=short
```

Result: **3 passed, 12 deselected**, 7.66 seconds.

After the reader guard patch:

```powershell
.venv/Scripts/python.exe -m pytest tests/test_table_security_review.py -q --tb=short
```

Result: **15 passed**, 23.03 seconds. A full rerun after the saved-view query/hash integration also passed **15 tests**, 29.43 seconds. The test module also passed an AST syntax check before fixture execution. The only pytest warning was the installed Starlette/httpx deprecation warning. PostgreSQL and full-suite integration remain coordinating-agent responsibilities; this review has not independently claimed those results.

## Saved-query frontend implementation

The shared table now contains a compact saved-query panel. A user can save a private query, select and explicitly load a current permitted configuration, or append a new immutable private revision with an optimistic version hash. The saved content includes search, column filters, sort, page size and typed filters. Column visibility remains a live display preference and is not represented as persisted authorization or saved configuration.

Evidence-bound saves use one to fifty explicitly selected source IDs for inventory or financial-fact IDs for financial tables; users can explicitly reuse a loaded revision's evidence bindings. Bank saves require evidence binding and remain private. Internal owners can request named, expiring sharing. A source-cleared independent SME sees the exact saved name, query, evidence references, version/share hashes and sharing rationale before manually checking the review declaration and approving or rejecting. Owners can revoke future sharing, including older revisions through the protected request queue. No approval checkbox or decision is automatically supplied.

Loading mirrors the stored search/order/page-size/column-filter controls and uses the authoritative server saved-view query. Manual search, sort, or page-size edits detach the saved-view identity and preserve the loaded typed filters until the user returns to workspace filters. External workspace filter changes clear that override. The effective-query callback also lets the inventory reader use the loaded historical flag. The wrapper sends the loaded immutable version hash with each saved-view draw. Unsupported saved sort/filter columns produce an explicit message rather than silently substituting a different query.

Saved-query calls use no-store fetches, CSRF for writes, abort controllers, scope/generation guards, and unmount cleanup. Explicit 401/403/409 clears saved metadata and blocks/unmounts the table. The UI does not infer or grant source access from labels, hidden columns, saved IDs or client state. Opening and refreshing the panel only reads data; saves and governance decisions require their distinct user actions.

`npm run build` from `frontend` passed after implementation and the loaded-version-hash patch (TypeScript and Vite, 73 modules; shared table JavaScript chunk 148.85 kB / 50.22 kB gzip). This reviewer has not claimed a browser action walkthrough or made saved-view governance changes against the live matter.

## Security conclusions and practical limits

The reviewed table flow obtains source metadata in SQL, applies the canonical PDP per row, and computes counts only from permitted results. Sort/filter names are allowlisted; caller values do not become SQL syntax. Financial amounts sort as Decimal. Selected exports recheck every ID and do not echo unavailable identities. Exported XLSX files are newly created from literal strings rather than copied native workbooks. Both dataset wrappers render user-controlled values through React components; current controls use context/current props rather than frozen row-action closures. The existing wrappers remount the shared table on matter changes. Hiding a column does not grant or remove access.

The table boundary tests and additional identity/content-label/approval-chain/reader-response tests found no unresolved row/count/file disclosure in the reviewed boundaries. Final saved-view integration, PostgreSQL and full-suite acceptance remain with the coordinating agents.

Remaining limits are material and explicit:

- Inventory authorization and authorization-input hashing still enumerate substantial matter state before returning a page. Reader candidate look-ahead can also scan and load many source/derivative records before finding enough permitted rows. Server-side paging is implemented, but 12,000-document/400,000-page performance has not been demonstrated.
- Financial tables reject scopes exceeding 100 permitted matching facts with 413. Selected exports are limited to 100 distinct IDs. These are bounded prototype behaviors, not full-corpus totals or bulk capacity claims.
- The 60-request/minute table throttle is per process. Multiple processes/hosts require a shared limiter and operational tuning; 15-second polling across tabs adds load.
- The fingerprint deliberately covers conservative matter authorization state. It is a change detector followed by current authentication/PDP checks, not a database serialization or instantaneous revocation mechanism. Conservative changes can require a retry.
- The UI refreshes authorization periodically and clears content on explicit denial. Already delivered data, offline pages, browser-rendered material and downloaded files cannot be remotely recalled.
- This independent suite covers the two implemented DataTables datasets and comparison increment. It does not establish migration of every application table or completion of every bulk action in the reusable-table prompt. No public launch, Azure migration, enterprise security clearance, or real legal approval follows from these fixture passes.
