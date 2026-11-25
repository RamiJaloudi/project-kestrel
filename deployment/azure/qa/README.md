# Closed platform and proxy probe — implementation plan

24 November 2026. This is synthetic target QA tooling, not a production launcher, a public runtime mode or approval to create Azure resources. No account, service, firewall, DNS or application change is performed by this tooling.

## Files and scope

- `closed_probe.py`: source fingerprints, real configured Windows identity/file-ACL and synthetic CurrentUser DPAPI checks, and a bounded loopback-only instance of the existing `PublicBoundary` around a route-minimal ASGI probe.
- `qa-config.example.json`: distinct schema for a short owner-controlled QA lease; no operational acceptance or approval fields.
- `Caddyfile.closed.example`: exact reviewed hosts, loopback HTTPS only, an owner-supplied certificate and separate QA token. No automatic certificate acquisition.
- `tests/test_closed_probe.py`: isolated self-tests; no database, service installation or TCP listener. Real OS tests run only when an operator explicitly supplies the target QA configuration.

Assumptions: an independently authorized closed Windows target; separate nonadmin application and proxy identities; owner-controlled code and every ancestor directory; existing locked Python dependencies; no external web ingress; a separately trusted test certificate. None is proved by this document. The current workstation must not be reconfigured to satisfy these assumptions.

Rollback: stop the foreground probe or its separately reviewed service wrapper; leave inbound web closed; retain the isolated evidence, configuration and technical/audit logs under the owner's retention policy. There is no automatic deletion and no database or operational state to merge back. Expiry or owner removal/change of the QA lease/token closes subsequent requests; the server begins shutdown at the deadline with a five-second graceful-shutdown limit.

## Acceptance boundaries

The normal `load_deployment()` and `public_service.main()` remain unchanged. No matching `kestrel-public-acceptance-1` or `kestrel-public-approval-1` file is generated. The probe does not call `create_app()`, install application routes or connect to a database. A small, explicitly named QA settings object supplies the existing boundary's interface and checks the real expiring QA lease. It is never accepted by the production loader.

The only probe route is `/closed-probe`, returning fixed synthetic metadata after proxy validation. It cannot reflect arbitrary headers, accept a document, authenticate a user or invoke a provider/worker. An extra outer guard permits only an actual IPv4 loopback connection and a loopback original-client address; it closes on lease drift. `PublicBoundary` still performs its own exact host/origin, private-token, forwarding removal and request bounds checks. A successful request is explicitly labelled closed QA, not PUBLIC readiness.

The real platform command invokes the existing `_windows_private_file()` without mocking it, checks the actual process SID, and encrypts/decrypts only a random synthetic DPAPI marker under that service profile. It never reads a provider credential or archived source. A same-profile round trip does not prove portability or cross-account denial. Separate target identity/challenge and source-decrypt/target-reencrypt work remains pending.

Identity, DACL and source-hash checks occur at lease loading and platform verification. Request-time lease checks cover expiry and configuration/token contents; they are not continuous identity, DACL, ancestor-control or code-integrity attestation.

## Target-only sequence

1. Obtain explicit authority for the isolated target, test identities and synthetic files. Keep Azure `allowPublicWeb=false`, Windows inbound web denied, PostgreSQL private and paid AI/OCR off. Verify the actual network rules and owner-controlled ancestors independently. This tool cannot attest those rules from a process-local socket.
2. Complete code changes/build/tests, then run `closed_probe.py fingerprint`. The owner copies the example outside the release tree, fills the actual three distinct SIDs, exact hashes and a fresh lease of at most 15 minutes, and privately provisions a separate random 43–128 character QA token. Apply protected explicit DACLs using the existing public-gate policy: owner/SYSTEM write, app read; proxy additionally reads only the token. Never copy a production token or receipt. Use a fresh service profile with its own DPAPI material.
3. Run `closed_probe.py verify-platform --config <external-qa-config> --evidence <new-evidence-file>` as the actual nonadmin app identity. Failure remains failure; no mock fallback. The output reports exactly the configured identity, file checks and synthetic DPAPI result, with all service/public/migration claims explicitly pending.
4. After independent Caddy binary/config/certificate review, bind the closed Caddy template only to `127.0.0.1:443`. Use local name resolution or a TLS client with explicit connection resolution and normal CA/SAN/hostname verification; never `--insecure`. Start `closed_probe.py serve --config <external-qa-config>` as the app identity. It binds only `127.0.0.1:9446`, one process, no forwarded-header trust, with a lease of at most 15 minutes and up to five seconds for graceful shutdown. The proxy must overwrite its private headers from the actual connection; QA requests originate on the target itself. Do not expose LOCAL through Caddy.
5. Record actual certificate/SNI and header-poisoning tests, lease/token revocation, missing/wrong proof, direct-IP/suffix/port Host, cross-host Origin, duplicate security headers, body/header bounds and absence of application routes. Run the self-tests separately; fixture passes are not real TLS or OS evidence. No self-test writes an operational pass receipt.
6. A separately reviewed SCM-compatible wrapper/installer is still required. Prove actual API, bounded authority-checked worker, Caddy and PG identities/dependencies, least privilege, crash recovery, service-profile persistence and reboot. A generic probe service does not establish those application lifecycles. Test source-independent restoration on target; provider secrets require secure target reprovisioning and archives/backups need a proven portability decision.
7. Independently review evidence against all eight existing public acceptance criteria. Platform/proxy probe results may support their specific subchecks; they do not automatically satisfy a whole criterion. If a criterion requires a running production API/worker and remains untested, it stays pending. Only a genuine completed receipt and separate owner approval can start PUBLIC. The owner must resolve any remaining first-start acceptance dependency explicitly; this probe supplies prerequisites without forging completed acceptance. Controlled final activation/ingress needs separate user consent and post-start checks.

## Self-test commands and limits

From the project root, using the locked backend environment:

```powershell
backend/.venv/Scripts/python.exe -m pytest deployment/azure/qa/tests -q
```

On the authorized target only, supply `KESTREL_CLOSED_QA_CONFIG` in that test process to enable the real OS check. Without it, that check is **skipped**, never reported passed. It must run under the actual configured app SID. The test never creates accounts, grants rights or repairs ACLs. The operator must retain sanitized proof of Windows ACLs, independent negative identities and target policy outside this output.

Preparation self-tests on 24 November: **19 passed, 1 skipped in 0.68 seconds**. The real target identity/DACL/DPAPI test was intentionally unconfigured and skipped. These tests used in-process ASGI calls and fixed-server-option inspection, with no TCP listener or Windows configuration changes. Offline adaptation using the already reviewed Caddy 2.11.9 binary succeeded and produced only `127.0.0.1:443`, with HTTP/1.1 and HTTP/2. Synthetic certificate/key path strings were used; no certificate was loaded, listener started or ACME attempted. Actual TLS and all target OS/service checks remain pending.

No runtime code change is needed to gather these platform and proxy prerequisites. If later full application startup before final approval is required, propose a separately reviewed test-only composition and its limits; do not weaken `load_deployment`, reinterpret LOCAL as public, add a broad bypass flag or fabricate passes. Any later application/bootstrap change requires its own regression run.

After adding the five-second shutdown limit, the final combined deployment-only run passed **48 tests with 1 real-target OS test skipped in 0.38 seconds** across `qa/tests` and `../services/tests`. This is separate from the frozen application suite; it establishes no target OS, TLS or SCM acceptance.

All files under `deployment/` contribute to `release_hash()`. Finish and review this tooling before computing a deployment approval hash. The current application full-suite run does not include these self-tests or constitute acceptance of this tooling.
