# CODEX IMPLEMENTATION PROMPT — PROJECT KESTREL MULTI-AGENT DUE DILIGENCE REPORT ENGINE

**Status:** User-approved requirements, November 23, 2026. Apply as a new feature to the **existing local Project Kestrel codebase**. Do not rebuild the repository or discard previously working modules.

## 0. Operating instructions: read first, preserve existing project

You are the lead Python/FastAPI, LangChain, LangGraph, React/TypeScript, data-engineering and legal-technology architect working on **Project Kestrel**, a fictional Freshfields Lab M&A technology design assessment.

Before editing code:
1. Inspect the actual local repository; read `AGENTS.md`, existing design documentation, current API contracts, auth/ABAC policy code, playbook schemas, audit, legal review, finding release, and report APIs. Find tests and run a baseline. Do not pretend you found missing files.
2. Locate the user-supplied **21-page M&A Due Diligence Checklist**, named `Contract-Content-Due-Diligence_Checklist.pdf`. The user's Windows source folder may be `C:\Freshfields-Takehome\Due_Diligence_Checklist\`; search only the local project and that explicit location, or ask for the file if not present. Do not rely on path without checking. It is **a document-request checklist, not an existing due diligence report/template**. Use it as an input taxonomy and evidence/completeness checklist, while designing an **original, editable, fictional Freshfields-style Project Kestrel DDR**. Do not claim the output is an official firm template or recreate Bloomberg Law branding.
3. Read the original five-page Freshfields assessment if present. Its fictional scenario controls: UK-listed Halden Industries plc buying private German Vireo Systems GmbH, Castlegate as bank adviser, six-wave VDR, 12,000 documents/approximately 400,000 pages, 20% German, scanned PDFs, restricted customer pricing, client/bank separation, attorney review and source citations. Firm tools/production deployment are separate from the candidate's demo.
4. Make **small, testable increments**. Start with a design and directory-level implementation plan, then implement the smallest complete vertical slice. Do not offer a fake or decorative agent UI instead of functioning LangGraph orchestration.
5. Clearly label `[EXISTING]`, `[TO BUILD]`, `[ASSUMPTION]`, `[DEMO]`, and `[PRODUCTION]`. Report exact tests run, limitations and costs. Keep everything local and synthetic until authorized to deploy; do not expose the workstation publicly.

## 1. Mandatory framework choice and model provider strategy

- **LangGraph** owns workflow orchestration: `StateGraph`, explicit node transitions, `Send` for bounded fan-out, checkpointing, conditional retries, interrupts for human decisions, and resumable execution; no unbounded recursive agent loops.
- **LangChain** supplies model-provider adapters, model-agnostic chat interfaces, structured output, prompt templates, tool binding, document retrievers, and instrumentation as warranted. Use stable compatible versions and lock dependencies; avoid deprecated APIs.
- **OpenAI API is the actively configured local provider**: make a real OpenAI-backed path work in local development, with configurable model IDs, timeouts, token limits, and clear configuration. **Never commit API keys**. Add provider interface(s) for Azure OpenAI, Google Vertex AI/Gemini, and local Ollama; these are OPTIONAL adapters until configured and tested; never claim they already work.
- Enterprise target architecture uses only models and EU regions approved by the actual firm; no production data leaves allowed boundaries. Model failover must respect classifications, data residency, vendor allowlists, permitted processing purpose, and matter `AI_RESTRICTED` flags. If no policy-approved model is available, fail closed / pause.
- Neither tools nor agents may directly override attorney findings, authorize reanalysis, change legal content approvals, grant permissions, release to Halden/Castlegate, approve clean-team publication, or publish advice.

## 2. Role-specialized multi-agent graph (real roles; reusable tools)

Implement an explicit **DDR Report Coordinator** graph with these nodes or subgraphs. Some specialist agents should execute concurrently when permitted; do not overcomplicate simple deterministic validations with LLMs.

1. **Coordinator / Planner**: validates report scope, matter, audience, requester rights, frozen/version state, approved playbooks, and checklist version; decomposes into workstreams and budgets. Outputs `ReportPlan`, not report prose. Distinguish requester vs service identities.
2. **Checklist Coverage / Gap Analyst**: maps the uploaded checklist's A–N categories to configurable `ChecklistItem` records and verified document inventory. Outputs REQUESTED / RECEIVED / UNDER_REVIEW / VERIFIED / GAP / NEEDS_CLARIFICATION / N_A_APPROVED_BY_HUMAN. Never infer N/A from absence and never infer that absence proves noncompliance. Turns gaps into draft information requests for attorney review, not unauthorized outbound messages.
3. **Evidence Retrieval Agent**: **authorization-filtered**, version-specific retrieval of existing lawyer-reviewed findings and linked original source excerpts. Must log source IDs, page/clause, original language, translation when available, OCR quality and provenance. Uses no unrestricted generic search index. If evidence is not authorized, report inability to substantiate; no raw denied document text in logs, prompts or messages.
4. **Specialist agents** (may run in parallel with bounded concurrency, scoped inputs and scoped ABAC):
   - Corporate / ownership / German GmbH formalities (A)
   - Finance, indebtedness and tax (B, C, D), with non-lawyer numeric assertions marked for finance or counsel validation
   - Property / leases / equipment (E)
   - IP / technology / software licensing (F)
   - Commercial and material contracts, change of control, assignment, exclusivity, termination, liability caps, governing law (G and relevant H)
   - Litigation and disputes (I)
   - Regulatory approvals / competition / FDI / anti-trust (J, and transaction-specific additional playbooks)
   - Employment / labor / works-council matters (K)
   - Privacy, GDPR, security and data incidents (L)
   - ESG, environment and related risks (M)
   - Custom jurisdiction- and transaction-specific requests (N)
   Dynamically select specialists according to approved matter-specific checklist scope, source availability, and active playbooks. The specialist must act as an **M&A-attorney-trained analytical assistant**: identify legal issues and drafting considerations with professional care, but **must not claim to be a licensed attorney, render definitive legal conclusions unsupported by reviewed authorities, or replace counsel**.
5. **Synthesis / Risk Prioritizer**: reconcile duplicate findings, group by legal category and severity, distinguish actionable issues from open diligence questions, identify key change-of-control contracts for Halden's board, and surface caveats/coverage limitations. Cannot raise privileges or rewrite approved finding severity. New candidates go back to attorney queue; no silent promotion to approved findings.
6. **DDR Drafter**: creates an original **fictional Freshfields-style Project Kestrel report** from attorney-approved findings with source references. Draft report sections: cover and confidentiality labels, scope/methodology/cutoff, executive summary, key findings and risk heat map, transaction overview, legal workstream chapters, material contracts/CoC schedule, risks and recommendations, consent/deadline action tracker, open questions/information gaps, assumptions/limitations, appendices and citation register. Do not imply an officially supplied Freshfields DDR template exists. Keep report version and underlying evidence snapshot fixed.
7. **Independent AI Quality Reviewer**: checks coherence, contradictions, completeness against checklist statuses, unsupported claims, invented law, unauthorized content, stale versions, conflicting results, audience restrictions, and alignment with approved playbooks. Reviewer cannot itself approve the draft for external publication.
8. **Deterministic Evidence & Citation Verifier** (ordinary code/tool, NOT just LLM): require each material claim to link to authorized lawyer-approved finding(s) and validated document/page/clause spans; verify document/version still exists and text span provenance matches; original German quote vs marked English translation; reject or flag unsupported sentences; do not fabricate pinpoint citations.
9. **Attorney Review / Approval Gate**: interrupt/resume with actual authenticated authorized Freshfields attorney user. Review in portal; approve, request changes, reject, or assign; preserve rationale and version history. Human approval of report is separate from permission to release to a particular audience. Separate antitrust counsel clean-team review applies to sanitized or aggregated outputs when applicable.
10. **Export / Publication Service**: create editable Word `.docx` and in-portal rich report draft. PDF export is available for reviewed/approved versions per policy. Exports enforce same audience and derivative restrictions. External release via existing reviewed publication workflow only; no agent direct publishing. Preserve document version, source finding snapshot, digital audit trail and download permissions.

Graph outline:
`START → coordinator → checklist_coverage → scoped_retrieval → parallel_specialists → synthesis → drafter → [LLM_reviewer + deterministic_citation_verifier] → {revise bounded | needs_missing_evidence | ready_for_human} → attorney_review_interrupt → [internal_approved] → audience_release_gate → DOCX/portal/PDF → END`.

**Important**: If the user's checklist is primarily a list of documents to request (it is), the specialist graph must not treat it as a pre-existing legal opinion, legal authority, evaluated findings, or reporting format. Operate only on document inventory, approved evidence and attorney findings. Use independently authored task descriptions/playbooks; do not embed large verbatim copyrighted checklist text or distribute the PDF without permission.

## 3. Checklist → playbook → tool mapping

Create `ChecklistRegistry` and machine-readable taxonomy based on the real PDF; see `CHECKLIST_TAXONOMY.json`. Each item should support:

- `checklist_id`, `section_code`, `section_title`, `item_number`, `short_abstract`, `source_document_ref`, `source_page`, `source_version`
- `matter_scope` / business materiality, document types, jurisdictions, potential governing laws, languages, conditional applicability and `approved_na_reason`
- `required_evidence_types`, `diligence_status`, `owner`, `linked_document_versions`, `approved_finding_ids`, `missing_information`, `audit`
- `specialist_agent_id`, `approved_playbook_version_ids`, `registered_tool_ids`, `report_section_mapping`, `security_labels`, `clean_team_restrictions`

Root Admin manages **technical** agent configurations, model routing, graph versions, allowed tools, retry/concurrency budgets and runtime configuration. Authorized Legal SME/Knowledge Lawyer separately approves new or materially changed substantive analysis/drafting prompts, checklist legal interpretations, specialized tools' legal rule configurations and playbooks. **No self-approval**. Published legal versions immutable. Changing them triggers impact assessment, durable SME notifications, and separately approved reanalysis of affected findings. Do not silently rewrite previously reviewed legal conclusions.

A shared, versioned, registered tool catalog should include (names illustrative):
- `validate_matter_and_actor`, `authorize_resource_action`, `resolve_effective_doc_attributes`, `get_document_version`, `get_approved_findings`, `get_source_passages`, `validate_citation`, `get_checklist_item`, `list_checklist_gaps`, `get_approved_playbook`, `get_verified_legal_authorities`, `get_report_snapshot`, `write_report_draft_version`, `create_attorney_review_task`, `render_docx`, `render_pdf`, `audit_graph_action`.
- Tools use typed inputs/outputs, least-privilege service identities, explicit matter and audience scope, allowlisted operations, and central policy enforcement; they never accept a caller-supplied actor ID as proof of identity.
- Prefer deterministic Python services for OCR offsets, ABAC decisions, deduplication, calculations, citation verification and export formatting. LLM agents should reason and write only within evidence constraints.

## 4. SECURITY NONNEGOTIABLE: the graph cannot bypass the policy engine

This codebase has Client-Matter Validation, Ethical Walls and **document-state/type ABAC** goals. Design every graph node and tool as a **policy enforcement point** or call a centralized PEP/PDP with policy-consistent decisions. Respect the user's existing `ethical-walls-matter` reference architecture and improve upon it: OAuth/service auth, explicit deny precedence, matter flags, batch checks, policy revision consistency, audit and fail-closed behavior.

Enforce on EACH access and action: authenticated user and organization, exact matter grant, ethical-wall denial, resource ACL, document-derived attributes and lifecycle (`INGESTED`, `CLASSIFIED`, `UNDER_REVIEW`, `ATTORNEY_APPROVED`, `RELEASED`, `FROZEN`, `ARCHIVED` as applicable), confidentiality, privilege, clean-team membership, audience, permissible AI processing/provider/region, purpose and policy revision. Attribute classifiers can propose more restrictive labels, but **only authorized humans may declassify** under governance policy. Recheck at async resume and export time. Never let document language determine governing law.

Derivatives INHERIT the union of source restrictions until independently approved release: OCR text, embeddings, chunks, citations, summaries, draft paragraphs, RAG answers, reports and exports. A cross-source synthesis must not wash away highly restricted labels; permissible sanitization/aggregation requires documented approval, with separate clean-team counsel as applicable. No external exposure of client-only privileged advice to Castlegate; never give competitive pricing to ordinary Halden business users. Users barred by firm ethical walls cannot learn even matter content through logs, task titles, counts, summaries, model prompts, embeddings or error messages.

Injected instructions embedded in the VDR are untrusted data; no PDF/contract text may instruct the agent to ignore policy, reveal secrets, call tools or modify approvals. All external actions and network access are explicitly allowlisted; no arbitrary python/shell/web browsing tools delegated by default.

## 5. Structured state and persisted evidence

Implement typed Pydantic models for `ChecklistItem`, `ChecklistCoverage`, `ReportPlan`, `SpecialistAssignment`, `EvidenceRef`, `SpecialistResult`, `RiskSummary`, `ReportSection`, `DraftReport`, `CitationValidation`, `QualityReview`, `ReportApproval`, and `ReportRun`. Define LangGraph `TypedDict` or `BaseModel` workflow state; include:

`run_id`, `matter_id`, `requester_id` (server derived), `requested_audience`, `report_kind`, `document_cutoff`, `evidence_snapshot_id`, `checklist_version_id`, `playbook_version_map`, `graph_version`, `model_routing`, `policy_revision`, `authorized_document_ids` (opaque refs), `assignments`, `results`, `coverage_gaps`, `draft_section_refs`, `citation_errors`, `review_feedback`, `review_iteration`, `max_iterations`, `token_budget`, `cost_budget`, `status`, `error_codes`, `audit_correlation_id`.

Keep secrets and long confidential raw passages OUT of persisted graph state and ordinary logs; store sensitive content in access-controlled evidence stores and pass opaque references. All graph resumes reauthorize. Use a local checkpointer for demo only; production checkpoint store should align with the approved database and retention requirements. Support idempotent run creation, cancellation, restart/retry, deadlines and partial failures.

Recommended structured `SpecialistResult`: `workstream`, `covered_checklist_ids`, `eligible_approved_finding_ids`, `evidence_refs`, `issue_ids`, `coverage_gaps`, `open_questions`, `proposed_section`, `security_labels`, `quality_flags`, `review_required`. The agent does not generate authoritative legal findings from raw text during DDR compilation; if new issues arise, queue a **new, unapproved** finding.

## 6. Report authoring, editing and delivery requirements

- Deliver editable **Word as primary**, plus version-controlled rich-text editing in the Freshfields portal, plus PDF export under authorized policy. Provide links for citations that resolve to the correct matter/document/version/page in the authorized source viewer; no broken or hallucinated citations.
- All internal versions labeled `DRAFT / AI-ASSISTED / SUBJECT TO FRESHFIELDS ATTORNEY REVIEW` until human approval, and no institution-branded claim of actual official Freshfields template. User-requested narrative/style: sophisticated M&A legal memo, concise partner and board executive summaries, practical recommendations, UK/German cross-border context, clean professional visual hierarchy. Use fictional firm/matter names only for synthetic demo.
- For incomplete due diligence, disclose source coverage, as-of date, VDR wave cutoff, missing documents, uncertain facts, translation caveats and assumed jurisdiction separately. Do not mark missing items as N/A unless an authorized person approves. The checklist's US-specific requests (e.g., IRS, ERISA, SEC) may be inapplicable to a German GmbH; identify **conditional applicability**, don't silently apply US law. German/UK/EU rules require verified, current legal source references and attorney review.
- Draft sections only from properly approved reviewed findings; source consultation for citation checking is read-only and permission-filtered. Newly discovered matters must be routed to attorney review and excluded from finalized conclusions until validated.
- For client/bank reports, do not simply redact by keyword. Build a separate audience-specific authorized evidence snapshot and regenerate/sanitize eligible derivative draft; require appropriate release approval. Redact/omit restricted sources, citations, appendix details, document titles and metadata too.
- Signing freeze / closing retention and deletion decisions remain records-management controlled, not graph tool actions.

## 7. API and UI requirements

Protected FastAPI routes (adapt to existing route naming conventions; do NOT create duplicate controllers):

```
POST /api/matters/{matter_id}/ddr-runs
GET  /api/matters/{matter_id}/ddr-runs
GET  /api/ddr-runs/{run_id}
POST /api/ddr-runs/{run_id}/cancel
GET  /api/ddr-runs/{run_id}/coverage
GET  /api/ddr-runs/{run_id}/evidence
GET  /api/ddr-runs/{run_id}/draft
POST /api/ddr-runs/{run_id}/request-review
POST /api/ddr-runs/{run_id}/review-decision
GET  /api/ddr-runs/{run_id}/versions
GET  /api/ddr-runs/{run_id}/exports?format=docx|pdf
GET  /api/admin/agents
POST /api/admin/agents
PATCH /api/admin/agents/{agent_id}/draft
POST /api/admin/agents/{agent_id}/test
POST /api/admin/agents/{agent_id}/submit-legal-review
POST /api/legal-sme/agents/{agent_id}/approve
POST /api/admin/agents/{agent_id}/publish
GET  /api/admin/agent-runs/{run_id}/audit
```

The backend must derive actor identity from secure session, validate CSRF as applicable, use idempotency keys for create/approve, and check `matter + resource + action + live policy + snapshot` per operation. Human approval/release requires strict server-side role and conflict-of-interest checks and immutable audit events.

React pages/components:
- `Reports > New DDR` wizard (matter, report type, cutoff, audience, authorized evidence only, template version, cost budget)
- `DDR Run Dashboard` with agent graph progress (specialists, cost/tokens, errors, coverage), source completeness and notifications
- `Report Review Studio` (editable section text, side-by-side citations/source evidence, new issue flags, redlines/commenting, approve/return/reject)
- `DD Checklist Coverage` by A–N workstream: Requested/Received/Gap/N/A approved, attorney ownership, evidence links
- `Root Admin > Agent Registry & Tools`: technical CRUD, active models/tools, graph version, dry run, test results, history
- `Legal SME > Agent/Prompt Approval`: exact prompt/tool/legal-rules diff, approval/rejection with rationale, immutable published versions, impact assessment
- `Legal Governance Inbox`: durable review tasks, stale/changed policy alerts, escalation and acknowledgment distinct from approval

## 8. Evaluation, security, performance and acceptance tests

Implement pytest unit/integration tests; Pydantic validation; LangGraph execution tests with deterministic fake chat models; UI tests at least for the critical review gate. Test with synthetic German and English data. Include:
1. The checklist A–N categories load with stable IDs, page references, status enums, and prompt/tool mapping; US-specific items are conditional, not asserted as German legal obligations.
2. One reviewed synthetic customer contract with a confirmed CoC finding produces a precisely cited section; no document source or factual detail is invented.
3. A checklist item with no document produces a **gap**, not a fictitious risk finding or an N/A.
4. An unapproved candidate finding NEVER appears as an approved legal conclusion in final DDR; it can create an attorney-review action.
5. A source document changes version after a graph checkpoint: stale input invalidates or pauses affected branch and requires a new authorized snapshot.
6. A walled Freshfields user, unapproved Halden user, and Castlegate user cannot invoke or receive forbidden report runs, draft paragraphs, source titles, log data or exported files.
7. Pricing clean-team source appears in a restricted report but never in a standard internal/client/bank report without approved sanitization. A high-restriction source contaminates dependent output labels by inheritance.
8. Graph model failover cannot select an unapproved provider or region, and cannot use AI when `AI_RESTRICTED` policy prohibits it.
9. Injected text in a synthetic VDR PDF does not change agent policy, tool permissions or output recipient; no prompt injection-induced tool calls.
10. LangGraph parallel specialists are deterministic/restartable and idempotent, with bounded retries, budgets, max steps/iterations, cancellation and no duplicate report versions.
11. Citation verifier rejects fabricated quotes, incorrect page/version and unauthorized source ID.
12. Human approval and external audience release remain two distinct server-side decisions; agent cannot fake either via graph state.
13. Material agent prompt/tool/playbook change requires independent Legal SME approval, exact version diff, impact assessment and action-center notification; published versions immutable.
14. DOCX export is editable and contains expected headings/citations; PDF export matches approved content and is access-controlled. Do not claim Word/PDF export works if dependencies or test outputs are missing.
15. Keep auditable costs (tokens, model identifier, duration) without leaking protected text.

## 9. Build order / acceptance gates

**Phase 0 — repo audit + architecture plan:** inspect current state, checklist metadata and existing APIs; run tests; identify missing source, package/license caveats; deliver concise implementation plan, actual file list and risk register.

**Phase 1 — deterministic domain foundation:** database models/migrations, `ChecklistRegistry` A–N from source (without bulk copyrighted text), `EvidenceRef` and reviewed-finding snapshot services, tool permissions, typed models; tests.

**Phase 2 — minimal working LangGraph vertical slice:** OpenAI adapter + fake test provider, graph coordinator → 1 authorized contracts specialist → drafter → citation verifier + reviewer → human interrupt → internal report version. Execute locally on synthetic documents; demonstrate real LangGraph node transitions and Pydantic typed outputs. No external release yet.

**Phase 3 — parallel specialist expansion:** add remainder of approved workstreams, checklist coverage, dynamic routing, bounded parallelism, gaps/question register, models/tool registry, audit, retries.

**Phase 4 — UX and exports:** report review editor, tracked versions, editable DOCX, gated PDF, download authorization, agent management + SME approvals + governance inbox.

**Phase 5 — security and scope hardening:** exhaustive negative authorization/derived data tests, stale snapshot invalidation, cost/latency observation, source completeness, quality evaluation, optional provider interfaces. All external releases after attorney + audience-specific approval only.

Stop after Phase 0 to show the exact plan and first implementation batch unless the user explicitly authorizes coding; once authorized implement incrementally and show verified test results. Do not replace the existing security architecture or prior playbook governance.

## 10. Output requested from Codex on the first turn

A. Describe the existing repo state and any missing files. Confirm checklist PDF is a **Bloomberg Law M&A request checklist**, not a completed DDR sample. Name source chapters A–N.
B. Present HLD Mermaid graph and LLD: node-by-node descriptions; tool registry and permissions; typed graph state; data flow; schemas/migrations; API endpoints; UI routes; abort/retry/interrupt and checkpoints.
C. Provide file-level implementation plan and ordered issues with acceptance tests for Phase 1 and 2.
D. Call out 5 risks around agent delegation, clean-team information, derivative labels, hallucinated citations, and legal vs technical approvals.
E. Propose a short, original **Project Kestrel Fictional Due Diligence Report** outline (not an official Freshfields branded source template), including cover, summary, findings by workstream and schedules.
F. Start only after showing the plan, preserving working functionality and all previous requirements.
