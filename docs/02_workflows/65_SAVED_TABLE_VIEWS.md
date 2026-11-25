# 65 — Retained saved DataTable configurations

[IMPLEMENTED / LOCAL DEMO] Migration `0034` adds six tables without rewriting sources, approvals, releases or earlier signing manifests: `table_views`, `table_view_versions`, `table_view_evidence`, `table_view_shares`, `table_view_share_recipients`, and `table_view_share_decisions`. Their rows reject UPDATE and DELETE on SQLite and PostgreSQL. An empty increment can be downgraded; any retained saved-view record prevents downgrade before any table is removed.

Saved configurations contain potentially protected names and search/filter text. They are private by default. Matter membership alone does not grant access to another person's configuration. Root Admin has no content override. A saved view does not authorize a document, fact, export, assignment, reanalysis or any other action.

## Configuration contract

`POST /api/v1/table-views` accepts `matter_id`, `dataset` (`inventory` or `financial`), `name`, a strict existing `TableQuery`, `handling`, `evidence_refs`, `rationale` and `request_key`. The query must name the same matter and use that dataset's allowed sort/filter columns and typed advanced filters. Unknown fields, arbitrary column names and regular-expression options are rejected. Global/column search remains literal substring search. Transport `draw` and `start` normalize to zero. A saved view cannot recursively reference another saved view.

`GET /api/v1/table-views?matter_id=…&dataset=…` lists only the current actor's permitted configurations and current approved named shares. `GET /api/v1/table-views/{id}` rechecks the same access. Responses identify the immutable version/hash and ownership. `POST /api/v1/table-views/{id}/versions` requires `expected_version_hash` and the configuration fields. Matter, dataset and owner are fixed. Append-only revisions preserve prior configuration text, evidence and decisions. Request keys prevent changed-payload retries; stale concurrent version updates fail.

`private_unclassified` explicitly records that arbitrary user text has not been classified. Internal owner-only configurations may have no evidence and match zero rows. They cannot be shared. `source_bound` requires explicit source references for inventory, or financial-fact references for financial views. These references are evidence/handling declarations; they do not assert automatic semantic classification of all user text. Named sharing requires independent human review of all text and its handling.

Each evidence reference captures the current canonical source/derivative policy snapshot and original retained classification/clean-team scope. Every configuration read/use rechecks current matter assignment, walls, role, clean-team scope, source integrity, source/derivative policy, fact eligibility and the captured restrictions. Changed policy attributes deny the old configuration. Its owner may append a newly bound version; old approvals do not transfer.

Bank users can create only private financial configurations with explicit active released financial-fact references and the current enabled bank gate. Financial fact authorization still requires its separately approved derivative and release. Responses expose fact references rather than original source IDs. Client saved views and external sharing are outside this baseline.

## Named internal sharing

`GET /api/v1/table-views/recipients?matter_id=…&dataset=…` returns current active, assigned, unwalled firm legal identities. The selected configuration's evidence is independently checked for every chosen recipient when sharing is requested and approved. The endpoint is an eligibility aid, never a grant.

`POST /api/v1/table-views/{id}/share-requests` accepts `version_hash`, distinct named `recipient_ids`, `expires_in_days` (1–30), `rationale` and `request_key`. Only the owner can submit an exact source-bound version. The baseline allows firm-to-firm sharing only. No original source or legal restriction is relaxed.

`GET /api/v1/table-views/share-requests?matter_id=…&dataset=…` supplies exact configurations and immutable request hashes to current source-cleared independent SMEs. Recipients and requesters cannot self-approve. Expired, rejected and revoked requests do not grant a reviewer a configuration-reading channel.

`POST /api/v1/table-views/share-requests/{id}/decisions` accepts `operation` (`approve`, `reject`, `revoke`), exact `content_hash`, `content_reviewed` (boolean) and `rationale`. Approval requires a source-cleared SME distinct from owner, requester and all recipients, plus `content_reviewed: true`. This attests human review of the entire configuration, names, filter/search text, provenance, sharing rationale and named audience. It does not replace separate disclosure/declassification approvals.

Every recipient read/use rechecks expiry/revocation, the exact configuration and request, current owner authority, current independent SME authority, and the recipient's own evidence access. A new owner revision does not inherit prior sharing; recipients continue to see only an independently approved version they remain entitled to use. Revocation retains prior decisions and can tighten access after signing or source drift without returning stale configuration text.

## Integration and boundaries

`TableQuery.saved_view_id` loads an authorized saved configuration as the authoritative query, preserving only the incoming `draw` and `start` transport values. Optional `saved_view_version_hash` must accompany a saved-view ID and match the version loaded into the client controls; a mismatch returns409 before scanning, preventing another tab's updated filters from silently replacing the displayed query. The client clears the ID/hash when the user edits live search, sorting, page size or advanced filters. The endpoint resolves again after scanning and fresh authorization, and compares the exact immutable version hash; even a rename with identical filters invalidates an in-flight response. Revoked/expired shares return no rows or counts. `table_views.resolve_query(db, actor, id, expected_matter, dataset)` remains available as a validated-query helper. Per-row PDP remains mandatory for every query/export.

The six tables join future lifecycle manifests and the write guard; new writes are frozen after signing, except retained share revocations. Protected audit references resolve to the union of retained evidence restrictions. Historical signed manifests remain unchanged. Access logs contain IDs and decisions rather than saved names or query text.

## Verification and remaining work

Isolated integrated SQLite suite: `python -m pytest tests/test_table_views.py tests/test_data_tables.py -q --disable-warnings --maxfail=1 --tb=short` — **22 passed** (39.42 seconds; one dependency warning). Fourteen saved-view tests cover owner/root isolation, cross-matter evidence and query checks, strict filter contracts, immutable versions/concurrency/idempotency, named independent sharing, expiry/revocation, current approver/recipient clearance, clean-team source drift, external denial, bank gate/released derivative/fact revocation, retained downgrade refusal, all-six-table signing coverage and post-signing revocation, authoritative saved-query transport, exact-version changes during scans, and sharing revocation while scanning. Eight existing DataTable tests remain passing.

The additional client-loaded version-hash guard and owner sharing history across prior revisions passed a subsequent **23-test SQLite run** (63.41 seconds;15 saved-view cases plus8 existing table cases).

The loaded-version-hash and owner prior-version share-history cases also passed on PostgreSQL in the subsequent **seven-case boundary run** with the converter workflows (23.38 seconds).

PostgreSQL verification: `KESTREL_TEST_POSTGRES=1 python -m pytest tests/test_table_views.py -q --disable-warnings --maxfail=1 --tb=short` — **14 passed** (29.55 seconds; one dependency warning), using disposable `kestrel_test_UUID` schemas and elevated local socket access. An initial sandboxed socket attempt timed out; a coordinated database shutdown interrupted a later fixture run. Neither interrupted attempt is counted as a successful full run. The one exact interrupted fixture schema was removed after restart; the final successful fixtures cleaned up their own schemas.

This baseline limits a view to 100 immutable versions and each version to 100 retained share requests; configuration lists/review queues return at most 100 permitted entries. This document does not claim full DataTables coverage across all product tables, production scale, group sharing, external saved-view sharing, automated sensitive-text classification, notifications or real legal approval. No live approval, new content grant, paid model call or public deployment is part of this increment.
