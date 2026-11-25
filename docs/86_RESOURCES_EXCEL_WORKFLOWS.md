# Resources Excel workflow scripts

24 November 2026. [USER DECISION / IMPLEMENTED LOCAL SLICE] Resources task scripts are actual Excel workbooks. There are 34 workflow IDs, 42 organization/role variants and 249 numbered steps. This documentation does not mark the remaining application gates complete.

Resources now provides a visible **Excel workflow (.xlsx)** download beside each permitted guide and a task/role search. Guidance and engine status expand on demand. The Markdown download contract remains available. Each workbook has one Workflow sheet, exact controls, prerequisites, expected results, HTTPS page links and editable Completion, Run date and Tester notes columns. The table header and step column freeze at B10. Completion is a personal checklist: no cell sends an application command or approves a record.

The focused **Approve AI stage profiles** workbook starts from the already-submitted contracts, drafter and quality profiles for Synthetic role testing — Project Kestrel (012345-789012). It uses the actual retained-version selector, configuration/test history, rationale, review affirmation and independent decision controls, then stops before Root publication. No account password or provider key is embedded. Independent human SME review remains pending unless subsequently recorded through the application.

The content catalog has separate internal/external financial, retrieval, disclosure and report workflows, separate firm/Halden/Castlegate collaboration, and separate clean-team variants. Halden original access explicitly requires an outside-business designation, named scope and independently approved exact source-version grant. Castlegate instructions use its own released-artifact pages and do not offer original access.

## Delivery and boundaries

- `GET /api/v1/resources/{guide_id}/workbook` returns a real XLSX attachment with no-store and nosniff. Existing Resources visibility is authoritative; Root has no blanket clean-team or legal-role override.
- Listing, Markdown and Excel responses authenticate and check guide visibility again immediately before emission. Changed session, role, wall or named-membership eligibility withholds the prepared response.
- Static templates contain instructions only. They do not query documents, account names, credentials or provider secrets. Link targets come from reviewed deployment settings, never Host/Forwarded assertions. Public-mode links use the approved public names; this is not public activation.
- Catalog/template SHA-256 bindings detect inconsistent local assets. This is an integrity check, not WORM storage or a legal signature.
- The authoring library runs offline during preparation. Packaged runtime assets and the standard-library OOXML hyperlink addition have no private authoring dependency on Azure. Native links are relationships rather than HYPERLINK cell formulas. No macros, embedded workbooks, external workbook references or hidden sheets are delivered.
- Start runs `verify_workflow_scripts.py` before starting services. Stop retains templates, local data/logs and downloaded workbooks. No new component or database migration is needed.

## Verification actually performed

- All 42 workbook sheets rendered; 11 contact sheets and the full SME approval sheet visually reviewed. Exported files read back with openpyxl without evaluating formulas.
- The same 30 authorization/package/freshness/integrity cases passed on SQLite (62.20 seconds) and isolated PostgreSQL schemas (61.04 seconds). These are the same cases, not 60 distinct scenarios.
- Coverage includes all listed guides for five audience types, active/expired/revoked/walled clean-team cases, Root denial, exact public navigation, hostile Host behavior, role/grant changes during rendering, source/person/credential canaries and isolated asset-tamper rejection.
- TypeScript/Vite build passed (82 modules). Local Start completed successfully with five fresh ready components and existing fixture decisions preserved.
- The six existing observability/governance cases, including the previous Markdown clean-team contract, passed in 10.38 seconds.
- Actual authenticated HTTPS read: 14 guides for the synthetic admin, focused workbook HTTP200, 11 steps/11 native hyperlinks, B10 freeze, one completion dropdown, zero cell formulas. Receipt: `delivery/frontend_preview/resources-verification.json`.
- Browser verified task search and the visible Excel link; preview: `delivery/frontend_preview/resources-excel.jpg`. Browser download-event automation stalled; no completed browser download or native Excel UI execution is claimed. The production HTTP attachment itself was successfully retrieved and parsed.
- No model call, independent approval, source/release change, cloud deployment or database migration was performed for this slice. Broader gate status remains in docs80; a separate observed heartbeat-publication issue is being fixed and tested independently.

## Safe rollback

Restore the previous Resources UI/API and launcher preflight together if necessary. Preserve the catalog, templates, outputs, tests and logs for inspection. No retained business record or schema needs reversal. Rebuild the frontend and perform a controlled local restart; do not delete user completion workbooks.

## Submission wording refresh on 24 November 2026

The `review-work`, `lawyer`, `admin`, `audit` and `tables` default guides now describe the later Tasks & assignments, exact finding review, current contract/licence register, Accounts directory, scoped Audit and Registry grids. The update changes instruction prose only. The catalog still has 34 guide IDs, 42 variants and 249 steps, with unchanged audience roles and page-link targets. Existing permissions, hyperlink construction and application commands are unchanged.

All 42 templates and sample downloads were regenerated through the existing offline Artifact Tool builder. The five changed sheets were visually reviewed. The launcher catalog/template hash verification passed for all 42 variants. The focused Resources suite passed **30/30 on SQLite in 53.29 seconds** for this wording refresh. No new PostgreSQL or native Excel execution is claimed. The [dated verification receipt](../delivery/submission_20261124/RESOURCE_GUIDANCE_CHECKS.json) records the new catalog/manifest bindings.

The deadline manual scope is the [candidate core flow](../delivery/submission_20261124/CORE_FLOW_CHECKLIST.md), followed by any later extended workbook walkthrough. No completion of all 42 workflows or genuine approval is implied by regenerated instructions or checked package hashes.
