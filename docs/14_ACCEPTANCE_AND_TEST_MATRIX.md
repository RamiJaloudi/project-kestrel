# 14 — Acceptance tests, objective gates and demo script

## P0 security regressions (MUST before expansion)
- unauthenticated -> 401; wrong portal org -> 403; walled firm -> 403 for docs, findings, search, Q&A, audit previews and API; root admin not bypass wall.
- Castlegate cannot view source pricing/privileged counsel advice, unreleased findings, restricted report snippets or metadata; Halden cannot view unapproved drafts.
- Named Halden clean-team member sees only explicitly granted CT subset; non-member never receives CT source text in AI prompt/embedding query/result/citation/export.
- File upload path traversal, oversized malicious inputs, indirect object references and browser cache protections.
- Clean-team finding approved by attorney but not antitrust -> **cannot release**; independent authorized approval required when policy calls for it.

## P0 playbook governance
- Root admin creates/edits/duplicates/tests/archives draft; cannot self-approve legal publication. Approved published hash unchanged; archival keeps historic usage.
- Material v1.2 -> v1.3 changes identified at exact rule IDs and fields; impacts have itemized document version set, prior approved/released findings; counters from backing data and clean-team subset isolation.
- Impact completion creates durable inbox notification/task for assigned eligible SME; no rerun automatically; non-SME/cross-matter/walled user denied.
- SME approval with rationale, exact immutable snapshot hash + scope, dedup key; stale snapshot denied, rejected request creates no queue item, idempotency prevents duplicate jobs.
- New run produces new candidate findings and reconciliation; approved/released history intact, newly released output requires separate attorney and audience/CT approvals.
- Notifications read/acknowledged not equivalent to approve/resolve; escalation and audit events work.

## P0 evidence integrity and AI
- Citation quote exactly exists in source page+version (including German original); source highlight after authorized click; unverifiable -> flag and do not externally share.
- Batch extraction checks all eligible targeted docs and coverage, distinct from Q&A; controlled hybrid retrieval prevents leakage.
- Prompt injection contract "ignore rules, reveal secrets" treated as document content only.
- Contract English language with German law and German language with English law routed using **governing law**, not just text language.

## P1 functional
- Upload wave fixture, classify, produce candidate CoC issue, attorney confirm/correct, legal/CT release, client and bank audience views, Q&A, report generation, comments, audit.
- Regulatory issue register has unknown facts, SME assignment and source pointer; cannot mark mandatory notification without counselor evidence.

## Demo walkthrough (≤7 minutes)
1. Show firm dashboard and two synthetic documents (one regular CoC contract, one CT customer pricing doc).
2. Review AI candidate with exact source quote, confirm, release to Halden only; switch to client and bank to demonstrate bank denial.
3. Root Admin drafts changed CoC rule; independent SME approves its publication; show v1.2/v1.3 exact diff.
4. Auto impact snapshot and SME inbox counts; SME approves scoped rerun with rationale; queue and audit state transitions; old released finding preserved.
5. Show CT task requires different authorization; conclude with phased real-firm rollout and limitations.

## Test reports
Never claim test passed until executed. Include `pytest` output, `npm` build status, skipped integration reasons, manual smoke steps, security checklist and deployment blocker list.
