# Azure preparation — closed candidate, 24 November 2026

This is a reviewable infrastructure and migration proposal for a **personal, synthetic interview demonstration**. It is not a deployment or production-readiness claim. The latest user decision is approximately **USD100/month all-in** and the five exact hosts below; this supersedes the earlier USD50/three-host assumptions in docs13. The enterprise matter architecture remains a separate design.

**Authenticated update, 18:32UTC:** Windows WAM/MFA login succeeded without policy changes. East US2 B2as_v2 returns `NotAvailableForSubscription` and Basv2 quota0/0; **the frozen new-VM Bicep below is not an available creation choice for this subscription**. Existing North Central US VM `vm-rplus-demo-ncus` has B2as_v2/Windows, a256GiB Standard SSD OS disk, no data disk, Standard security (not Trusted Launch), and Basv2 quota2/2 already consumed. North Central US SKU restrictions are empty, still subject to allocation capacity. The owner authorized this exact existing VM's paid start for read-only assessment: request18:29:18UTC, start completed18:30:30UTC /13:30:30EST, agent Ready18:32:20UTC. No deployment, guest configuration or ingress change is authorized. Guest inventory and reuse-purpose decision remain pending; preserve all existing resources/data/services.

The existing VM's **continuous-running base is USD84.46/month** (compute61.61 + E15 OS disk19.20 + static IPv4 3.65), plus the retained incremental snapshot, disk operations, backup/network/log growth, tax and AI. Fresh official North Central US receipts are in `.runtime/azure/retail-prices-northcentralus-2026-11-24.json` (18:26:46UTC) and `retail-existing-storage-northcentralus-2026-11-24.json` (18:30:23UTC). The Standard_LRS incremental snapshot is billed on used data at USD0.05/GB-month, not automatically its256GiB logical size; actual used billing is unverified ([Microsoft snapshot billing](https://learn.microsoft.com/en-us/azure/virtual-machines/disks-incremental-snapshots)). USD12.80 would be a full256GiB planning bound, not a measured bill. Two hours of the authorized assessment adds approximately USD0.17 compute before tax, with existing storage/IP charges continuing. No new disk/snapshot is created. The earlier USD79.66 table below describes only the unavailable new-VM candidate, not this reuse topology.

## Concrete owner decision

Propose one **East US2 Standard_B2as_v2 Windows Server2022 Gen2 Trusted Launch VM**, 2vCPU/8GiB, 128GiB E10 OS SSD plus 64GiB E6 data SSD, one Standard static IPv4. PostgreSQL stays on the same VM and loopback; Caddy terminates HTTPS and forwards to API127.0.0.1:8000. No managed PostgreSQL, public pgAdmin, public API port, Bastion, NAT Gateway, load balancer or paid log workspace is included. This is a small demonstration topology, not capacity for the brief's400,000 pages.

Owner-confirmed subscription: **HudsonRiverAI-R+Demo_Portal**, `bd7d0da6-eaa6-45c5-b4fb-01edc19f9b1a`. Root observed Portal Active/Owner; CLI verifies Enabled with the expected tenant. Three existing groups and nine resources were inventoried read-only; no proposed `rg-kestrel-demo-20261124` exists. Do not alter unrelated resources. The proposed new `kestrel-demo` topology is blocked by the verified East US2 restriction above. A future different region/SKU needs a new quote/template review and spare quota. `latest` is not an immutable image pin.

Immediate owner action: select that subscription, confirm this cost/design and a single public owner IPv4 for administration, then review the closed candidate/what-if when an authorized scope exists. **Do not select Create, change DNS or open web ingress yet.** Creation and public activation are separate approvals. Codex prepares tooling; Azure CLI/Portal provisions Azure. Tesseract performs OCR and does not provision infrastructure.

## Current cost evidence

The official [Azure Retail Prices API](https://learn.microsoft.com/en-us/rest/api/cost-management/retail-prices/azure-retail-prices) was queried **2026-11-24T17:56:22Z**, USD/East US2/Consumption, excluding Spot/Low Priority. Public receipt: `.runtime/azure/retail-prices-2026-11-24-latest.json`. This is a retail estimate, not a subscription quote, availability check, tax estimate, reservation, free-credit or Azure Hybrid Benefit assumption.

| Item | Reviewed rate | 730-hour month |
|---|---:|---:|
| B2as_v2 Windows compute | USD0.0844/hour | USD61.61 |
| E10 LRS128GiB OS disk | USD9.60/month | USD9.60 |
| E6 LRS64GiB data disk | USD4.80/month | USD4.80 |
| Standard static IPv4 | USD0.005/hour | USD3.65 |
| **Base subtotal** | | **USD79.66** |
| Disk operations allowance | USD0.002/10,000 operations | USD0–3 reserve |
| Small encrypted off-VM backup allowance | destination/retention not yet quoted | USD2–5 reserve |
| Modest network/log allowance | actual usage/eligibility varies | USD0–5 reserve |
| **Working estimate before tax and paid AI** | base plus reserves | **USD81.66–92.66** |

Keep another USD5–10 contingency. **Approximately USD85–100 is a tiny-workload planning range, not a hard cap or guarantee.** Tax, paid AI, larger backup retention or traffic can exceed it. The app's USD10 monthly AI ceiling is additional to infrastructure, not free capacity. Backup requires an actual destination/retention/restore quote before approval. Do not silently enable paid monitoring agents, Defender plans, Log Analytics, Azure Backup or support plans. Check existing subscription services as well as this VM. The user's permanent technical/audit retention decision means storage grows over time: this initial small-workload allowance cannot guarantee an indefinite USD100 ceiling.

For an explicit budget example:79.66 base +3 backup +1 operations +1 network/log +5 AI +5 contingency = **USD94.66 before tax**, using unverified small-usage allowances. At the upper reserve assumptions plus the full USD10 AI allowance, the total is **USD102.66 before tax or contingency**. Thus USD100 requires disciplined usage and a final backup quote; it is not assured by choosing this VM. Existing billed resources are additional unless the owner explicitly includes and reviews them in the same budget.

Standard SSDs charge transactions; the API's separate mount meters apply to [shared disks](https://learn.microsoft.com/en-us/azure/virtual-machines/disks-understand-billing), which these single-VM disks are not. [Bandwidth pricing](https://azure.microsoft.com/en-us/pricing/details/bandwidth/) lists the first100GB/month Internet egress free in North America; verify account aggregation before relying on it. Owner budget alerts at50/75/90/100 are useful, but [budgets do not stop consumption](https://learn.microsoft.com/en-us/azure/cost-management-billing/costs/tutorial-acm-create-budgets).

The [Basv2 specification](https://learn.microsoft.com/en-us/azure/virtual-machines/sizes/general-purpose/basv2-series) gives B2as_v2 a40% aggregate CPU baseline,48 credits/hour and no local temporary disk. Sustained OCR can consume credits and throttle. Keep OCR/liveAI off during initial target verification. A4GiB Windows VM leaves little headroom for Windows, PG and document processes;8GiB is the proposed minimum, not a measured guarantee. D2as_v5 Windows costs USD129.94/month compute alone in the receipt. Deallocation stops VM compute billing, but retained disks/IP still cost approximately USD18.05/month; stopping only the guest is not deallocation. Review actual billing and retained resources.

## Offline review and code package

From the project root:

```powershell
powershell.exe -NoProfile -ExecutionPolicy Bypass -File deployment/azure/Review-Plan.ps1
```

The reviewer verifies the compiler, rejects unknown/password-bearing parameters, requires six explicit nonsecret values, rejects public ingress, compiles locally and writes `.runtime/azure/reviewed-arm.json` and `closed-plan.json`. It checks an explicit private subnet and derives base cost from the saved public receipt. No Azure login, cloud validation, resource or DNS action occurs. `main.json` is compiled candidate evidence only. `parameters.example.json` leaves RDP and web closed. An eventual Windows owner password is a required secure parameter entered interactively; never put it in this file, a command/history, exported template, chat or application dummy-password field.

Pinned official compiler: [Bicep v0.49.2](https://github.com/Azure/bicep/releases/tag/v0.49.2), Windows x64 SHA256 `acfff0453c9bcf442aa97103acbcd845ef366634e6ea2a2ba5734514409ce9c3`, verified at `.runtime/tools/bicep-0.49.2.exe`. No automatic download. After a template edit, regenerate/review `main.json` from the compiler output before packaging.

After final source/build/test freeze, optional local packaging:

```powershell
powershell.exe -NoProfile -ExecutionPolicy Bypass -File deployment/azure/Review-Plan.ps1 -PackageCode
```

The exact application `release_hash()` allowlist produces a new timestamped ZIP and receipt under `.runtime/azure/packages`, with per-file SHA256/size, release hash and CRC checks. It rejects credential/runtime file types, unreviewed deployment files, symlinks/reparse points, outside paths and oversized assets. Static workflow workbooks are code assets. `.runtime`, `.env`, dumps, archives, DPAPI files, approvals, venvs, node_modules and proprietary Codex runtimes are excluded. No provider key/database is read. **An allowlist does not replace final synthetic-data/secret review**; inspect the manifest and refreeze hashes after any code/test/build/deployment-file change. The package remains local, with no transfer.

## Management tooling and authenticated read-only discovery

No system CLI/Az module or Azure connector was present initially. Microsoft's official `azure-cli==2.93.0` is now installed in a separate `.runtime/azure-tools` Python3.12 venv; version and dependency checks pass. It is not part of the application release. The official wheel is15.2MB before dependencies and requires Python>=3.10. [Microsoft's Windows guide](https://learn.microsoft.com/en-us/cli/azure/install-azure-cli-windows) also offers MSI/portable ZIP. Owner WAM/MFA authentication succeeded; no tenant security policy was changed. The earlier device flow was denied530035 and cancelled; sanitized request/correlation/timestamp facts are retained privately. Do not change the application venv or inspect/package token caches. Do not initialize first-use Cloud Shell storage, which can create resources.

For each isolated CLI shell, set `AZURE_CONFIG_DIR` to the absolute workspace `.runtime/azure-cli-profile`, `AZURE_CORE_COLLECT_TELEMETRY=0` and `AZURE_EXTENSION_USE_DYNAMIC_INSTALL=no`, then invoke `.runtime/azure-tools/Scripts/python.exe -m azure.cli` in place of `az`. This avoids the user's default profile. Authentication material remains private runtime data and is never part of a release package.

Read-only examples (use only the explicitly selected isolated CLI):

```powershell
az account show --query '{subscription:id,name:name,state:state,tenantId:tenantId}' --output json
az account list-locations --query "[?name=='eastus2'].{name:name,displayName:displayName}" --output json
az vm list-skus --location eastus2 --size Standard_B2as_v2 --all --output json
az vm list-usage --location eastus2 --output json
az resource list --subscription bd7d0da6-eaa6-45c5-b4fb-01edc19f9b1a --query '[].{name:name,type:type,resourceGroup:resourceGroup,location:location}' --output json
az provider show --namespace Microsoft.Compute --query registrationState --output tsv
az provider show --namespace Microsoft.Network --query registrationState --output tsv
```

No `get-access-token`, credential-list/reset, automatic provider registration, create or delete commands. Check2 regional and2 Basv2-family vCPUs plus offer restrictions; [regional and family quotas both apply](https://learn.microsoft.com/en-us/azure/azure-resource-manager/troubleshooting/error-resource-quota). A returned SKU can still have restrictions/capacity failure. Confirm role scope and quote in the actual subscription. Retain sanitized findings only.

A resource-group what-if needs an authorized existing group. **Do not create a group just to run what-if without approval.** Once a scope is authorized, review `az deployment group what-if`/Portal validation using the exact candidate and nonsecret parameters; its required secure password needs a verified non-echo owner input mechanism. No password logging. No create/deploy command is included. Review changes/costs before separate creation approval.

## Target layout and service proof

| Candidate path | Identity/access intent |
|---|---|
| `E:\Kestrel\app` | Owner-controlled release; app/proxy read/execute |
| `E:\Kestrel\app\.runtime` | Explicit precreated app-writable child; never overlaid by code ZIP |
| `E:\Kestrel\pgsql` | Dedicated PostgreSQL identity/data ACL |
| `E:\Kestrel\owner` | External owner config/approval/receipt; owner/SYSTEM write, app read; proxy reads token only |
| `E:\Kestrel\proxy` | Separate Caddy identity and private certificate/data ACL |
| Encrypted off-VM backup | Owner controlled; separately quoted and restore tested |

Verify actual drive letters, every ancestor's owner control, no app/proxy Write/DeleteChild and no junction/symlink substitution. File-only DACL checks do not prove a whole NTFS deployment. Preserve the explicit app-writable `.runtime` child: current adapters use it, so not all paths are externally configurable.

[USER DECISION] Technical and audit logs are retained permanently: **no automatic deletion, truncation or time-based pruning**. Rotation may close a bounded active segment, but must preserve every completed segment and its integrity/provenance. Keep protected, independently verified retained copies before moving anything off the VM. Monitor disk/DB capacity and backup growth, with owner alerts at reviewed thresholds (candidate80%/90%); capacity pressure requires a reviewed storage/cost action, not silent deletion or automatic paid resizing. Avoid source bodies/credentials in technical logs. Actual retention and rotation configuration remains target acceptance work, not an implemented infrastructure feature.

Install independently sourced/hash-reviewed target Python3.12 (local reference3.12.10), PostgreSQL18 (local18.6; verify compatible security minor), locked Python requirements and built frontend assets. Do not copy a workstation venv or Codex WindowsApps/Node/artifact-tool bundle. Native OCR and English/German models require target licensing/hash/function checks; no target OCR readiness is claimed.

The API entrypoint is `python -m kestrel.public_service`, one loopback process with proxy-header trust disabled. **It is not an SCM implementation.** `sc.exe create` around ordinary Python does not make a working Windows service. A real reviewed installer, persistent nonadmin profile, dependencies, explicit Manual startup/recovery policy and reboot test are missing. PG, Caddy and API need separately proved service identities. LOCAL `console_runner.py worker` is not a validated public worker: keep public OCR/liveAI/background processing off until a bounded authority-checked entrypoint and service lifecycle are accepted. Never proxy LOCAL publicly.

The separately reviewed [closed platform/proxy probe](qa/README.md) can gather bounded synthetic loopback-only identity/ACL/DPAPI and proxy prerequisites without starting app routes or writing an operational approval. The [static service-plan generator](services/README.md) produces only noninstallable review drafts, Manual/no automatic recovery/append logging, and no worker XML. Their48 self-tests pass with one real-target OS check skipped; offline Caddy adaptation succeeds. These are local preparation results, not actual Windows SCM, target TLS, database restore or application first-boot acceptance. They do not resolve the outstanding full-stack startup dependency.

## Data and secret migration

Copy reviewed code only first. Separately inventory synthetic DB rows, source/archive/report artifacts, schema head and retained records. Before an authorized export, quiesce writes/workers, verify source manifests/counts and retain a tested recovery point. PostgreSQL custom dumps are sensitive: use native file output rather than a PowerShell binary/text pipeline and an approved encrypted transfer container/channel. Never put plaintext dumps in code ZIPs/webroots. Rehearse restore to a new isolated DB, major/roles/extensions, schema/count/hash and authorization checks before cutover. This runbook exports/transfers nothing.

**CurrentUser DPAPI provider secrets, archives and encrypted local backups are not portable to another VM/account.** Provider keys must be privately re-entered under the new persistent app-service identity/profile, never plaintext-exported. A reviewed archive/backup source-decrypt/target-reencrypt transfer with provenance/content verification is not implemented. Full copy migration stays blocked until it exists and passes. An alternative needs explicit owner authorization for a new isolated synthetic fixture through approved tooling, labelled as new: never replay old approvals or claim copied history. Do not delete source records to simplify migration.

Root's fresh metadata-only backup inventory confirms **one source_archive**,17 source_versions,16 documents,17 source links and23 source findings. No archive plaintext was inspected. The17 raw sources are independently stored in `SourceVersion.data` and survive a verified whole-DB restore; the old protected archive is a separate custody/recovery obligation. `SourceArchive.protected_hash` pins the original ciphertext, `archive_store.get` verifies it, and migration0017 forbids archive-record UPDATE/DELETE. **Target DPAPI re-encryption changes that hash: never overwrite the old file/record or disable retention triggers.**

A full-custody transfer needs a separately reviewed **append-only verified storage binding**, adapter and security/restore tests, preserving the original archive record/digests and identifying a new target ciphertext hash and provenance. A protected owner-controlled append-only sidecar is a candidate, not an accepted shortcut or current feature; a later table design would need additive DDL review. Any binding must require the preserved original ciphertext hash, exact immutable lineage/manifest, fixed safe paths, new ciphertext hash, decrypted original content hash and every reconstructed source/unit check before success. The transport must authenticate identities, decrypt only in source-profile memory, verify the digest, encrypt to a new target-held transport key without plaintext files/shares, then verify/re-encrypt under the persistent target app profile into a new storage object. No such binding/exporter is implemented or approved. An owner may instead explicitly accept a limited target copy with the old archive unavailable on the VM and its original record/file retained locally; this is **not complete archive migration** and must be visible in custody/recovery acceptance. Independently test tampering, wrong-key/profile, path/replay mismatch, rollback and reboot access. Neither a DB dump, code ZIP nor generic DPAPI probe proves full archive portability.

## Exact hosts, DNS and public gate

| Host | Shell/audience |
|---|---|
| `portal.ramijaloudi.com` | Home; no organization granted |
| `firm.portal.ramijaloudi.com` | Firm |
| `halden.portal.ramijaloudi.com` | Halden |
| `castlegate.portal.ramijaloudi.com` | Castlegate |
| `admin.portal.ramijaloudi.com` | Firm admin shell; Root role still required |

After separate approval, exact records can point to the verified eventual static IPv4. No guessed IP, wildcard or unplanned AAAA. Review existing DNS/CAA/ACME first. Ordinary DNS resolution is the baseline: CDN/proxying changes socket-IP trust and requires another reviewed design. No DNS writes here.

`deployment/Caddyfile.public.example` is the previously offline-adapted Caddy2.11.9 example: exact hosts, incoming proxy/identity/secret headers stripped then private token/proto/socket-clientIP overwritten. Only Caddy has TLS ingress. API8000/PG5432/pgAdmin/diagnostics stay private. Unknown hosts/directIP fail; public Swagger needs genuine audience login. Host-only Secure/HttpOnly cookies and CSRF remain; hosts never grant roles, matter/wall/clean-team access or release. Optional RDP is owner IPv4/32 only. Subnet `defaultOutboundAccess:false` plus the NIC's explicit public IP gives outbound without paid NAT, per [Microsoft guidance](https://learn.microsoft.com/en-us/azure/virtual-network/ip-services/default-outbound-access).

PUBLIC_DEMO needs external owner files, separate owner/app/proxy SIDs, actual NTFS controls, matching host/config/release/test/receipt hashes and unexpired approval (max7days). No Web API creates approval. `python -m kestrel.public_inspection <external-config>` is read-only. See [docs78 exact protocol](../../docs/78_PUBLIC_DEMO_RUNTIME_GATE.md). No actual owner files are created here.

**First-boot protocol remains unresolved:** startup requires `all_required_passed:true`, including actual TLS proxy, Windows services and backup recovery, before PUBLIC can start; public_service refuses LOCAL. Naming a closed rehearsal does not resolve this dependency. A concrete independently reviewed closed acceptance/bootstrap protocol is required. Do not relax the guard, fabricate passes or expose LOCAL to work around it. SCM/reboot, first-boot acceptance, ancestor ACLs, target DPAPI restoration, real proxy/TLS and recovery remain blocking target evidence.

Actual final receipts must bind the frozen release and backend_full, public_boundary, postgres_restore, frontend_build, tls_proxy, windows_services, backup_recovery, owner_review. Exercise host/header/socket refusals, cookies/CSRF/audiences, walls/clean-team/bank default-off, uploads/throttling, reboot and recovery. Fixture passes are development evidence only. Keep `allowPublicWeb=false` until acceptance and explicit ingress authorization. Even bounded80/443 opening for ACME/TLS proof needs a reviewed protocol; none is assumed.

## Cutover and rollback

After those gates, owner reviews exact costs/resources/credentials/scope, authorizes closed infrastructure creation, verifies isolated services/data, then separately reviews DNS/TLS/public activation. Preserve the known-good local environment and source recovery point. Failed acceptance means leave web closed, stop target processing, retain sanitized diagnostics and use the verified source; never merge target writes back automatically.

Set an owner service/approval review date; check daily billed inventory and alerts. Later deallocate/remove only explicitly approved isolated resources after retention/backup review, preserving verified permanent technical/audit copies. Template disks/NIC detach on VM deletion; retained disks/IP can continue charging. No automatic teardown or log-pruning command. A public interview URL today is **not promised** while these blockers remain open.
