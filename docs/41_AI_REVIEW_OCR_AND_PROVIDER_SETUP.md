# 41 — AI review, original evidence and OCR

[IMPLEMENTED, LOCAL DEMO, 21 NOV 2026] The provider is configured through **Administration → AI provider**. Paste a key into the masked password field, choose whether to enable processing and save. The server protects it with Windows CurrentUser DPAPI; the API never returns it, and saving clears the input. Existing protected settings take precedence over the older `.env` fallback. No restart is needed for a settings change. This protection is tied to the Windows account; Azure needs separate managed-secret configuration.

## Review workflow

1. A cleared lawyer selects a folder in Firm → Documents, checks its preview list and imports selected synthetic files into a validated matter.
2. Confirm the declared classification. Competitively sensitive and privileged content retain their restrictions; a relaxation needs its separate approval workflow.
3. For an image-only PDF, queue offline OCR. The worker uses local English/German Tesseract models and creates a **new source version**, retaining the original PDF and historical version. Read the original page beside the transcript and record verification before confirmation/analysis. Engine confidence is not a measured accuracy guarantee. The local OCR limit is ten pages per request.
4. A scoped Legal SME chooses the independently approved **eight-risk English/German checklist** and requests a first analysis of that source version. The original starter checklist remains in history; select the intended version explicitly.
5. The worker checks identity, walls, clean-team clearance, document attributes and processing policy before provider calls and again before saving results. It covers all text windows within its explicit bounds; oversized sources fail instead of silently claiming a full review.
6. Risk Review shows candidate assessments, conditions/exceptions, proposed severity and exact original-language evidence. A lawyer confirms, corrects or rejects findings and makes the materiality/action decisions. An individual finding decision does not complete whole-document review.
7. A different cleared lawyer approves each audience release. Clean-team sanitization additionally requires the antitrust decision. The bank cannot receive privileged/legal-advice lineage.

The eight categories are change of control, assignment, exclusivity, non-compete, termination, liability caps, governing law and data protection. Document language never establishes governing law. The checklist is synthetic legal-review guidance, not a researched or professionally cleared playbook for a real matter.

## Evidence and costs

The model selects numbered original passages. The server attaches their retained text and Unicode offsets; the model cannot manufacture a source location. Coverage explicitly distinguishes identified, not identified and uncertain. **Not identified is not legal clearance.** Returned assessments still require legal review for relevance and accuracy.

[USER DECISION] Each document run, report-drafting operation or Q&A synthesis reserves at most USD 2 against the same USD 10 calendar-month application ledger. Known usage settles conservatively at pinned rates. Unknown/failed calls retain reservations; there is no automatic paid resend. These limits do not cap other OpenAI clients on the account. Start never runs paid checks.

## Observed verification

Normal HTTPS accounts and the real worker/provider were used; no output was released externally:

| Synthetic case | Observed result |
|---|---|
| German contract; English/Welsh governing-law clause | Eight expected cited risk groups |
| New, distinct English supplier-contract holdout | Eight expected cited risk groups |
| English delivery receipt negative control | No risk groups |
| Scanned English assignment clause, after transcript verification | One expected cited assignment group |

The original English evaluation job was rejected by the older quote/offset interface and remains retained. It was not resent or overwritten. The separate English holdout is a different agreement receiving its first review. The failed job's USD 2 reservation remains held. At the latest live check, the application recorded six cents estimated usage and USD 2 reserved. This small synthetic set is not a production recall/precision benchmark.

Explicit paid verification commands: `scripts/verify_live_ai_review.py --execute --only <case>` and `scripts/verify_next_phases.py --execute`. Existing request IDs prevent automatic resend. Preserve their `.runtime` markers. Historical reanalysis and billing reconciliation remain separate workflows; do not delete a marker/job to bypass their gates.
