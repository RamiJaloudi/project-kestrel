# 75 — Selected cross-domain security gate evidence

[DEMO / SELECTED MATRIX VERIFIED] This is a reproducible adversarial regression slice for `migrations/database-schema-evolution/02_CROSS_DOMAIN_SECURITY_REGRESSION.md`. Passing this selected matrix does not establish full feature completion, production readiness, production throughput, genuine legal approval or authorization to deploy.

The suite is `backend/tests/test_cross_domain_gate.py`. All records are fictional and created through the isolated test fixture. PostgreSQL runs create/drop disposable `kestrel_test_UUID` schemas; SQLite runs use temporary databases. No live content, source lineage, approval, signing record, public application schema, provider budget or deployment is modified. Provider-facing semantic tests replace the embedding adapter with fixed synthetic vectors. Graph execution uses the offline deterministic workflow and temporary private checkpoints. Distinct fixture accounts exercise independent approval; they do not impersonate a real human legal decision.

## Scope and observable boundaries

| Scenario | Observed boundary |
|---|---|
| Combined Root and legal roles, enabled technical gates, then a matter wall |20 read surfaces and8 query/count/export/compare commands must deny without source names, quotes, query text, counts or files. Root's technical authority cannot countermand a legal wall. Denial audit records retain safe actor/action metadata. |
| Independently approved client-level person wall |Both assigned matters become unavailable, including owner-only saved configurations with no source references and zero matching rows. |
| A foreign matter with a known source ID |Inventory counts exclude it; selected exports report an unavailable count without the foreign ID/name; reader, financial query and task creation deny; a SQL-like entity string remains a literal filter. |
| Provisional source restriction applied to a nonselected member of a cached semantic corpus |The old answer cannot retain counts/ranking metadata from that now-denied corpus. Its stored embeddings remain retained without granting access. Fresh lexical and cached semantic/hybrid groups contain only currently permitted evidence; dashboard reads make no provider calls. |
| Exact named Halden clean-team source grant |Only its precise source can appear in permitted reader/table/compare results. It does not grant general original-source, task, DDR, registry, bank or external metadata-export access. Unapproved/self-approved scope relaxation cannot take effect. Revoked current clean-team membership closes future reads/counts while approval history remains retained. |
| Source labels change after separate artifact/fact releases |Bank fact tables and financial clusters drop the stale evidence; old financial answers and private saved configurations deny; original/derivative comparison panes cannot expose denied content. Original legal and financial approvals remain retained; counsel-impact records appear. |
| Signing with table views, scoring profiles, agent versions and a cancelled graph's retained report/tasks/artifacts |Future manifests include the retained domains. Source, label, view, DDR, agent and scoring writes freeze; read-only staged attachment access and access-tightening share revocation remain possible. A legal hold blocks client-copy deletion. Subsequent closure/hold release permits only the authorized client-copy deletion, preserving firm source/email bytes and the exact original signing payload. DB triggers reject destructive changes to retained configuration/artifact tables. |
| Identity/authority changes during response preparation |Reader tests cover a new wall, session revocation, account deactivation and revoked assignment. Lexical quotes, direct financial counts/amounts, scoring-profile metadata, retained task details and complete report-list bodies must be withheld after mid-request scope loss. Root technical profile reads must succeed before the wall and fail after it. |

The wall matrix includes source detail/reader/download/list, findings, comparison candidates, review tasks and notifications, Q&A history/cached answer, reports/Word access, DDR list/detail/options, table-view list/detail, agent registry metadata, scoring profiles/alerts, inventory/financial queries, metadata export and multi-pane comparison. It does not enumerate every application route or prove every concurrency interleaving.

## Findings and repair verification

The first four race regressions failed on SQLite: source reader presentation returned200 with text after a new wall; lexical Q&A returned201 with quotes; direct financial query returned200 with amounts/counts; scoring-profile metadata returned200 after current person authority had changed. These were real missing fresh-response boundaries rather than fabricated provider failures.

Root added a common authenticated response guard for the first three route families. Scoring-profile/intelligence governance received a separate role-preserving response guard. All repaired cases passed in the complete current SQLite and PostgreSQL runs. Tests also exercise revoked sessions, inactive accounts, revoked matter assignments and Root's valid technical-read path, so a patch cannot merely deny all Root requests to make the negative case pass.

A further route audit confirmed two analogous gaps: retained review-task detail and complete report-list bodies could return 200 after a new wall during their final projection. Root added the corresponding response guards; the suite now contains 17 cases, all of which passed on both databases. No production code was edited in this test-only slice; the corresponding implementation owners made the repairs.

Final sanitized evidence:

| Database | Cases passed | Failed / skipped | Duration | Migration head |
|---|---:|---:|---:|---|
| SQLite temporary databases |17|0 /0|96.51 seconds|0037|
| PostgreSQL disposable schemas |17|0 /0|58.16 seconds|0037|

Test-file SHA-256: `c8e71f6d32d7f7a6350a444dd00b3f4e0205bad56a208268926c0cae6ef8d2e0`. These are correctness checks under local test load, not throughput benchmarks. The two database runs exercise the same 17 cases; they are not 34 distinct scenarios.

Checkpoint results actually executed by this agent:

- Initial fresh-response diagnostic: **4 failed**, 14.36 seconds. Those failures were reported to the implementation owners.
- Selected six nonrace cross-domain cases: **6 passed**, 25.69 seconds.
- Signing/retention case: **1 passed**, 23.51 seconds.
- Complete current SQLite suite after repairs and expanded identity variants: **15 passed**, 61.68 seconds.
- Subsequent task/report-list diagnostic: **2 failed**, 10.58 seconds; repaired before the final runs.
- Complete PostgreSQL matrix after all repairs: **17 passed**, 58.16 seconds, at migration head 0037 in disposable schemas. Fixture schemas cleaned up normally; the live/public application schema was not mutated.
- The first full 17-case SQLite rerun reached 16 passes and one test-assertion wording failure: the existing SQLite agent trigger reported `agent governance records retained`, while the test required the literal word `immutable`. The assertion now accepts either explicit retained-record/immutability denial and still excludes foreign-key-only failures. The complete corrected SQLite run passed **17 cases**, 96.51 seconds.

## Reproduction

From `Freshfields_Codex_Handoff/backend`, using its existing virtual environment:

```powershell
$env:KESTREL_TEST_POSTGRES='0'
.venv\Scripts\python.exe -m pytest tests/test_cross_domain_gate.py -q --disable-warnings --tb=short

# Only after the local PostgreSQL service is ready and coordinated fixture runs are permitted:
$env:KESTREL_TEST_POSTGRES='1'
.venv\Scripts\python.exe -m pytest tests/test_cross_domain_gate.py -q --disable-warnings --tb=short
```

Local socket access may require the test runner's elevated transport permission. Keep traceback output short; do not print database URLs, credentials, fixture request bodies or protected passages into diagnostic logs.

## Remaining limits

This suite supplements the component suites for source classification, validated disclosures, reader panes, exact financial evidence, retrieval, table exports/views, agent registry approval/impact and durable graph execution. It does not replace those suites or operational acceptance. The selected metadata-export checks do not establish bulk assignment/reprioritization/reanalysis behavior. Native layout-preserving redaction, broad legacy converters, production identity/information-barrier integrations, malware scanning/OS isolation, provider outage and spending drills, production checkpoint protections, 12,000-document/400,000-page load testing and approved external deployment remain independently assessed work.

Older downloaded files cannot be remotely recalled. No test result authorizes changing that fact, relaxing source classifications or publishing a report automatically. The wider implementation plan must continue to mark partial or unsupported capabilities honestly.
