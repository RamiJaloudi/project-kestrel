# 01 — Complete requirements and product decisions

Each ID is independently testable. Source P = brief page, U = explicit user design decision, D = proposed design.

## 24 November 2026 deadline decision

[USER DECISION] At approximately 12:44–12:50 PM Eastern, the user approved the deadline-focused recommendation and parallel work. Hard submission cutoff is 6 PM Eastern today; the planning target is a reviewable submission by 5 PM, with time for upload/recovery. Finish and verify the Registry DataTables increment, then freeze application features. Defer secondary-register conversions and optional feature expansion. Run final regression, prepare honest assessment/demo deliverables, and prepare the Windows/Azure migration in parallel. Resource Excel scripts receive only essential wording updates; the bounded human walkthrough remains the last gate. This is a target, not a guaranteed completion time. Independent legal decisions, acceptance and the public-deployment approval/security gates remain required.

| ID | Source | Requirement | Acceptance evidence |
|---|---|---|---|
| R01 | P1-2 | Ingest 6 VDR waves, 12k docs / ~400k pages forecast, versioned, duplicate-aware | queued jobs + source manifest + version coverage |
| R02 | P1-2 | Scanned PDFs and 20% German | OCR fallback, language detection, preserve original spans |
| R03 | P2 | Risks incl CoC, assignment, exclusivity, noncompete, termination, caps, law, privacy | category-specific extracted candidate with evidence |
| R04 | P2 | Every finding grounded in exact source passage | evidence integrity test: doc version/page/quote/span verified |
| R05 | P2 | Lawyer confirm/correct/reject | review history with actor/time and rationale |
| R06 | P2 | No unreviewed finding externally released | 403 and no resulting external retrieval |
| R07 | P2 | DD sections from reviewed findings | draft generated only from approved eligible items |
| R08 | P2 | Cited Q&A | access-filtered evidence, unanswerable fallback |
| R09 | P2 | Halden only sees authorized releases + comments/uploads | client API checks both org and artifact audience |
| R10 | P2 | Castlegate selected financial/commercial only | cannot access privileged legal advice or draft internal content |
| R11 | P2 | Clean-team controls | named membership, no information in unauthorized search/AI/export |
| R12 | P2 | Ethical walls | walled firm user cannot access matter or derivatives |
| R13 | P2-3 | Traceable usage and retention | append-only events; signing snapshot; policy-based delete/retain |
| R14 | P3 | Board in five weeks and first wave next week | interim coverage disclosure; rapid approved-tool strategy |
| R15 | P3 | No new external app next week without 4–6-week review | phased rollout with external gates |
| R16 | P3 | Matter-specific jurisdiction/taxonomy legal approval | versioned playbook + legal owner acceptance |
| R17 | P4 | VDR/DMS/Walls/M365 integration interfaces | mock ports with replaceable adapters |
| R18 | P4 | Production operations, error/model/cost control | queue/retry/circuit breaker/model fallback/observability design |
| R19 | P4 | Partner note ≤1 page and panel 20–30m | markdown partner note and presentation outline |
| R20 | P1 | State assumptions and AI assistance | decision log and disclosure |
| U01 | U | Three firm/client/bank portal shells | verified host and session organization mapping |
| U02 | U | Windows-first, eventual public, real accounts, $50 goal | README and hardening gates |
| U03 | U | Root Admin playbook management | create/edit/duplicate/test/submit/archive audited |
| U04 | U | Legal SME independent approval | no self-approval and immutable publish |
| U05 | U | Version comparison / impact / inbox | exact rule diff; counts by affected docs/approved/released findings |
| U06 | U | Material change triggers scoped authorization | SME approval with rationale and immutable impact hash |
| U07 | U | Reanalysis creates candidates, not overwritten conclusions | historical findings intact, new attorney review |
| U08 | U | Notifications durable, states/action center | unread/read/acknowledged + pending action/escalation/resolution |
| U09 | U | No paid iManage/M365/Intapp/Practical Law in prototype | mocked adapters, licensed citation catalog only |
| D01 | D | Dual-control clean-team declassification | attorney validation + separate authorized antitrust approval where policy requires |
| D02 | D | Optional transaction regulatory screening | counsel issue-spotting, unknown facts, no mandatory conclusion |
| D03 | D | Incident containment and correction tracking | quarantine, revoke, audit, attorney escalation |

## Important distinctions
- **Matter access** is not the same as login role; **clean team** is a scoped attribute not global role.
- **Lawyer-reviewed finding** is not necessarily **client/bank-releasable**.
- **Approved playbook version** is not **SME-approved reanalysis**; separate decisions.
- **Notification viewed** is not **task approved**.
- **Document language** is not necessarily **governing law**.
- **RAG answer** is not **complete review**; batch analysis must track coverage.
- Candidate private demo vs real firm production are different deployments/entitlements.


### 24 November 2026 — Remaining gates and Azure decisions

[USER DECISION] Complete remaining gates before migration. User authorizes parallel coding agents within each gate. User confirms composer GPT-6.1 Sol — Ultra; runtime metadata did not independently expose the active root model setting. Deadline is 24 November, 6 PM Eastern; completion remains at risk and is not promised.

[USER DECISION] MFN means Most-Favored-Nation contractual clauses. Independent Legal SME publication and material-change impact approval remain required.

[USER DECISION] Active Azure subscription and DNS control confirmed. Windows Server with local PostgreSQL; approximately $100/month target. Main entry point: portal.ramijaloudi.com. Approved separate portal hostnames: firm.portal.ramijaloudi.com, halden.portal.ramijaloudi.com, castlegate.portal.ramijaloudi.com, admin.portal.ramijaloudi.com. No public resources, DNS records, transfers or launch have been executed by these decisions. Public launch remains a separate acceptance/security/user-approval gate.

### 24 November 2026 — DataTables priority

[USER DECISION] Prioritize DataTables now. Review the Excel workflow scripts together as the last gate. This changes implementation order; it does not supply Legal SME/antitrust approval, enable paid AI or approve Azure/public launch. The bounded rollout starts with Tasks & assignments, then findings/registers, admin/audit and secondary lists. See docs/88 and docs/89 for current scope and evidence.
