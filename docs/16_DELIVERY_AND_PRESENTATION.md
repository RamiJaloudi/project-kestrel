# 16 — Assessment submission package and interview narrative

## Source brief rules
Plan 4–6h for design; prototype optional; one-page plain-language M&A partner note; panel ~75m, 20–30m presentation and ~40m Q&A. AI assistance welcome but disclose. Deadline user says Nov 24, 2026; verify with recruiter if changed.

## Submission deliverables (proposed)
- 10–14 slide presentation PDF/PPTX: business problem and timeline, user map, conflict decision table, day-one solution, target HLD/LLD, AI/risk taxonomy, evidence/citations, IAM/clean-team/walls, AI Q&A/batch distinction, audit/retention, phased rollout, quantitative acceptance, cost/risk/decision asks.
- `PARTNER_NOTE.md` below reduced to one page and language understandable without software knowledge.
- Architecture diagram (Mermaid exported to image if possible), one technical appendix with policy matrix, API schema and evidence/citation example.
- Optional synthetic demo with recorded test results, explicit list of what is mocked and not implemented. Do not invite panel to a public demo without permission.
- Disclosure: which steps used Codex/AI, what was manually verified and where legal authorities were checked.

## Partner note (ONE PAGE max; adapt before submission)
**Subject: Project Kestrel — safe early value from AI-assisted due diligence**

The first seller data-room wave arrives next week. We will start by using the firm's currently approved document-review and collaboration tools, concentrating on material customer contracts and potential change-of-control exposure. The team will agree a short risk checklist with the knowledge lawyer and German legal colleagues, then record lawyer-confirmed findings with precise document citations. That lets us reduce tracker administration and give Halden an interim, clearly caveated board risk picture in five weeks, even though additional VDR materials arrive later.

We will **not** launch a new client/bank-login application next week: IT security has said approval may take four to six weeks. Nor will AI findings be sent directly to Castlegate: Freshfields attorneys review them first and release only the appropriate commercial subset. Competitive customer pricing stays restricted to named clean-team members, and ethical walls exclude prohibited lawyers. In the longer-term solution, AI can help draft reports from reviewed findings, provide permission-trimmed cited questions and answers, and maintain an auditable record of who reviewed and released information.

Please decide: (1) initial contract/risk priorities and who approves the taxonomy; (2) whether a scoped bank-facing red-flag report is adequate at first; (3) named clean-team membership and release approvers; (4) whether the interim board report should focus on a customer-contract consent register and material risk summary; (5) who authorizes retention/deletion decisions. We will track gaps transparently rather than claim due diligence is complete before the remaining materials arrive over the six-week intake period.

## Interview script anchors
- "I don't confuse a VDR with the client-facing application: the seller VDR remains the source; Kestrel is a controlled review and release layer."
- "For the first wave I reuse authorized tools, not promise a brand-new externally reviewed app."
- "The AI can propose findings, but the lawyer confirms the source and the release approver controls the audience; clean-team releases have a separate policy gate."
- "RAG answers questions over authorized sources; batch extraction tracks coverage, so no hidden assumption that search examined all contracts."
- "Root admin is not legal authority; immutable playbooks, separate SME approval and action-center controlled reruns preserve reproducibility."

## Demo implementation vs target production distinction
Three domain shells are **the candidate demo**, not a claim that Freshfields would adopt those hostnames. Production would require firm-approved identity, information barrier integration and security assessment. Candidate optional prototype is synthetic only.
