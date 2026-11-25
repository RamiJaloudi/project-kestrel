# 15 — Ordered implementation backlog (start here)

**Each sprint is independently testable; complete P0 gates before public access.** Keep a narrow demonstrable vertical slice before feature breadth. List scope/changed files/tests before coding.

| Sprint | Deliverables | Exit tests |
|---|---|---|
| S0 — Verify starter | Parse original assessment and confirm docs, run local test suite, identify gaps | imports pass, health local, no protected demo endpoints accessible |
| S1 — Security foundation | PostgreSQL/Alembic; real demo accounts/password hashing/sessions; three hostname-aware shells; centralized deny-first policy + org/matter/wall/CT | login/logout/session tests and all negative access matrix |
| S2 — Versioned document flow | mock VDR manifest, file ingestion, original-language extraction, classification, evidence span and checksum, viewer | version/quote correctness and restricted download tests |
| S3 — Playbooks + legal workflow | CRUD draft, version, testing, SME legal approval, immutable publish; risk extraction adapter; attorney review states | no self-approval, immutability, citation/review release denial |
| S4 — Release and collaboration | Halden/Castlegate audience artifacts, CT sanitization/antitrust gate, comments, Q&A/report stub, audit | no privilege/CT leaks, no external unreviewed finding |
| S5 — Action Center | exact diff, impact snapshot affected doc/approved/released counts, SME task inbox, rationale approvals/rejections, idempotent rerun, reconciliation | all P0 governance tests in `docs/14` |
| S6 — Expanded AI and research | hybrid RAG, multilingual contract processing, model adapters, citations/evals, draft reports, regulatory issue register | no answer w/o evidence, verified expert case tests and access checks |
| S7 — Presentation/public gate | integration docs, change-control, security review, cost/teardown, slides/partner note; optional authorized public demo | full test matrix + explicit launch permission |

## Definition of done
Code, tests, migrations, README with Windows commands, DTO/API contracts, clean policy tests, audit records, documented limitations. No fabricated metrics. Deploying public demo is **not** an automatic step.

## Submission deadline reminder
User-reported deadline **November 24, 2026**. The original brief itself says one week from receipt. Favor focused assessment (HLD/LLD, conflicts, safe first-wave plan, partner note) over excessive prototype scope.
