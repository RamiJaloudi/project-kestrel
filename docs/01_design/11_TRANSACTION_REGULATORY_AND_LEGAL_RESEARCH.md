# 11 — Transaction-level issue spotting and legal source provenance

## Transaction structure (always check this first)
[BRIEF] UK-listed manufacturing **buyer** Halden acquires privately held German GmbH **target** Vireo. This is **not** automatically a UK or German public-target takeover, take-private or squeeze-out. Prefer private-target share acquisition questions, without assuming whether transaction is share purchase/asset deal/other until confirmed. Avoid overloading the first demo with public takeover mechanics.

## Regulatory playbook (counsel-validated question bank, not automated advice)
| Topic | Required triggering facts | Suggested question | Counsel owner |
|---|---|---|---|
| German GmbH notarization | Is share transfer / binding obligation involved? | Does GmbHG §15 or articles require notarization/consent? | German corporate |
| Merger control | Relevant turnovers, jurisdictional nexus, control | Are EU/German/UK filings possible under applicable rules/thresholds? | Competition |
| German FDI | Investor ultimate beneficial owners, sector, target activities, thresholds | Does German investment screening apply? | German regulatory |
| UK NSIA | Specified qualifying entities/assets, sector, UK nexus, trigger events | Is mandatory notification or optional call-in exposure implicated? | UK regulatory |
| UK listing rules | Specific listing category, deal classification and applicable version | Does Halden owe approvals, announcements or disclosures? | UK capital markets |
| Employment & co-determination | Employee counts, works council structures, transaction steps | Are consultation/works council obligations potentially relevant? | German labor |
| EU/UK GDPR | Controllers/processors, data subjects, establishments, cross-border transfers | Which due diligence data protection duties may apply? | Data privacy |

No rule assumes automatic filing; status fields: `not_assessed`, `facts_missing`, `possible`, `out_of_scope`, `legal_reviewed`, `completed`; retain authority, version and responsible reviewer.

## Official research starting points (NOT live-verified in this project)
- German `Gesetze im Internet` government portal: https://www.gesetze-im-internet.de/englisch_gmbhg/ (English translation may not be current; authoritative German text check required)
- German BGB: https://www.gesetze-im-internet.de/englisch_bgb/
- German Works Constitution Act: https://www.gesetze-im-internet.de/englisch_betrvg/
- EU GDPR consolidated source: https://eur-lex.europa.eu/eli/reg/2016/679
- EU merger control: https://competition-policy.ec.europa.eu/mergers/overview_en
- European Commission Horizontal Guidelines (2023): https://eur-lex.europa.eu/eli/C/2023/4752/oj
- UK NSIA: https://www.legislation.gov.uk/ukpga/2021/25/contents
- UK FCA Handbook: https://handbook.fca.org.uk/handbook/UKLR/
- German investment screening: Bundesministerium für Wirtschaft und Energie official site / relevant foreign trade acts (confirm current exact source when researching).
These are references for specialists to check applicability and present status; **not** legal determinations.

## Research provenance fields
`authority_id, title, jurisdiction, issuer, authoritative_url, consulted_at, current_as_of, language, license_or_access_basis, effective_date, supersedes, reviewer, notes, excerpt_rights`.

## Westlaw limits
User can log into Westlaw Next but cannot access Practical Law subscriber-only documents. Do NOT make Practical Law any build dependency. Do NOT export or index proprietary Westlaw text into Codex/RAG without confirming explicit permitted AI use. Original researcher-authored summaries plus citation to authorities are permissible only to the extent not violating applicable contractual/use restrictions; confirm terms.
