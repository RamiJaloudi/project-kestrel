# 68 Authorized review intelligence and progressive clusters

Update: document 70 records the subsequently implemented organization gate, published score profiles, governed overrides and durable manual hot-alert scans. The phase-one limits below remain historical context for this read-only projection; its separate governance controls are now implemented as described there.

24 November 2026. [USER REQUEST] `Prompts-repository/features/dashboards-datatables/01_CLUSTER_HOT_DOCS_AND_SLA.md` and `features/financial-analytics/02_FINANCIAL_BANK_ACCESS_AND_HOTNESS.md` define the review-intelligence wheel, separate delay/legal/financial scoring and bank-specific restrictions. The user clarified **MFN means Most-Favored-Nation contractual clauses**.

[IMPLEMENTED] The first slice is a **read-only deterministic projection** over existing source, task, legal assessment, financial evidence and embedding records. It adds no legal approval, release, provider request, score override, alert policy, schema or migration. The existing independently approved SLA-alert workflow is reused for operational escalation. New durable hot-document alert records and configurable score-profile publication remain a separate subsequent slice; do not call the entire dashboard/alert specification complete on the evidence below.

## Endpoint and bounded projection

`POST /api/v1/intelligence/query` uses the normal authenticated session, same-origin CSRF and shared policy engine. Its strict input schema accepts the matter, view, path, typed source/financial filters, bounded search, independent score ordering and pagination. Unknown keys, arbitrary formula/score inputs, client elapsed time and a combined-priority flag are rejected. View paths are at most three groups deep; rows/group pages are at most 50 records. The default UI requests 20. There is no endpoint accepting a claimed actor or role.

```json
{
  "matter_id": "<permitted matter UUID>",
  "view": "workstream",
  "path": [],
  "sort": "delay",
  "search": "",
  "start": 0,
  "length": 20,
  "group_start": 0
}
```

| View | Progressive groups | Leaf |
|---|---|---|
| workstream | task stage → current authorized custodian → document type | Existing document reader |
| review | task stage → assigned reviewer → task state | Source/task reader |
| legal | reviewed legal topic → reviewed severity | Existing document/evidence reader |
| financial | authorized entity → exact period → metric | Cited released derivative for external users |
| topic | literal topic indicator → language | Authorized text-ready source; BM25 search |
| semantic | current cached cosine band | Authorized document with available cached vectors |
| hybrid | cached semantic plus BM25 → cosine band | Authorized document |

Counts are distinct authorized record IDs, not raw database totals. A source with several tasks/custodians/topics can belong to several children. Child counts therefore overlap and must not be added into a source total. The response explains this explicitly. An unavailable path returns an empty authorized result; it does not report denied group names/counts. Financial counts are fact counts rather than document counts, and the UI names them accordingly.

There is a declared demo limit of **1,000 permitted matching sources/facts** per query. Exceeding it returns a generic request to narrow typed filters, without returning a hidden total. Text topic/search projections use at most 16,000 characters per eligible source and a 2 MiB authorized corpus. These are focused local-demo bounds, not a claim that all 12,000 source documents can be clustered interactively in production. Production should replace this collector with incrementally maintained policy-aware projections and indexed keyset queries, retaining the same authorization contract.

## Authorization and bank isolation

The source collector reuses the canonical table inventory policy checks and then the existing source/task/custodian/retained-record checks. It obtains legal facts only through the existing permission-filtered diligence service. Custodian link retirement, effective dates and retained restrictions apply before names enter a group. Review activity observations keep the existing visibility rule: another reviewer's active/idle observations are not made visible merely by opening the dashboard.

Every contributing financial fact passes `financial.read` before its value, dimensions, evidence or existence enters the projection. Bank users need the active matter financial feature gate **and** the independently released, unexpired, current sanitized disclosure **and** the independently verified/released fact. The feature gate never grants row access. Original-source financial facts remain internal even after a bank feature toggle. Other audiences cannot gain Castlegate's derivative access merely by using its fact ID.

External users can request only Financial view. The response contains released fact dimensions and a disclosure reader target; it contains no parent source ID, internal task list, assignee, reviewer name, queue age, productivity statistic or reconciliation-case metadata. Internal-only fields are removed by an explicit projection before response serialization. The endpoint records a minimal `intelligence.query.denied` audit event for denied cross-audience requests, without logging supplied IDs, group terms or confidential passages.

The request reuses the existing authorization-input change detector and authenticates again after preparing the projection. Current policy, membership, wall, feature-gate, release/decision and recipient inputs must match. It then reauthorizes every contributing source/fact once more before returning **counts as well as rows**. A wall or approval change during projection yields a denied/conflict response and no prepared dashboard content. The browser clears old rows/details/readers while querying, on matter/view changes and on denial; requests are aborted on replacement. Results are not persisted to browser storage and use `cache: no-store`.

## Independent signal calculations

The response records a version (`deterministic-review-intelligence-v1`), each component's value, weight, evidence references and calculation basis. Scores use a weighted mean of **observed components only**. `UNKNOWN` components carry `null`; they never become zero. A score with some unknown components is visibly `PARTIAL`, with its observed weight shown against the full profile weight. No components available means an `UNKNOWN` score, not an invented risk estimate. A partial zero is only the absence of that observed signal; it does not establish low overall legal/financial risk.

| Domain | Component | Weight | Calculation or unknown basis |
|---|---|---:|---|
| Delay | pinned SLA overdue | 40 | Highest overdue business seconds / exact published budget, capped at 100 |
| Delay | queue age | 20 | Elapsed age above five calendar days / five calendar days, capped at 100 |
| Delay | reassignments | 10 | Observed reassignments / 3, capped at 100 |
| Delay | paused QC | 10 | Explicit QC pause: 100; observed open tasks without it: 0 |
| Delay | manual deadline | 10 | Explicit task deadline overdue / one elapsed day, capped at 100 |
| Delay | stalled active review | 10 | UNKNOWN: quiet or unobserved reading does not prove a stalled review |
| Legal | reviewed severity | 70 | Highest lawyer-reviewed critical=100, high=75, medium=50, low=25, information=0 |
| Legal | reviewed materiality | 20 | Explicit material=100, not_material=0; undetermined is UNKNOWN |
| Legal | transaction urgency | 10 | UNKNOWN until a reviewed transaction-deadline assessment exists |
| Financial | comparable variance | 60 | Different exact verified amounts with every comparison dimension identical: 100; comparable equal facts: 0; absent comparator: UNKNOWN |
| Financial | materiality/exposure | 20 | UNKNOWN: no approved monetary threshold/exposure policy is configured |
| Financial | period consistency | 10 | UNKNOWN: different valid reporting periods are not assumed inconsistent |
| Financial | verified evidence | 10 | 0 when eligible exact evidence is verified; otherwise UNKNOWN |

The five-calendar-day queue fallback is a transparent demo navigation default. It is **not** an applied business-day SLA. Published SLA policies continue to use their immutable calendar version, timezone-data version, selected weekdays, holidays, stage, paused-time treatment and budget. Their approvals/bindings are unchanged. The UI keeps queue age, active observations, idle observations, unobserved time, acceptance time, turnaround and business days open distinct. Missing timing observations stay UNKNOWN. A QC pause is an operational state, not a legal quality judgment.

Legal risk uses reviewed findings, not AI candidates or lexical matches. The financial score never sums amounts across currencies, dates, accounting bases or consolidation scopes. Variance only compares matching entity, metric, period dates, currency, accounting basis and consolidation scope, using canonical exact amount strings. It flags a comparison for review and does not select an authoritative value or expose an internal reconciliation assessment to the bank.

No combined hotness total is produced. No reviewer override or AI-generated explanation is claimed. The explanations shown are deterministic descriptions of the recorded components and their evidence. The endpoint does not invoke an LLM, change a score based on generated text or consume paid tokens.

## Lexical, semantic and mixed navigation

Literal English/German topic triggers include Most-Favored-Nation, assignment/consent, change of control, termination, exclusivity, competition clauses, data protection and financial metrics. They are clearly labeled lexical indicators, not an assessment that the contract contains an operative legal obligation. Only classification-confirmed, text-ready, human-verified OCR sources enter text clustering. An MFN trigger does not create a finding or a legal score.

BM25 reuses the existing deterministic adapter (`k1=1.5`, `b=0.75`) over the current already-authorized corpus. Unauthorized documents never affect document frequency or rank. Scores are retrieval navigation values and do not modify delay/legal/financial components.

Semantic and Hybrid require an explicitly selected currently readable seed with **existing** governed cached embeddings. The collector rechecks current source policy, analysis/processing permission, retained embedding restrictions, source snapshot, exact text span hash, vector hash, model/version and vector validity. Up to eight verified chunks per source contribute; similarity is the highest cosine between seed and candidate chunks. Bands at 0.8 and 0.5 are disclosed navigation choices, not calibrated relevance probabilities. Missing target caches appear UNKNOWN. A missing seed cache returns unavailable rather than silently buying embeddings or substituting lexical support. The seed itself can appear with cosine 1.

Hybrid uses reciprocal-rank fusion (`k=60`) over authorized BM25 and cached semantic ranks. This slice does not create an index, generate new embeddings or access a provider credential. The existing governed Questions semantic workflow remains the explicit place to create approved embeddings under its budget and approval rules.

## UI and existing operational alert reuse

`frontend/src/IntelligenceWorkspace.tsx` is a compact responsive workspace with exact matter choice, view selector, typed language/currency filters, search, score ordering, progressive breadcrumb navigation, a keyboard-operable SVG wheel, equivalent group buttons and paged rows. It renders a bounded number of group labels rather than thousands of document labels. Every row opens the existing `DocumentReader`; signal evidence preserves unit/offset anchors or task context. A details panel explains every component and its observed weight. External users receive Financial controls only.

The current `review_work`, `review_clocks` and `sla_alerts` services already provide durable task events, notifications, independent SME-approved escalation plans, deduplication by approved plan/level, recipient reauthorization, read receipts and disposition history. This view reads those task/SLA metrics and directs users to that existing workflow. Viewing or expanding the wheel does not create or approve an alert, legal finding, release or review task.

[NEXT SLICE / NOT IMPLEMENTED] New hot-document alerts need their own immutable score-profile versions, independent approval, scoped override history, exact trigger snapshots, durable deduplication, authorized recipient records and disposition timeline. Proposed migration number **0035 is reserved but no model/migration edit was made for this read-only slice**. Do not reuse generic notifications as legal approvals or silently modify existing SLA plans. A subsequent implementation should key alert dedupe by source/version snapshot, approved profile version and trigger revision, reauthorize the approving principal plus every recipient at execution, and create only explicit operational tasks. Saved/shared authorized cluster configurations and generated AI explanations also remain subsequent work.

## Validation evidence

[VERIFIED] New `test_intelligence.py`: **9 passed in 15.38 seconds**, using isolated test databases and no live-state changes. Tests cover UNKNOWN handling, independent evidence weights, authorized source/group/drilldown counts, root denial, clean-team source/name/count exclusion, task timing reuse, bank feature gate with original-fact denial, current released derivative-only bank drilldown followed by revocation, authorization change during projection, MFN lexical navigation without a legal score, strict bounded paths, cached semantic/hybrid navigation with provider calls stubbed only during cache fixture creation and no calls during dashboard projection.

TypeScript compilation passed. The existing frontend Vite build passed; the root integration must import the new component and mount the API/router before browser smoke can prove the live path. This task does not claim that an unimported file is already available in the running local service, that the public domains serve it, or that the complete hot-document alert specification has passed. No cloud resources, public deployment, source approvals, live database migration, model edit or new paid provider request was performed by this slice.
