# 78 Explicitly approved PUBLIC_DEMO runtime

24 November 2026. [IMPLEMENTED, NOT ACTIVATED] The application now has a separate `PUBLIC_DEMO` mode alongside `LOCAL`. This is preparation for the synthetic single-VM design in document 66 and the closed-by-default Azure template. It is not an approval, deployment, certificate, DNS change or claim of public readiness. No real public configuration, acceptance receipt, proxy token or owner approval manifest was created. The live local launcher and database are unchanged by this slice.

## Concrete runtime and owner-controlled parameters

`LOCAL` remains the default. Its existing local host allowlist, five-console launcher, HTTP preview and local HTTPS behavior remain. Unknown environment names, including `PUBLIC`, are refused. `PUBLIC_DEMO` loads an external JSON file named by `KESTREL_PUBLIC_CONFIG`; it cannot be enabled by a web request or a Boolean approval flag.

| Required configuration field | Required value / owner input |
|---|---|
| `schema`, `mode` | `kestrel-public-config-1`, `PUBLIC_DEMO` |
| `hosts` | Exact map below, including `null` for the home host |
| `backend_host`, `backend_port`, `workers` | `127.0.0.1`, `8000`, integer `1` |
| `owner_sid` | Actual owner Windows SID, pending owner identification |
| `service_sid` | Separate non-owner application service SID, pending provisioning |
| `proxy_sid` | Separate reverse-proxy service SID, pending provisioning |
| `proxy_token_file` | Absolute external local file; owner-generated random URL-safe token, 43–128 characters |
| `approval_file` | Absolute external owner-maintained approval JSON path |
| `receipt_file` | Absolute external completed acceptance-receipt JSON path |

The exact host map is:

```json
{
  "portal.ramijaloudi.com": null,
  "firm.portal.ramijaloudi.com": "firm",
  "halden.portal.ramijaloudi.com": "halden",
  "castlegate.portal.ramijaloudi.com": "castlegate",
  "admin.portal.ramijaloudi.com": "firm"
}
```

The home host has no authenticated content organization. Administration selects the firm organization and preserves all existing role, matter, ethical-wall, clean-team and approval checks. A hostname grants no role or document entitlement.

## Approval protocol outside the Web API

The owner creates the configuration, receipt, token and approval files manually outside the application/frontend tree. Each file must have a protected explicit NTFS DACL: owner and SYSTEM may write; the application service receives read access only. The token additionally permits the named proxy service to read. Inherited, broad, unknown or service-writable grants are refused. The running process must match the separate configured application SID, must not be the owner, and must not be an elevated administrator/SYSTEM process. No environment variable bypasses this OS check. Paths must be absolute local files; symlinks and UNC paths are refused.

`python -m kestrel.public_inspection <external-config-file>` is a read-only owner review helper. It prints the configuration hash, release hash, acceptance-test-source hash and public hosts. It does not read a key/token or write an approval. The release hash binds backend code, migrations, test sources, dependency locks, frontend source/build and the reviewed Caddy example; every changed release must be reviewed again. Do not populate hashes until the final build and test sources are frozen.

The receipt schema is `kestrel-public-acceptance-1`. It must bind `release_hash`, `config_hash`, `test_suite_hash`, `all_required_passed: true` and exactly these `required_checks`: `backend_full`, `public_boundary`, `postgres_restore`, `frontend_build`, `tls_proxy`, `windows_services`, `backup_recovery`, `owner_review`. The owner must retain the real evidence for each check. A fixture receipt is not that evidence.

The approval schema is `kestrel-public-approval-1`, with decision `approve-public-synthetic-demo`. It binds the exact owner SID, mode, host map, configuration hash, release hash, test-suite hash and SHA-256 of the receipt bytes, plus integer UTC epoch `approved_at` and `expires_at`. Approval cannot be future-dated, expired or last more than seven days. This document deliberately creates no completed approval artifact. The service checks all bindings and ACLs at startup; approval removal/change, receipt change, configuration change or expiry closes subsequent public requests. A new release requires restart and a fresh matching review. The manifest is an owner filesystem attestation, not a legal/content approval or a substitute for the final infrastructure permission.

The actual release directory and every ancestor of owner files must also be owner-controlled, with no application/proxy write, rename or delete-child authority. A protected file DACL alone cannot establish that boundary. This deployment-directory/ancestor check and the distinct-account rehearsal remain pending operational evidence.

## Proxy and browser boundary

The separate future service entrypoint is `python -m kestrel.public_service`. It refuses LOCAL mode and fixes Uvicorn to `127.0.0.1:8000`, one worker, `proxy_headers=False`, no trusted forwarded IP ranges, no WebSocket listener or access logs, bounded concurrency and headers. No invocation was made to bind a service. The existing LOCAL start scripts were not changed.

The [review-only Caddy example](../deployment/Caddyfile.public.example) uses the five exact HTTPS names, strict SNI/Host matching, no admin listener, no configuration persistence and no access/body logs. It strips client forwarding, identity and private protocol headers, then overwrites `X-Kestrel-Proxy-Token`, `X-Kestrel-Proto: https` and `X-Kestrel-Client-IP` from its actual socket connection. The owner supplies the random token privately to both service identities. Caddy's official documentation describes [header overwriting/removal](https://caddyserver.com/docs/caddyfile/directives/reverse_proxy), [SNI matching and server timeouts](https://caddyserver.com/docs/caddyfile/options), and [request body bounds](https://caddyserver.com/docs/caddyfile/directives/request_body). The implementation agent installed/ran no Caddy binary. Root subsequently verified the official 2.11.9 archive and ran only offline version/adaptation; see docs82. Actual module provisioning/validation and TLS rehearsal remain required.

The backend requires an actual loopback peer and a constant-time matching private token before trusting that private protocol. Generic `testclient` is never accepted in PUBLIC_DEMO. All standard `Forwarded`, `X-Forwarded-*`, `X-Real-IP` and demo identity headers are removed before downstream request handling. Unknown hosts, direct IPs, suffix lookalikes, trailing dots, non-443 ports, insecure or cross-host origins and duplicate security headers are rejected. Case and explicit port 443 normalize to the exact approved host. Uvicorn must not pre-process forwarding headers before this check.

Sessions retain `__Host-` host-only Secure/HttpOnly/SameSite=Strict cookies, session-host and organization binding, current identity checks and existing CSRF rules. No wildcard cookie, CORS exception, demo user header or source-access override is added. Public Swagger HTML, schemas and supporting assets require a genuine same-portal session. Schemas are curated by current organization/roles, external paths/components are filtered, and authority is checked again after preparation. The service endpoints still apply their own canonical PDP checks.

## Bounded traffic and UI behavior

Public headers are bounded to 16 KiB; ordinary bodies to 4 MiB, login bodies to 16 KiB, upload duration to 20 seconds and ASGI body fragments to 1024. Existing source-file validation retains its 3 MiB file limit. Folder imports remain sequential existing per-file requests with the existing aggregate folder constraint; this is not a 4 MiB folder restriction. There are at most four concurrent password verifications and 64 server requests.

Per-process rate counters use a lock, fixed expiry and at most 4096 retained keys, with refusal rather than active-key eviction when full. Limits are 600 API requests/IP/minute, 240 authenticated API requests/account/minute, 1200 ordinary web requests/IP/minute and 60 login requests/IP/15 minutes. IPs come only from the authenticated proxy protocol. The existing account/peer login database limits now use atomic conditional SQL increments; they retain their local failure/reset behavior. The one-worker restriction is part of the approved configuration; multiple processes require a separately reviewed shared limiter.

`/site-config` returns only exact trusted navigation metadata. Public home shows no database readiness, runtime-console links or design preview; `/preview`, `/launch-info`, `/health/ready`, debug and diagnostics paths are closed. Minimal `/health` contains no database or source details. Frontend portal selection and authored guide/navigation URLs use the approved hosts; source text, citations and evidence URLs are never rewritten. A compatibility fallback for a missing `/site-config` exists only on known LOCAL hosts, allowing the already-running local API to show a newer frontend without a restart. Public and unknown hosts have no fallback.

## Verification and remaining gates

- LOCAL authentication regression: **22 passed in 32.80 seconds**.
- LOCAL authentication plus preview/Swagger regression: **24 passed in 99.81 seconds**.
- Initial public SQLite suite: **14 passed in 22.07 seconds**.
- Expanded isolated PostgreSQL public suite: **16 passed in 27.09 seconds**, including retained real synthetic upload limits and a mid-preparation Swagger role revocation.
- TypeScript/Vite build passed; root separately inspected the branded local Home, Firm and Administration previews.
- Final public PostgreSQL suite: **19 passed in 32.61 seconds**; combined public/LOCAL authentication SQLite suite: **41 passed in 57.51 seconds**.
- Final LOCAL preview/Swagger check after independent financial-context grouping: **2 passed in 7.10 seconds**. Final TypeScript/Vite build: **82 modules passed**. Python compile checks passed.
- A real temporary Uvicorn listener bound only to an ephemeral `127.0.0.1` port verified rejection without private proxy proof, rejection of direct-IP Host, and removal of forged forwarding headers. The listener stopped automatically. This socket test plus owner configuration/receipt revocation: **2 passed in 4.31 seconds**, with isolated SQLite and fake owner files. It is not a live-service or TLS deployment.
- After preserving the original full LOCAL OpenAPI schema and explicitly denying administrator service execution: LOCAL preview plus owner-gate smoke **3 passed in 7.52 seconds**, and compile checks passed.

Temporary test approval files live only under pytest fixture directories. The OS owner/service ACL boundary is explicitly mocked in those fixtures; actual distinct-identity NTFS enforcement has not been claimed tested. The real socket test requires local network permission when running inside the workstation sandbox; it opens no public listener and does not use live PostgreSQL.

Still required before any actual public use: final full regression and frozen hashes; private Caddy adaptation/TLS/header-poisoning rehearsal; distinct Windows owner/app/proxy ACL validation; loopback-only service/firewall/PG checks; verified restore and archive portability decisions; service boot/recovery and backup evidence; exact DNS/certificate verification; genuine account provisioning; owner-written final receipt and approval; and separately authorized Azure/Windows ingress. The Azure template keeps `allowPublicWeb=false` by default. No PostgreSQL, pgAdmin, application port, Caddy admin port or broad RDP ingress is authorized by this runtime gate.
