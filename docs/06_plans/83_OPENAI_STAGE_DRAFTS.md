# 83 Reviewable OpenAI stage drafts

Three proposed profile definitions are in `delivery/agent_profile_drafts/`: contracts, drafter and quality. They pass the strict current server schema. These files are **unapproved drafts**. Root has now saved and statically checked their exact versions in the local synthetic registry and submitted them for independent SME review. They have not been legally/semantically approved, published or used for a model call. See `delivery/agent_profile_drafts/submitted_review_receipt.json` for their exact IDs and hashes.

The currently implemented paid DDR graph requires exactly those three independently published stage profiles. The model is pinned to `gpt-5.4-mini-2026-03-17`; the whole-run bounds remain three model calls, concurrency two, 12,000 total tokens, 1,200 maximum output tokens per node and $2 maximum per run, within the shared $10 monthly allowance. The reservation is shared across the run, not $2 per stage. A lower profile bound tightens the run. Uncertain completion holds its reservation and requires reconciliation rather than automatic resending.

In [Administration → Agent Registry](https://admin.localhost:8443/portal?view=Agent%20Registry), an assigned Root Admin can prepare each new draft using the file's name and `definition` fields. Select the intended matter, retain the exact version, run static manifest checks and submit it. A different assigned Legal SME must inspect the exact instructions/tools/bounds and approve or reject with a rationale; Root Admin can then publish the approved version. Static checks validate structure and supported tools, not legal quality. Nothing in these draft files grants authority or replaces that workflow.

Keep the OpenAI key in the masked [Admin provider settings](https://admin.localhost:8443/portal?view=AI%20provider). The browser never receives a saved key. Actual live acceptance also requires an enabled private provider, current independently published legal playbook, reviewed findings, source processing permission, available budget and these published profile IDs. No paid call or independent approval was performed when preparing this document.

The offline graph remains available without a provider key. Other registry role names describe configuration kinds; publishing one does not implement an additional specialist. See [the gate acceptance audit](../05_validation/80_GATE_ACCEPTANCE_STATUS.md) for the remaining execution scope.


## Local review checkpoint

The primary synthetic matter has four currently permitted reviewed findings and two published legal playbooks. A read-only authenticated readiness check reports live provider enabled; the Admin UI also shows a saved masked key and enabled setting. This is not a test of provider validity or legal quality. All three new stage profiles are **submitted**, with zero approvals/publications/provider calls performed by this preparation. Sign in through Administration using a different assigned Legal SME account to review each complete definition and its exact hash, then approve or reject with a rationale. Root Admin publication follows a genuine independent approval.
