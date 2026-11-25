# Target Windows services — plan and static drafts

24 November 2026. This folder prepares review-only WinSW configuration. It does not install, start, stop, grant rights, create accounts, change recovery policy or authorize PUBLIC. Keep all target inbound web closed. No workstation services should be changed to test this plan.

## Scope, assumptions and rollback

Files: `prepare_service_plan.py`, `service-plan.example.json` and isolated `tests/test_service_plan.py`. The generator uses only the Python standard library and a strict nonsecret input schema. It writes a **new** review directory, two `.xml.review-only` drafts and a JSON plan. These names deliberately cannot be discovered as the final service XML. No binary is downloaded/copied and no installer command is executed. Unknown input fields, built-in identities, overlapping owner/app/proxy SIDs and unsafe/relative/UNC/expandable paths are refused.

The API draft runs the existing `python -m kestrel.public_service`; its production approval gate is unchanged. The Caddy draft names the reviewed public configuration but contains no proxy token. Both remain unfit for installation until owner-controlled database/profile/token/ACL prerequisites are verified. The worker is a **blocked plan row without XML**: `console_runner.py worker` is a LOCAL launcher, not an accepted PUBLIC worker service.

All three planned services are Manual, with no automatic restart or reboot action. Logs append; there is no reset, rotation, purge or automatic deletion. Owner monitoring/diagnosis and an explicit later manual start follow a failure. Reboot proof means services remain stopped until authorized manual startup and then recover safely; this plan does not promise unattended boot. Stop timeout/termination behavior needs target testing, especially lease recovery for any future worker.

WinSW append logs are only one part of permanent technical/audit retention. Target acceptance must separately configure Windows Event Log preservation, PostgreSQL logs, proxy/runtime diagnostics and application audit/backup retention without automatic loss. Rotation must preserve prior segments. Prove monitoring, capacity/budget alerts and owner-approved capacity handling; never silently purge older evidence when space runs low.

Rollback is stop-only: after separate authority, stop the affected service, retain its registration/configuration/logs and keep web closed. No automatic uninstall, account deletion, credential reset, source modification or data merge is authorized.

## Wrapper evidence and target prerequisites

The candidate wrapper is official [WinSW v2.14.0](https://github.com/winsw/winsw/releases/tag/v2.14.0). Root independently retrieved release asset metadata: Windows x64 asset SHA256 `4ebd9dc3e817f80b2bd8c18f5bfe0d550241c1d08b57bd9694777a6e56a7b24f`, 18,845,338 bytes; NET462 alternative SHA256 `5099b87c7b2d8ec6441adc477aa9d82aa3cee132b6dd69f95682212ac3b61654`, 788,992 bytes. The generator pins only the x64 candidate metadata. This is not proof of an installed/verified target binary. Independently verify the exact downloaded bytes, signature result, provenance, licence, architecture/runtime, malware policy and target execution before selecting it. Do not silently choose an alternative asset or latest version.

WinSW's [versioned XML specification](https://github.com/winsw/winsw/blob/v2.14.0/doc/xmlConfigFile.md) supports Manual startup, append logging, `onfailure action="none"`, an explicit working directory and bounded stop timeout. Its [installation guide](https://github.com/winsw/winsw/blob/v2.14.0/doc/installation.md) pairs each renamed executable with the same basename XML. The drafts omit `<serviceaccount>` because they are not installed through WinSW's default installer. Its default LocalSystem installation is forbidden here. Version 2 examples use `domain`/`user`; no password should ever be put in either version's XML.

Before installing anything, an authorized target owner must establish:

1. Real separate owner, nonadmin app and proxy accounts/SIDs, persistent profiles and independently granted Log on as a service rights. Reject built-in privileged identities, owner-as-service and an unresolved SID. No installer grants those rights automatically. PG uses its separately reviewed identity.
2. Owner-controlled release/service/config ancestors, binaries and XML, without app/proxy write/delete-child substitution. Precreate narrowly writable runtime/log children. Protect token, DB configuration and DPAPI material with the intended identity boundaries; process-local probe checks do not replace ancestor review.
3. A real loopback-only PostgreSQL configuration, target credentials and profile provisioning. `database_url()` currently has a SQLite fallback; never start PUBLIC without independently verifying its actual PostgreSQL connection and least-privilege role. Do not embed a credential-bearing URL in XML or installer arguments.
4. A reviewed process-only Caddy token-loading launcher: it must read the separate owner-controlled token under the actual proxy identity, set only its child process environment, never log/persist the token or fall back to an empty/default value, and preserve the existing exact Caddy header protocol. This generator does not implement that launcher. Machine/user environment registries and XML are not secret stores.
5. A reviewed PUBLIC worker entrypoint that checks the same owner gate and intended database at startup, uses normal lease/current-authority checks, has bounded shutdown/diagnostics and keeps live AI/OCR off until separately authorized. No runnable worker configuration is produced before that review.
6. Genuine completed public receipt/approval for the final source/build/config hashes, actual service profile/ACL proof, closed proxy/TLS tests, backup restoration and archive migration. The platform/proxy probe provides only its expressly recorded subchecks. No forged pass files or LOCAL proxy shortcut.

## Owner installation sequence — target only, not an executable installer

After independent approval, copy/hash the reviewed wrapper into separate owner-controlled service directories and rename it to match the selected service ID. Review/promote each `.xml.review-only` only after its blockers are resolved. Use the Microsoft [New-Service credential interface](https://learn.microsoft.com/en-us/powershell/module/microsoft.powershell.management/new-service?view=powershell-5.1), with `Get-Credential` held only in an in-memory `PSCredential`. Do not invoke `winsw install`, which can default to LocalSystem; do not put a password in XML, a command argument, transcript, JSON or command history. An actual service installation is a separate approved target change.

For each approved service, the future installer must resolve the supplied account to its expected SID before creation; use `New-Service -Credential <in-memory-object> -StartupType Manual` and a correctly quoted wrapper-only `BinaryPathName`; then query `Win32_Service` and resolve `StartName` back to the exact expected SID. Verify Manual start mode, stopped state, executable path and no recovery actions before permitting any manual start. Any mismatch leaves the service stopped for diagnosis, with no fallback, rename, reinstallation or automatic deletion. Test the installer in an isolated Windows target before accepting it; this static generator is not that test.

The XML `onfailure` value alone does not prove SCM recovery policy when service creation uses `New-Service` rather than WinSW's installer. Inspect the actual target service failure actions and ensure they are empty/none; never infer that result from a draft. Refuse an already registered service instead of changing its identity or recovery policy as an incidental repair.

Only after the valid PUBLIC gate and all component prerequisites are satisfied may the owner manually start the actual API, reviewed worker and proxy. Exact source hashes must be recomputed after all deployment changes. Keep outside ingress closed until the separately authorized final visibility checks. Retain actual stop/crash/reboot/session/DPAPI/PG evidence; static XML and a generic SCM probe do not establish a working production stack.

## Preparation and tests

From the project root:

```powershell
backend/.venv/Scripts/python.exe deployment/azure/services/prepare_service_plan.py --config deployment/azure/services/service-plan.example.json --out .runtime/service-plan-REVIEW-ONLY
backend/.venv/Scripts/python.exe -m pytest deployment/azure/services/tests -q -p no:cacheprovider
```

The example uses synthetic paths/accounts/SIDs and is not approved target configuration. The first command only writes drafts to a new directory. Tests exercise strict parsing, path/account safety, fixed commands, Manual/none/append semantics, absence of secrets/account installer XML and blocked worker output. They do not install a service or validate Windows SCM. This tooling is separate from the frozen application suite and not a public readiness claim.

Preparation self-tests on 24 November: **29 passed in 0.10 seconds**. No service installation, account/logon-right change, recovery setting, listener or target command was executed.

After the probe shutdown-limit check, the final combined deployment-only run passed **48 tests with 1 real-target OS test skipped in 0.38 seconds** across this folder and `../qa/tests`. This separate preparation result is not added to the frozen application-suite aggregate.
