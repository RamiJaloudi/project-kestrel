# Confirmed scope — 20 November 2026

## [USER DECISION]
- Preserve ethical-walls-matter's client/matter, batch and email-wall contracts; extend through versioned document-authorization endpoints. Parity requires a measured contract/test comparison, not a claim based on screen appearance.
- Project PostgreSQL and SQL read views are authoritative for registry, identity policy and document attributes. SQLite remains an isolated test fallback, not the selected project source.
- Document policy covers contracts/licences, pricing/financial records, internal advice, client uploads, findings, Excel trackers and due diligence reports.
- Independent state dimensions: processing/classification; lawyer review; audience release; quarantine; supersession; signing freeze. Freeze preserves read eligibility and blocks mutation, not all reading.
- AI can suggest attributes and provisionally tighten restrictions; human confirmation and separate authorized approval required to relax them. AI never grants access.
- OAuth service clients/scopes required alongside real browser sessions.
- Firm has Diligence Trackers and Reports & Board Pack areas. DB records authoritative, validated Excel import and versioned export.
- Trackers have server-filtered rows; separate audience-specific lawyer-approved exports. Hidden sheets/rows are not security.
- Reports: Word/PDF plus Excel risk/consent annexes. Only reviewed eligible findings, verified source references, audience-safe outputs.
- Each complete audience-specific package/version is approved separately. Content or contributing-version changes require new approval; retain old approved versions and support authorized revocation.

## Implementation order and acceptance
1. Move local launch to dedicated PostgreSQL (reuse installed native binaries, isolated project cluster; do not modify other databases/services). Validate migrations/views against actual PostgreSQL. Back up/preserve earlier SQLite records separately; no silent approval or account copying.
2. Document version attributes and deterministic policy decisions with explicit action/type/state checks. Test unknown/quarantine/walls/wrong matter, bank privilege, clean team, source inheritance, freeze, supersession, AI restriction, row filtering and recipient release.
3. Contract-compatible validation/walls/batch adapters and OAuth scoped service identities, revision-based decisions, audit and fail-closed outages; publish dedicated Swagger per API. Must not copy permissive legacy behavior/defaults that conflict with deny-by-default.
4. Tracker import/row/export and report package lifecycle, reference immutable finding/source snapshots. Generated Word/PDF/Excel requires respective artifact skills and rendering/validation; never count a placeholder as an export.

## Current sprint boundary
Small independently tested increments; no attempt to build the complete platform in one response. Preserve assessment readiness. Record what actually runs versus follow-on work after each increment. No public exposure, real documents, real identity/wall providers or legal clearance claims. Rollback: stop owned processes, restore backed-up selected DB, review/revert source; preserve old DB and issued packages. No blanket data deletion.
