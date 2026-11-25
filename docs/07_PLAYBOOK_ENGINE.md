# 07 — Legal risk playbook design and governance

## Purpose
A playbook is a versioned structured rule set, not just an LLM system prompt. Legal SME defines risk taxonomy by document type, governing law, jurisdiction, language, explicit contract triggers, exceptions, evidence required, severity/escalation and relevant verified authority pointers. Original text citations are mandatory.

## Core structure
`id`, `name`, `owner`, `status`, `version`, `document_types[]`, `languages[]`, `governing_laws[]`, `matter_constraints[]`, `risk_category`, `rule_definitions[{rule_id, description, triggers, negations, evidence_requirements, notes}]`, `legal_authorities[{id,title,issuing_body,url,jurisdiction,verified_at,version,license_provenance}]`, `output_schema`, `evaluation_cases`, `approval_policy`, `change_classification`, `published_at`, `content_sha256`.

## Seed playbooks (fixtures in `data/playbooks/`)
- `PB-COC-DE-001` German/German-or-English contract change-of-control & deemed assignment (illustrative). Must separate **language** and **governing law**.
- `PB-ASG-001` assignment and consent.
- `PB-DP-EU-001` EU data protection issue spotting.
- `PB-LIABILITY-001` liability caps/exclusions.
- `PB-CLEAN-001` clean-team release **governance**; not a legal risk extraction model and not a license to publish.
- `PB-REG-001` transaction regulatory issue spotting, reviewed by UK/German specialists with open-facts questionnaire.

## Two separate approvals
1. **Publish legal playbook:** draft author submits; independent assigned Legal SME (not the same user) reviews exact diff, scope, test evidence, jurisdiction/law, source references and approves. Root admin may publish *only the approved exact version* through locked transaction and signed audit.
2. **Authorize reanalysis of historical material:** when a material version is published, impact engine computes fixed candidate snapshot. Assigned independent Legal SME gets Action Center task. Cannot run until scoped approval with rationale (or reject with rationale); separate clean-team approval if scope includes restricted data. Neither approval automatically republishes findings.

## Material-change semantics
- `editorial`: spelling/description only, no change to detection semantics. No reanalysis unless manually required.
- `material_detection`: new/removed/modified trigger/exclusion/schema that could alter extracted findings.
- `material_legal`: legal interpretation, jurisdiction, severity/escalation, authority update; legal SME impact assessment.
- `critical_correction`: known error with potentially wrong *released* conclusions: urgent legal task independent of slow job; possible containment/correction per policy.
A material playbook publication **must run impact analysis**, but only post-SME authorization starts reprocessing. Old reviewed items retain hashes and history; coverage/comparison explicitly visible.

## Change-of-control v1.2 -> v1.3 illustration
- Rule `COC-03`: changed from "direct change in ownership" to "direct OR indirect control changes and ultimate ownership where contract so provides".
- Rule `COC-09`: added `deemed assignment` language with exceptions and consent requirements.
- The sample impact output may include 1,240 document versions, 186 approved findings, 32 released, 11 restricted; numbers illustrative and generated from fixture, **not empirical result**.

## Evaluation
Each playbook must ship synthetic positive, negative, borderline, German original-language, unanswerable/contradictory, and prompt-injection cases. Measure detection precision/recall against expert-labeled subset; citation integrity separately. A rule must not be published solely on synthetic cases if real production claim is made. Legal SMEs sign off before deployment to real matter data.

## API invariants
- Archive/supersede retains all published versions, findings, usage logs and approvals.
- New publish cannot retroactively change results; compare displays exact field-level diff (semantic classification is reviewed, not solely model-generated).
- Source authority may be available only by URL/metadata if Westlaw copyrighted. No unlicensed primary full-text index.
