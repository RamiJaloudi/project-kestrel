# DDR graph foundation and integration protocol

[DEMO] 24 November 2026. This is an actual bounded LangGraph implementation with an offline fake provider and injected application services. It is not yet the complete durable DDR application, approved legal configuration, enterprise provider connection or a release workflow.

## Implemented scope

`backend/kestrel/ddr/graph.py` builds a real `StateGraph`: coordinator/evidence validation → contracts specialist → draft → parallel quality and deterministic citation verification → join → idempotent external review-task creation → human interrupt. Validation failure stops before human review. There is one initial contracts workstream, at most three model calls, concurrency one or two, a bounded recursion limit and output-token ceiling. There is no automatic revision loop, permission-management tool, publication tool or release/export tool.

`schemas.py` distinguishes transient evidence/claims/draft/quality objects from opaque checkpoint references. `evidence.py` verifies exact requested finding coverage, original Unicode offsets, quote/unit hashes, source/version binding, citation identity and unchanged reviewed severity. This proves integrity and binding, not semantic entailment or legal correctness. The fake quality reviewer is deterministic fixture behavior; its pass is not independent legal review.

Checkpoints contain the immutable run specification, opaque artifact/task/approval references, hashes and phase. Source passages, model messages, prompts, draft text and quality prose stay outside checkpoint state. Artifact reads verify the retained hash, including again at human review/resume. The application must protect the external artifact and evidence store using the current canonical PDP.

The official [Graph API](https://docs.langchain.com/oss/python/langgraph/graph-api) supplies typed state, graph nodes and parallel edges. LangGraph [interrupts restart their node on resume](https://docs.langchain.com/oss/python/langgraph/interrupts), so task creation is in a separate idempotent node. A resume is only an acknowledgement; the graph rereads the external approval record. A [checkpointer persists graph state](https://docs.langchain.com/oss/python/langgraph/persistence), while application artifacts and the legal decision remain separate records.

## Root service adapter contract

`DdrEngine(ports, provider, checkpointer, clock=time.time)` exposes:

```python
engine.start(spec, active_deadline_epoch=deadline)
engine.continue_run(spec, active_deadline_epoch=fresh_deadline)
engine.resume(spec, active_deadline_epoch=fresh_deadline)
engine.status(spec)
```

`RunSpec` contains server-derived `run_id`, `requester_id`, `matter_id`, immutable `graph_version`, `snapshot_hash`, `config_hash`, exact opaque reviewed `finding_refs`, overall `deadline_epoch` and `Limits`. The overall deadline can represent the seven-day run expiry. Each start/continue/resume gets a fresh active execution deadline capped at 120 seconds; a human pause does not consume that active allowance. Provider timeouts remain bounded separately.

`GraphPorts` is authoritative and must use fresh per-call/per-thread database sessions where parallel nodes operate. Its methods are:

| Method | Required application behavior |
|---|---|
| `authorize(spec, stage)` | Re-derive current internal requester/service capability; enforce matter, wall, clean-team, current source lineage, processing policy, approved configuration, cancellation and expiry. No graph field grants access. |
| `evidence(spec)` | Return a typed transient `EvidenceBundle` from exactly the retained reviewed finding revisions. Validate current native bytes/text/policy/OCR and the expected snapshot/config hashes. |
| `execute_once(spec, step, input_hash, producer)` | Serialize attempts across workers and persist the produced typed artifact with a server-owned `ArtifactRef`. Reuse completed identical attempts; refuse changed inputs or uncertain paid completion. A process crash must not cause an automatic second paid attempt. |
| `artifact(spec, reference)` | Authorize and return the exact typed external artifact. The graph compares its canonical hash to the reference. |
| `reserve(spec, step, estimated_input_tokens, max_output_tokens, live)` | Atomically enforce aggregate run call/token/cost limits and the shared application monthly ledger before the provider executes. Enforce the actual provider/purpose policy; the estimate is not authoritative provider usage. |
| `settle(spec, reservation, usage, uncertain)` | Reconcile actual input/output tokens and approved-model pricing. Retain reservations for unknown/ambiguous completions. No automatic retry or failover. |
| `review_task(spec, draft, validation, key)` | Create/reuse one protected attorney-review task for the exact draft and validator references. This does not approve it. |
| `approval(spec, draft, validation)` | Read an independently authenticated immutable decision. Recheck reviewer role, current source clearance and exact draft/snapshot/config. The reviewer must differ from both requester and draft creator. Return `ApprovalReceipt` or `None`. |

The graph checks receipt hashes and independence itself as well. A pending resume interrupts again. A reject ends as rejected. An approve marks only the graph's internal phase after observing the external authority; the graph does not create that authority. Existing release routes must separately enforce the actual internally approved DDR version, audience release and antitrust requirements.

`start`/`continue_run` detect pending noninterrupt nodes and continue with `invoke(None)`, so a crash after a durable artifact commit can recover through `execute_once` without repeating completed producers. Human resume uses `Command(resume=...)`. An ambiguous provider attempt remains failed closed through the external attempt ledger. Raw thread IDs are private implementation details and must not become an unauthenticated checkpoint API.

## Providers and dependency evidence

`FakeProvider` makes no network calls and retains only stage names. `ChatOpenAIProvider` uses the actual [LangChain ChatOpenAI integration](https://docs.langchain.com/oss/python/integrations/chat/openai), typed structured output, explicit credentials/configuration/pricing, bounded timeout/output, `max_retries=0` and disabled external tracing. It is disabled by default. The graph's processing-policy and budget ports are still mandatory when a live adapter is enabled. No paid or live provider invocation was performed.

Resolved and installed in isolated `C:/Freshfields-Takehome/.ddr-build-venv`: LangGraph **1.2.24**, langchain-core **1.8.4**, langchain-openai **1.8.5**, checkpoint **4.3.2**, SQLite checkpointer **3.1.3**, OpenAI SDK **2.54.0**. `backend/requirements-ddr.lock` pins all 48 resolved transitive versions, constrained against the existing tested baseline. `pyproject.toml` exposes exact primary optional `ddr` pins. Native wheels were resolved on Windows/Python 3.12; this is not Linux/Azure verification. New LangSmith dependencies include httpx2, so the root-controlled application/runtime installation needs its full regression check. The active backend virtual environment was left unchanged by this foundation.

## Tests actually run

From `backend`:

```powershell
C:/Freshfields-Takehome/.ddr-build-venv/Scripts/python.exe -m pytest tests/test_ddr_graph.py -q --tb=short
C:/Freshfields-Takehome/.ddr-build-venv/Scripts/python.exe -m pip check
```

Result: **22 passed in 3.52 seconds**; **no broken requirements**. Coverage includes physical SQLite checkpoint close/reopen and a reconstructed engine; source/summary canaries absent from checkpoint bytes/state; real pending interrupt/resume; acknowledgement without approval; immutable independent receipt/hash checks; reviewer/requester revocation and snapshot/config drift; post-review artifact tampering; rejected and failed-quality outcomes; actual two-node parallelism; completed-producer crash recovery; uncertain-provider reservation retention and refusal to resend; Unicode/hash/severity/coverage validation; active execution deadline; fresh deadline after a one-hour review pause; and a disabled live adapter that never constructs an API client.

The SQLite tests persist checkpoints but use a test-only in-memory artifact/attempt/approval adapter. They do not prove application-wide restart durability, PostgreSQL locking, production telemetry isolation, semantic citation quality, live provider behavior, governed agent publication or release-endpoint integration. Those remain root integration/acceptance work. Optional graph tests explicitly skip where the DDR extra is absent; their executed isolated result above must not be substituted for a skipped application run.
