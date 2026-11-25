# 00 — Exact case scope and source mapping

## [BRIEF] Official assessment facts (5-page original in `source/`)
- Buyer: **Halden Industries plc**, UK-listed manufacturer. Target: **Vireo Systems GmbH**, privately held German industrial software firm. Sellers: founders and PE; financial adviser **Castlegate Partners**; fictional Project Kestrel.
- Seller-hosted third-party VDR. Approximately **12,000 documents / 400,000 pages** by end of diligence. Documents delivered in waves over **six weeks**; many scans; **~20% German**.
- Signing in ten weeks, first wave next week, Halden board in five weeks. This does **NOT** imply the German target is publicly traded; exclude default public-takeover and squeeze-out workflows.
- Current manual VDR review, Excel trackers, email spreadsheets/questions, manual report drafting and seller Q&A.
- AI assists document risk spotting: change of control, assignment, exclusivity, non-compete, termination, caps, governing law, data protection, with **exact source passage**. Lawyers confirm/correct/reject; **nothing unreviewed reaches client**.
- Draft legal DD reports from reviewed findings. Cited document Q&A. Halden sees explicitly released results and can ask/comment/upload. Castlegate sees selected commercial/financial disclosures but **not Halden-only privileged legal advice**.
- Clean team: Halden and Vireo compete. Competitively sensitive data (e.g. customer pricing) restricted to certain **named** Freshfields and Halden personnel outside the business. Some Freshfields lawyers blocked by ethical walls. Audit accesses and releases. Freeze snapshot at signing; address Halden post-closing deletion requests and Freshfields retention obligations.
- Partner wants immediate bank access to red flags, BUT attorney review required; knowledge lawyer wants localized taxonomy first; senior associate wants precise citations/easy correction; IT says new externally logged-in client/bank portal **4–6-week** security review. Existing M365 guest access approved, plus internal Copilot/AI toolkit are firm-only.
- Firm technology assumptions FOR TARGET (NOT AVAILABLE TO USER'S DEMO): Azure/M365/Entra, iManage, Intapp Walls, enterprise-approved EU AI (Azure OpenAI/Google Vertex incl Gemini/Claude); 25 firm, 10 client, 6 bank users.
- Deliverables: assumptions, priorities/conflicts, day-one usable approach, HLD/LLD, AI citation/quality/cost, security/integrations, operations/monitoring/scaling, audit/deletion, rollout, ONE-PAGE plain-language partner note, 20–30 min panel talk with ~40 min questions. **Prototype optional; 4–6h focused design suggested; AI-tool usage must be disclosed.**

## [USER DECISION] Candidate implementation
Windows-first local demo, eventual isolated authenticated public demo if permitted, $50/month goal; three organization shells, no clean-team portal, real accounts, broad functional scope; no personal iManage/M365/Intapp; fictional mock adapters. Playbook admin/SME separation, impact + inbox + approval gated reruns. Westlaw Next access but Practical Law paywall.

## [DESIGN] Suggested extra scope (NOT stated by brief)
Separate antitrust counsel release approval, formal clean-team agreement metadata, workflow for incident containment, material rule version changes, regulatory issue register (German GmbH formalities, German/EU merger-control/FDI, works councils, conditional UK NSIA/UK listing). These are proposed architecture features and should not dominate take-home MVP.

## [OPEN] Decisions needed from actual firm / partner
VDR API/export rights, risk taxonomy owners and thresholds, formal information barrier/release agreement, whether bank gets sanitized results and when, approved client guest collaboration for this matter, clean-team nominative roster, report format, retention periods and legal holds, which model/AI services may see data, data residency, budget, production identity model, deal structure and jurisdiction/threshold facts.
