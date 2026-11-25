# 44 — Person, client–matter and document ethical-wall checker

[USER DECISION] Add person-only and person-plus-documents checks to **Administration / SQL Registry → Clients, matters & ethical walls**, using the person's role and relationship to the client and/or client–matter combination, together with document attributes.

[IMPLEMENTED, LOCAL DEMO] Open [Administration → Wall checker](https://admin.localhost:8443/portal?view=Wall%20checker), or use its panel on Registry. [Swagger](https://admin.localhost:8443/docs/wall-checker) documents the typed request and response contracts. This component uses the existing shared API; it adds no duplicate service or separate clean-team portal.

## What the combined decision means

ABAC combines a subject, resource, action and applicable context, consistent with [NIST SP 800-162](https://csrc.nist.gov/pubs/sp/800/162/upd2/final). Documents carry policy attributes and inherited restrictions; they do not need an independent conflicting-person identity. The implemented precheck combines:

1. A known, active SQL person and their actual organization/application roles.
2. Client-level restrictions, including approved relationship-based matches.
3. Matter-specific restrictions, including existing registry walls and published legacy wall policies.
4. Validated matter status and active need-to-know assignment.
5. The requested document version, its type/state/classification, audience/release, inherited source restrictions, clean-team membership and named grants, where applicable.
6. Requested action, signing/closing state and the existing document policy engine's other gates.

**Deny overrides.** A client restriction covers all current and future matters for that client. A matter restriction covers only its client–matter pair. A matter assignment, relationship-partner designation, role or document flag cannot override a client restriction. Root cannot grant source access by running a simulation for another person.

Client-only checks deliberately return no positive matter/document access decision. “No matching recorded restriction” is not a legal conflicts-search clearance. The checker uses registered local data; it does not discover undisclosed conflicts or query Intapp. Processing-environment restrictions, SME authorization, budget checks, legal review and audience approvals remain separate execution gates. A positive document-policy precheck is not a job or publication authorization.

[DESIGN] This follows the centralized enforcement approach described in [Intapp's public Walls materials](https://www.intapp.com/walls/). It is not a claim to reproduce Intapp's proprietary internals, licensed integrations or full feature parity.

## Using it

1. Select a client and, for matter/document checks, the exact client–matter combination. Leading zeros remain strings; `012345-789012` is not reduced to two integers.
2. Enter a login/email. Roles and relationships are returned from SQL; the browser cannot assert them.
3. Choose **Person** for the client/matter precheck, or **Person + documents** and an action. Select policy references or enter source/policy version IDs. Each document must belong to the selected pair.
4. Review separate client and matter restrictions, assignment, SQL roles and per-document outcomes. A batch passes only if all selected references pass. Restricted document names/attributes stay hidden unless the operator's own document rights allow them. Root receives opaque policy references and redacted document-denial details, not contents.
5. Download the decision receipt. Recent history shows the latest 20 retained checks, their operator, subject, action, time and outcome. Historical receipts are explicitly not current access grants; run a fresh check before acting.

Root administrators and Conflicts approvers require active, unwalled management scope. Client-wide operations require clearance for every registered matter of that client; otherwise select a permitted pair. Ordinary lawyers and external accounts cannot inspect other people's authorization through this administrative component. Scoped OAuth diagnostics require `EthicalWalls.Check`; governance changes require authenticated human sessions and CSRF protection.

## Relationships, rules and retirement

The management panel supports:

- **Relationship records:** a named person connected to the client or one matter. Neutral relationships do not create matter assignment, content roles or clean-team membership. `restricted_interest` means a Conflicts-confirmed restricted interest and itself denies the relevant scope. A former/adverse relationship is not automatically treated as a legal conflict merely from a job title.
- **Deny restrictions:** match a named person, application role and/or active recorded relationship. All supplied selectors must match. A matter-level rule may use a client relationship; a matter-only relationship is never lifted into an entire-client match.
- **Independent approval:** proposals remain inactive until an unaffected, separately scoped Conflicts approver approves the immutable record. Root cannot self-approve. Named self-access changes are prohibited.
- **Retirement:** propose a separate retirement record and obtain independent Conflicts approval. The old rule, author, approval and rationale remain. Retiring one rule never overrides another applicable restriction.
- **Validity:** controls are indefinite by default. If a limited term is selected, its exact expiry is part of the approved proposal. Expiry/retirement removes applicability, not retained evidence. No records are automatically deleted.

Use an unconditional named-person deny for a confirmed personal conflict. Conditional role/relationship rules are access-policy conditions; changing a person's role must not accidentally clear a confirmed personal restriction.

## SQL sources and enforcement

Additive migration `0019` supplies immutable `wall_controls`, `wall_control_decisions` and `wall_check_records`, plus:

| SQL view | Purpose |
|---|---|
| `vw_person_wall_entries` | Independently approved controls excluding approved retirements; validity is evaluated at check time |
| `vw_person_relationships` | Relationship projection |
| `vw_person_wall_rules` | Deny-rule projection |
| `vw_wall_document_references` | Opaque policy/source references; API applies operator scope and metadata redaction |

Existing client–matter and document-policy views remain in use. Views are projections, not authorization boundaries. `repositories/identity.py` incorporates client and relationship-derived restrictions into the principal used by existing sessions/OAuth, source readers/downloads, findings/reports, Q&A and workers. The checker calls the same document evaluator; it does not implement a permissive parallel engine. Missing policy views make readiness fail instead of being treated as an empty restriction list.

Receipts retain the authenticated operator separately from the checked subject, roles/relationships at evaluation, per-reference outcomes, timestamp and a fingerprint of the decision/referenced policy snapshots. Document passages and hidden attributes are not included. Records have immutable database guards; ordinary technical logs contain no input bodies. A fingerprint is not a signed access token, WORM assurance or permission to replay an old authorization.

## Isolated synthetic examples

When the existing demo-seeding flag is enabled, Start initializes **client `054321`**, **Alpha `100001`** and **Beta `100002`** once. The marker `.runtime/wall-checker-lab.json` prevents reapplying decisions or restoring retired controls/assignments. An existing reserved client number causes a skip rather than overwriting data.

| Person | Alpha | Beta | Explanation |
|---|---|---|---|
| `lawyer03@freshfields.example` | Denied | Denied | Client-level restriction |
| `lawyer02@freshfields.example` | Person precheck passes | Denied | Matter-only restriction on Beta |
| `lawyer01@freshfields.example` | Person precheck passes | Person precheck passes | Neutral relationship; existing roles/assignments still required |

Alpha contains two independent synthetic source versions. For lawyer01, an `analyze` precheck permits the ordinary source and denies the source marked **No AI processing**. This checks the document-policy layer only; no provider call, analysis job or client publication is performed. No main-matter permissions, existing releases or Wave 2 imports are changed. Fixture approvals use different fictional role profiles and are not real professional clearance.

## Verification and rollback

Boundary tests cover client inheritance/future matters, sibling-matter isolation, role-plus-relationship conjunction, relationship scope, no implicit grants, legacy walls, exact source-policy enforcement, quarantine, Root content denial, self-approval, SQL immutability, OAuth scopes, historical receipts, asserted-role/attribute rejection and missing-view failure. The frontend must build before serving the new UI; PostgreSQL tests use isolated schemas.

An encrypted, verified database backup was retained before migration. Normal Start upgrades schema; it never performs a downgrade. Empty test schemas can roll back, but any retained wall governance/check records block downgrade rather than discarding evidence. Operational rollback should use a separately reviewed backup/restore procedure; it must not silently delete audit records or run an older application against a partially downgraded schema.


## Observed live results

The normal HTTPS demo accounts passed client inheritance, sibling-matter isolation, mixed document ABAC, historical receipt and unchanged logged-in-operator checks. Root remained denied by the original document reader; the old client–matter validation API reflected the new restrictions. The main-matter PDF/Word/Excel and audience-isolation walkthrough passed, with Wave 2 still unimported. The full regression run passed 169 tests with one PostgreSQL-only skip; subsequent focused policy checks covered the separate assignment/validation display and PostgreSQL boundaries. Browser pixel/click verification remains unverified because desktop automation was unavailable.

Migration `0020` preserves the same three-value wall-control whitelist using scalar comparisons on PostgreSQL. The initial backup comparison found no row differences: PostgreSQL had reparsed an equivalent varchar-array `IN` constraint into element casts. The scalar form avoids that serialization-only mismatch without weakening validation. The subsequent encrypted backup/isolated restore passed all 49 tables (2,747 rows at that snapshot), plus schema definitions, indexes, functions and triggers. Failed backup attempts are retained; full schema-difference evidence, if captured, is protected with DPAPI instead of printed in ordinary diagnostics.
