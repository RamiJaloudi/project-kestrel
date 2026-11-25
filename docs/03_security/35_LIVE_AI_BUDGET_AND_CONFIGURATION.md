# Personal synthetic OpenAI adapter

[USER DECISION] OpenAI for the personal synthetic demo, with USD 2 per run and USD 10 per calendar month. This is the application's limit, not an OpenAI account-wide billing limit. Live synthetic checks have now been executed; see `docs/02_workflows/41_AI_REVIEW_OCR_AND_PROVIDER_SETUP.md` for results and retained failed-call reservations.

[IMPLEMENTED] The optional adapter uses the pinned `gpt-5.4-mini-2026-03-17` snapshot, Responses API, strict JSON output, `store:false`, no tools and no redirects or proxy inheritance. Credentials remain server-side. Every returned quote must exactly occur in an authorized immutable source unit; rule identifiers and evidence offsets are validated before candidates are stored. Model output cannot change permissions, approve findings or release content.

The model and standard token prices were verified against [OpenAI model documentation](https://developers.openai.com/api/docs/models/gpt-5.4-mini). Requests use the [Responses API](https://developers.openai.com/api/reference/resources/responses/methods/create) and [Structured Outputs](https://developers.openai.com/api/docs/guides/structured-outputs). `store:false` is a response-storage choice, not a claim of zero retention or enterprise production clearance.

## Configuration

1. Use Administration → AI provider to save and enable the masked key; the server protects it with Windows CurrentUser DPAPI. The older private `.env` fallback (`KESTREL_OPENAI_ENABLED` / `KESTREL_OPENAI_API_KEY`) remains available only when no protected settings file exists. Do not put the key in the chat, a fixture, browser code or a shared credentials CSV. Keep `.env` excluded from version control. Azure secrets management remains a later deployment task.
2. Protected provider-setting changes apply without restart. In Documents, a Legal SME can see whether the provider is configured and the current estimated spend/reservations. The API exposes only a boolean for key presence.
3. The source must be human-confirmed, text-ready, assigned, unwalled, named-clean-team-authorized if applicable, and free of an AI restriction. A published processing policy must explicitly permit the operation.
4. The first-wave processing fixture intentionally blocks cloud processing. Adding a permissive policy does not defeat a restrictive published policy. Therefore enabling a key alone does **not** enable live processing for this seeded matter. A controlled policy replacement/retirement workflow remains required before enabling cloud processing there; do not edit database policy records as a workaround.
5. A scoped Legal SME selects the published playbook and live engine. Only a first analysis of that immutable source version can be queued. Use a fresh authorized source version for a new run; historical reruns remain blocked pending impact approval implementation.

## Spending behavior

Before any provider request, the worker atomically reserves the full USD 2 allowance against the USD 10 monthly ledger. Parallel requests cannot reserve beyond the available allowance. Calendar months use America/New_York. Reservations are unique per job. Usage settles at conservative uncached input/output rates, rounded up to cents; unused reserved funds become available. This is an estimate using the pinned model's documented rates, not an invoice reconciliation service.

Context is bounded to 100 KB and output to 2,000 tokens. Provider timeout is 30 seconds. No automatic provider retries occur. Unknown usage, timeouts and uncertain failures retain the reservation for operator reconciliation; automatic deletion or silent release of that reservation would risk overspending. A settled failed evidence check can still incur cost, since the provider request occurred.

The default offline literal engine makes no network calls. It demonstrates original-language evidence and role-separated review; it does not establish legal accuracy or exhaustive clause coverage. Environment policies, document restrictions, spending limits, independent legal review and audience release remain separate controls.
