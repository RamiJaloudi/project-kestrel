# 17 — Assumptions, open decisions, risks and owners

| Decision to confirm | Current assumption | Who owns it | If false |
|---|---|---|---|
| VDR export/API allowed | periodic authorized batch exports | Seller VDR admin + partner | manually selected files; no unauthorized scraping |
| Initial legal taxonomy | CoC + assignment + software licenses high priority | Knowledge Lawyer + German counsel | risk model delayed; do not run unapproved playbook |
| Clean team agreement and roster | formal named scope + dual-control release if needed | Antitrust/competition + conflicts | block CT release and potentially CT processing |
| Client/bank security approval | new external platform takes 4–6 weeks | Security/IT + business owner | rely entirely on approved M365/secure sharing |
| Halden board expectations | interim CoC register/risks with coverage gaps | GC + M&A partner | change prioritization/report format |
| Acquisition legal structure | private German GmbH share deal (not guaranteed) | Transaction counsel | different notarization/review requirements |
| Regulatory thresholds/jurisdiction | unknown until matter facts supplied | German/UK/EU specialists | cannot conclude filings required |
| AI model/data residency | only firm-approved EU enterprise models in target | Security/privacy | disable model or use manual workflow |
| Cost ceiling $50 | prototype hosting target, not production budget | Candidate | use localhost/no LLM, request permission before paid deploy |
| Domain ownership and approval | proposed demo-prefixed subdomains | Candidate/recruiter | use local hosts only |
| Post-closing deletion | collaboration items may differ from firm records | Records/privacy/client | never auto-delete legal holds/firm records |
| Legal research usage | user has Westlaw Next, not Practical Law | Candidate/legal licensing | don't ingest restricted resources |

## Scope risks
- Model citation hallucinations: verify spans against source and let lawyers correct.
- Search vs full coverage: batch screening and explicit unprocessed counts.
- Permissions lost during embedding/index creation: enforce label propagation and deny before retrieval.
- Model-provider outages: queue retry, manual alternative; no unsafe fallback region/provider.
- Public candidate demo confusion: disclaimers, fake companies, synthetic data and gated launch.
- Playbook version drift: immutable snapshot and targeted rerun approvals.
- Stale SME task: reject with 409 and recompute impact.
