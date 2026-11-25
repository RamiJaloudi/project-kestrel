# 04 — Threat model, permissions and identity

## Concrete role/attribute rules
**Default deny**: `allow = authenticated AND session_valid AND org_allowed_on_host AND matter_assigned AND not_ethically_walled AND action_permitted AND object_policy AND source_version_access AND audience/release_scope_match`.

- For source documents and internal AI candidates, Halden/Castlegate have **no broad raw-source rights**; a specific clean-team user may see a named scoped subset as explicitly authorized.
- `is_clean_team` is **not a blanket role**; require named member + matter + approved subject area + active term + item label. Banking audience is not a clean-team member by default.
- `firm_reviewer`: cannot review matter if walled; can confirm/correct/reject only assigned matter evidence.
- `firm_release_approver`: may release only approved findings to permitted audience and only if privilege/label allows. Clean-team-derived content may require separate antitrust counsel verification and sanitized artifact approval.
- `root_admin`: may manage accounts/playbook drafts/technical infrastructure but does NOT automatically access walled matter content or approve own legal changes.
- `legal_sme`: may review legally relevant playbook diff/impact, approve version (when independently assigned), authorize specific reanalysis, and see only content they are cleared for.
- `audit_admin`: permission-scoped governance metadata, not automatic privileged source passage access.
- `service_worker`: job-scoped processing identity restricted to authorized dataset and purpose; not arbitrary admin.

## Matrix (must enforce routes + background jobs + search)
| Role | Internal docs | Candidate findings | Manage playbook drafts | Approve legal version | Approve rerun | Release externally | Clean-team source |
|---|---|---|---|---|---|---|---|
| Root admin | matter-scoped only | scoped only | Yes | No | No | No | only if named |
| Firm attorney | assigned/unwalled | assigned/unwalled | suggest changes | only if separately SME, independent | only if assigned SME | if authorized | named only |
| Legal SME | assigned/unwalled | authorized scope | review/comment | Yes, no self-approval | Yes, independent and scoped | separate authority | named only |
| Antitrust counsel | assigned/unwalled | restricted if named | clean release rules | if designated | if designated | separately approves sanitized CT release | named only |
| Halden user | explicitly released only | never raw | No | No | No | No | named+specific only |
| Castlegate | released commercial only | never raw | No | No | No | No | No by default |
| Walled firm lawyer | No | No | no matter data | no matter approval | no matter approvals | No | No |

## Security tests that must pass before publicly reachable demo
- Fail closed for unknown host, absent/expired/revoked session, wrong org, walled user, inactive clean-team member, wrong matter, unapproved finding, non-released artifact, restricted metadata and negative RAG access.
- Prevent IDOR via direct document ID, finding ID, preview endpoints, reports, search snippets, vector indices, citation clickthrough, storage URLs, exports, notifications and error messages.
- Secure real accounts: Argon2id, no hardcoded credentials, controlled bootstrap, short server sessions, httpOnly secure host-only cookies, CSRF for state-change cookie requests, limited login attempts, lockout, revocation, no permissive CORS. Avoid social login complexities for initial demo.
- `root_admin` can never forge `legal_sme` approval; self-approval denied by invariant, including through direct API.
- Users can never approve a rerun based on stale impact hash, changed playbook status, altered affected item set or revoked membership.
- No live real firm branding or real data; place disclaimer on all public pages and synthetic-only fixtures in every flow.

## Prompt injection
Treat all VDR contents as adversarial evidence, never system instructions. No model authorization decisions, no tool execution based on contract text, no unfiltered prompts/logs. Constrain structured outputs, validate evidence against trusted source spans. Stage policy filtering **before** retrieval, reranking and model calls; verify again at citations and output.

## Access boundaries vs domain UX
Proposed demo hosts: `kestrel-firm.ramijaloudi.com`, `kestrel-client.ramijaloudi.com`, `kestrel-bank.ramijaloudi.com`. **Not configured; need domain control.** Host determines shell; verified session determines org. Firm host login does NOT authorize a Halden user merely because they know its URL. Use per-host host-only cookies and same-origin API reverse proxy; never wildcard-auth cookies.
