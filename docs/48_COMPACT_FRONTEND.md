# Compact frontend refinement — 22 November 2026

## Scope
Frontend presentation only: tighter spacing, readable controls, shorter labels, clearer active states, expandable help and focused workflow tabs. Authorization, approval gates and stored data are unchanged.

## Changes
- Added frontend/src/compact.css as the final shared styling layer, imported in main.tsx. Compact cards, tables, sidebar, profile, forms and responsive layouts retain visible keyboard focus and larger touch targets.
- WorkflowSteps now uses an expandable guide, preserving all workflow links and role guidance.
- PortalApp removes a duplicate navigation item while retaining its existing route; portal descriptions are shorter.
- Administration groups optional registry tools and registration forms in expandable sections, with clearer navigation and a compact validation form.
- TrackerExchange separates import, export preparation and approval/download into focused tabs. Hidden sections preserve form state. Approval and audience restrictions remain visible where relevant.
- ActionCenter, MatterWorkspace and PortalHome use shorter introductory text and headings. Home groups additional API links under expandable details.
- Start and Stop batch files include a presentation-update note; service lifecycle behavior is unchanged.

## Verification
- npm --prefix frontend run build: passed (TypeScript and Vite, 44 modules).
- Browser visual checks: Portal Home, authenticated Firm tracker import/export/approval tabs, and read-only Administration preview.
- Verified tracker tab switching without submitting imports, releases or approval decisions.
- Screenshot: outputs/compact-frontend-preview.jpg.
- Backend tests were not rerun for this presentation-only change. No service restart or database migration was needed.

## Rollback
Initial source copies for main.tsx, PortalApp.tsx, WorkflowSteps.tsx, Administration.tsx, TrackerExchange.tsx and ActionCenter.tsx are in .runtime/ui-backups/20261122-022048. Restore those copies and remove the compact.css import to undo the main layout changes. PortalHome, MatterWorkspace and batch-file wording edits can be reverted separately. Rebuild frontend afterward. No database rollback is required.
