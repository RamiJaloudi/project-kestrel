# 10 — Clean team, information barriers, audit, incidents and retention

## Clean-team design [DESIGN subject to governing agreement]
- A formal clean-team roster, scope, permissions and expiration are defined with conflicts/antitrust counsel. Clean-team classification applies to originals, chunks, AI findings, summaries, query answers, logs, exports and copies; a root admin role does not override restrictions.
- Default deny to both Halden business users and Castlegate. Named eligible Halden **outside the business** and Freshfields clean-team members get only allowed scope.
- Standard path: candidate risk -> attorney approval -> proposed sanitized/aggregate artifact -> independent authorized antitrust/clean-team counsel approval where required -> permitted audience release -> audit/possible revocation. **A reviewed finding is not publishable by itself.**
- Aggregation alone may not de-risk inference of individual customer prices; counsel must review anonymity/reidentification context. The sample policy must support rejection.

## Privileged material
Halden-only legal advice must never appear in bank summary, citations, search index visibility or exports. Permission trimming occurs before LLM and on output. Every delivered artifact records source IDs, label, audience, approvers, timestamps and revision.

## Audit
Append-only events: login/access, denied read (safe metadata), VDR sync, OCR/AI processing, findings review, playbook edits/diff/test/SME approval/publication, impact snapshots, notification/tasks, rerun approval/denial, job status, release/declassification/export/revocation, sign/close freeze, retention holds, deletion/disposal actions. Separate authorized audit views from confidential content. Protect audit logs against tampering; production model tamper-evident storage/WORM and access separation.

## Confidential-price leak incident
- Contain release and access immediately; quarantine derived summaries/AI caches; rotate affected links; record affected recipient/downloads.
- Preserve scoped audit and evidence; assign incident lead and antitrust/legal counsel; assess whether any external/authority notices required. Do not claim access revocation can recall previously downloaded copies.
- Correct legal advice/client communication under authorized lawyer control; approvals and remediation tested before re-enable.

## Signing/closing retention
Signing: create immutable frozen *record* snapshot, with ongoing operational workflow separated if deal continues. Closing: decide which Halden-owned collaboration copies may be deleted, and which Freshfields records must be retained under policy/holds. Document deletion requests, decisions, holds, deadlines and erasure events; no hardcoded blanket deletion. If deal collapses, enforce separately approved clean-team agreement return/destruction/retention rules.
