# 66 Azure runtime portability and proposed Windows deployment

Updated 24 November 2026. [USER DECISION] The desired optional demo is interviewer access through browser HTTPS, Windows Server, and PostgreSQL on the same VM, approximately USD100/month all-in; DNS control is confirmed. [OBSERVED] Azure Portal Active/Owner and normal Windows WAM/MFA CLI login verify subscription **HudsonRiverAI-R+Demo_Portal** (`bd7d0da6-eaa6-45c5-b4fb-01edc19f9b1a`). East US2 B2as_v2 is NotAvailableForSubscription with Basv2 quota0/0; the original new-VM proposal is unavailable. Existing North Central US B2as_v2 Windows VM has a256GiB Standard SSD, Standard security, quota2/2, and was separately owner-authorized to start only for read-only assessment at18:30:30UTC/13:30:30EST. Its running base is USD84.46/month before snapshot/operations/backup/network/tax/AI, not the earlier new-VM subtotal. No resources, deployments or ingress rules were created. [OPEN] Guest/reuse readiness, actual image/patches, DNS/certificates, final RDP approval, custody/restore and public acceptance remain pending. See the [current concrete Azure runbook](../deployment/azure/README.md), which preserves service, DPAPI and first-boot blockers.

[IMPLEMENTED] This change removes hardcoded Codex runtime paths from the report, tracker, disclosure, audit and OCR adapters. It does **not** activate a public service, create cloud resources, copy data, change live approvals, or migrate the local database. `LOCAL` remains the default; the separately implemented `PUBLIC_DEMO` runtime refuses startup without the external owner/configuration/test-bound approval described in [document 78](78_PUBLIC_DEMO_RUNTIME_GATE.md). No such real approval was created. Portability checks are separate from the full acceptance/security gate and cannot authorize public deployment.

## Proposed VM and current retail cost

[DESIGN] Use one isolated Windows Server VM in **East US 2**, subject to subscription SKU availability and an actual quote. Start with **Standard_B2as_v2**, 2 vCPU and 8 GiB RAM, for a small synthetic interview workload. This is a candidate convenience deployment; the real-firm target remains its approved EU architecture and services. The Basv2 credit model throttles sustained CPU use after credits run out. Run one OCR job at a time, keep the ten-page OCR cap, and measure web responsiveness during an OCR job. This is not capacity for the brief's 400,000 pages. [Microsoft Basv2 specifications and credit model](https://learn.microsoft.com/en-us/azure/virtual-machines/sizes/general-purpose/basv2-series).

The following USD public PAYG rates were returned directly by Microsoft's unauthenticated Retail Prices API on 24 November 2026. VM rows explicitly selected **Windows** products, `Consumption`, and ordinary on-demand meters, excluding Spot, Low Priority, Dev/Test, reservations, Azure Hybrid Benefit and credits. Use 730 hours for a planning month. The [official API documentation](https://learn.microsoft.com/en-us/rest/api/cost-management/retail-prices/azure-retail-prices) explains the data and filtering; `scripts/get_azure_retail_estimate.ps1` repeats these read-only queries without Azure login. The saved [public pricing receipt](evidence/66_azure_retail_prices_2026-11-24.json) contains the filtered Microsoft results queried at 07:57 UTC, with source, region, rate units and monthly arithmetic.

[REFRESHED] The same official API was queried again at **17:56:22 UTC**. `.runtime/azure/retail-prices-2026-11-24-latest.json` records the unchanged rates below (SHA256 `6cccca45234ca74d130eed98b020ab418fc0b85a1614a5eda6dbbc8f0f366dc6`). The [current closed plan](../deployment/azure/README.md) separates USD79.66 base from USD2–5 unquoted small-backup allowance, USD0–3 disk operations and USD0–5 network/log reserve: USD81.66–92.66 before tax/paidAI, plus contingency. Those allowances are assumptions requiring a final quote, not verified prices or a cap. Shared-disk mount meters do not apply to these nonshared single-VM disks. [Microsoft disk billing](https://learn.microsoft.com/en-us/azure/virtual-machines/disks-understand-billing).

| Component | Verified retail rate | 730-hour planning cost |
|---|---:|---:|
| Standard_B2as_v2 Windows | $0.0844/hour | $61.61 |
| E10 LRS Standard SSD, 128 GiB OS disk | $9.60/month | $9.60 |
| E6 LRS Standard SSD, 64 GiB data disk | $4.80/month | $4.80 |
| Standard regional static public IPv4 | $0.005/hour | $3.65 |
| **Base subtotal** | | **$79.66/month** |
| Standard SSD disk operations | $0.002 per 10,000 operations | Usage-dependent |
| E10 and E6 separate Disk Mount meters returned by API | $0.91 and $0.47/month | Shared-disk meters; excluded for these single-VM disks |
| D2as_v5 Windows alternative, compute only | $0.178/hour | $129.94 |

[ASSUMPTION] Allow roughly **$85–100/month for a very small synthetic workload**, including a modest reserve for disk operations, small encrypted backups and limited transfer. This is an estimate, not a guaranteed all-in price. The exact disk-mount meter applicability, tax, backup destination/storage, DNS renewal, monitoring and outbound data charges must be checked before purchase. Paid AI tokens are additional usage; keep live AI disabled unless its measured allowance fits the total. The $20.34 difference between the base subtotal and $100 is the entire remaining allowance, not free OCR/model capacity. No paid Azure managed PostgreSQL, Azure Bastion, load balancer or other service is included. Disk provisioned size, snapshots and transactions affect billing. [Microsoft disk billing](https://learn.microsoft.com/en-us/azure/virtual-machines/disks-types), [managed disk tiers and prices](https://azure.microsoft.com/en-us/pricing/details/managed-disks/).

B2s Windows was $0.0496/hour ($36.21 compute), and B2ms Windows $0.0912/hour ($66.58). Do not choose them for a new deployment: Microsoft's Bv1 family documentation now marks the series End of Life. [Microsoft Bv1 lifecycle and sizes](https://learn.microsoft.com/en-us/azure/virtual-machines/sizes/general-purpose/bv1-series).

Before creation, confirm Windows image licensing is included in the selected PAYG product, the required image generation is supported, Basv2 vCPU quota and East US 2 capacity exist, and the displayed calculator quote matches the plan. Budget alerts at $50/$75/$90/$100 provide notice and do not impose a hard spending cap. Deallocate compute after the interview when appropriate; disks and reserved public IP can continue to incur charges. Teardown requires a reviewed inventory and explicit authorization to delete resources.

## Concrete Windows layout

```text
Internet browser
  -> exact owned DNS name -> static public IPv4
  -> TLS reverse proxy on TCP 443 (TCP 80 only for redirect/ACME)
     -> same-origin /api -> FastAPI 127.0.0.1:8000
     -> compiled React assets from the reviewed release
  -> API and bounded worker -> PostgreSQL 127.0.0.1:5432

C:\Kestrel\app\             reviewed source and frontend build
C:\Kestrel\app\backend\.venv\   independently installed public Python packages
C:\Kestrel\app\.runtime\    service-profile configuration and model manifest
C:\Kestrel\tools\           independently installed OCR tools and license notices
E:\Kestrel\postgres\        durable PostgreSQL data, never Azure temporary storage
E:\Kestrel\backups\         encrypted staging, restricted ACL; verified off-VM copy needed
E:\Kestrel\logs\            minimal metadata; rotate segments, retain all permanently
```

[DESIGN] The API and worker use a dedicated nonadministrator Windows identity/profile because CurrentUser DPAPI protects provider configuration and archives. PostgreSQL and proxy use separate identities. Apply least-privilege roles and narrow runtime ACLs, with an independent migration role. The latest static [service plan](../deployment/azure/services/README.md) proposes Manual start, no automatic restart/reboot and append-only log handling; actual target services/profile/dependencies/reboot behavior are unverified. It supersedes the earlier automatic-restart suggestion. After reboot, verify the stopped state and separately authorized manual startup; no unattended recovery claim is made.

[USER DECISION / TARGET NOT VERIFIED] Technical/audit logs are retained permanently. Rotation can bound the active segment but must not automatically delete/truncate old segments or prune by age. Protected retained copies, capacity/budget monitoring and an explicit owner storage action are required as data grows. No indefinite USD100 cost guarantee follows from the initial small-workload estimate. See the current Azure runbook for the retention/capacity acceptance requirement.

Allow inbound 443 and, if ACME requires it, 80. Permit RDP 3389 only from the owner's explicitly supplied fixed IP, preferably enable it only for maintenance. No inbound PostgreSQL 5432, pgAdmin, application/worker ports, Caddy admin port or Windows file shares. PostgreSQL `listen_addresses` and `pg_hba.conf` restrict to loopback with SCRAM credentials. Windows Firewall and the Azure NSG must both be checked. Restrict outbound services to the reviewed destinations where operationally practical. Keep patches, time synchronization, malware protection and disk free-space alerts enabled.

### TLS and exact host mapping

[DESIGN] Caddy is a simple Windows-capable TLS/reverse-proxy candidate. Its automatic HTTPS needs valid DNS control and reachable ACME validation; localhost trust is not browser-trusted interviewer HTTPS. [Caddy automatic HTTPS](https://caddyserver.com/docs/automatic-https), [reverse proxy behavior](https://caddyserver.com/docs/caddyfile/directives/reverse_proxy).

The user confirmed these exact intended names. This records the approved naming plan; it does not assert that DNS, certificates or services have been configured:

| Confirmed hostname | Organization shell | Backend organization |
|---|---|---|
| `portal.ramijaloudi.com` | Public entry and portal selection | No content authorization |
| `firm.portal.ramijaloudi.com` | Firm | `firm` |
| `halden.portal.ramijaloudi.com` | Halden | `halden` |
| `castlegate.portal.ramijaloudi.com` | Castlegate | `castlegate` |
| `admin.portal.ramijaloudi.com` | Administration shell | `firm`, with existing scoped administrative role checks |

Configure these exact hosts consistently in DNS, TLS, proxy host matching, frontend shell selection, backend allowlist, organization checks, CSRF origin checks and generated links. The public home displays no protected counts/content, and the admin shell does not introduce another organization, legal approval power or access to walled content. Reject unknown hosts and direct-IP requests. Preserve the original exact Host when proxying. Trust forwarded HTTPS/client-IP headers only from the loopback proxy and strip client-supplied forwarding headers at the edge. Do not enable wildcard proxy trust or accept an unverified arbitrary `Host` header. Test malicious `X-Forwarded-Host`, `Forwarded`, host suffixes and case/port normalization.

All three shells use a same-origin API. Authentication cookies remain host-only, `Secure`, `HttpOnly` and appropriately `SameSite`, with CSRF checks on state-changing requests. Never set a wildcard cookie Domain or permissive CORS. A host selects the shell; it never grants a role, matter assignment, wall clearance or clean-team access. A client account on the firm hostname must remain denied.

Block anonymous `/swagger`, `/docs`, `/redoc`, `/openapi.json`, admin/diagnostic paths and their subpaths at the public edge; retain any approved internal tooling behind authentication and owner restrictions. Prefer blocking public Swagger entirely for this interview deployment. Enforce request-body and connection bounds. **Core Caddy does not by itself implement the required per-IP application rate-limiting policy.** A reviewed edge throttling implementation plus the application's login/session controls must pass abuse tests before public mode is considered. No third-party Caddy module has been installed or approved in this change.

[IMPLEMENTED / TARGET NOT VERIFIED] The subsequently implemented PUBLIC_DEMO host mapping, trusted proxy protocol, application request/login bounds, exact generated links and external owner approval gate are described in [document78](78_PUBLIC_DEMO_RUNTIME_GATE.md). This supersedes the earlier hardening-open status above; it does not prove real target TLS, service startup, ancestor ACLs, restore or public activation. The latest [Azure runbook](../deployment/azure/README.md) records those operational blockers, including the unresolved first-boot acceptance dependency. Never proxy LOCAL publicly or fabricate a pass receipt to start PUBLIC_DEMO.

## Portable report and tracker runtime

[IMPLEMENTED] `report_export`, `tracker_workbooks`, `disclosure` and `audit_pdf` use `kestrel.adapters.runtime` to select `sys.executable` by default. A deployment must create its own Python 3.11+ virtual environment and install `backend/pyproject.toml`. Reports now use public **python-docx, openpyxl and ReportLab**; ReportLab is explicitly declared. There is no application XLSX dependence on Node or `@oai/artifact-tool`. The old `.mjs` commands are compatibility shims to the Python workers, and `prepare_tracker_runtime.ps1` only checks Python/openpyxl; it creates no machine-specific junction.

The application does not copy Codex executables/packages or redistribute proprietary artifacts into the deployment. Any bundled tools used for local visual QA are a local authoring convenience, not a deployment dependency. [ReportLab's primary licensing statement](https://docs.reportlab.com/developerfaqs/) identifies its open-source toolkit as BSD. PDF generation uses its bundled Bitstream Vera fonts rather than `C:/Windows/Fonts/arial.ttf`; retain the installed package's `fonts/bitstream-vera-license.txt` and notices. Optional administrator-supplied fonts require their own appropriate rights and Unicode coverage. The Word document specifies a normal font family and allows a viewer fallback; it does not copy Windows font files.

XLSX strings are explicitly stored as string cells, including leading `=`, `+`, `-`, `@`, tabs and line breaks. No formulas are evaluated or generated. Identifiers stay text, revisions stay numeric, valid DueOn dates stay sortable dates, invalid proposal dates remain visible for existing server validation, editable columns remain amber and freeze panes remain. All created sheets are visible. Existing workbook payloads are rejected by the authoring worker; actual imports continue through the tracker service's macro/link/formula/hidden-sheet/hidden-row/hidden-column checks. The importer retains preview, human selected-row attestation, revision checks and independent audience release. The bounded worker has a 45-second timeout, a 2 MiB request cap and 3 MiB XLSX output cap. Report output remains capped at 20 MiB, and disclosure output at 3 MiB.

The optional tracker-lab preview is a bounded Pillow raster preview of the first six rows. It is not an Excel rendering engine. Actual saved XLSX files were independently imported and rendered with the local bundled spreadsheet renderer for visual QA; that renderer is not shipped or required on Azure.

### Configuration and read-only preflight

Use administrator-only environment variables or `.runtime/portable-runtime.json`. Environment variables take precedence. `scripts/portable-runtime.example.json` shows the proposed target folder layout; copy/edit it only after installing the corresponding tools. It contains no secrets.

| Environment variable | Purpose/default |
|---|---|
| `KESTREL_REPORT_PYTHON` | Report/workbook Python executable; default running application's Python |
| `KESTREL_PDF_FONT`, `KESTREL_PDF_FONT_BOLD` | Optional licensed Unicode TrueType font files; default ReportLab Vera |
| `KESTREL_OCR_ENGINE` | `native`, `tesseract-js` or `auto`; auto tries native first |
| `KESTREL_TESSERACT` | Native executable; default `tesseract` on PATH |
| `KESTREL_PDFTOPPM` | Independently installed renderer; default `pdftoppm` on PATH |
| `KESTREL_OCR_MODELS` | Pinned model directory; default project `.runtime/ocr-models` |
| `KESTREL_OCR_NODE`, `KESTREL_OCR_NODE_MODULES` | Optional independently installed JS OCR fallback |

Runtime JSON keys are the lowercase suffixes, for example `report_python` and `pdftoppm`; PDF font overrides are environment variables. The optional local JS OCR path can still read the old tracker runtime configuration for compatibility, but report/XLSX generation cannot depend on it. Do not move that machine-specific JSON or its junction to the VM. Configure `native` explicitly on the VM to avoid an unintended fallback.

From the project root, these checks do not read provider keys, connect to PostgreSQL or contact Azure:

```powershell
& backend/.venv/Scripts/python.exe scripts/check_portable_runtime.py
& backend/.venv/Scripts/python.exe scripts/check_portable_runtime.py --require-native
```

The first succeeds on this workstation using the existing local Tesseract.js baseline. The second currently fails as expected because native Tesseract is not installed. An Azure CLI presence flag is informational only; it does not authenticate or confirm subscription readiness.

## OCR installation and evidence contract

[IMPLEMENTED] The native path supports a verified **Tesseract 5** executable, Poppler `pdftoppm`, English/German LSTM models, TSV words, confidence and image coordinates. The engine/version and immutable model commit remain attached to the extraction provenance. The existing local **Tesseract.js 7.0.0** path remains available; its exact package version is checked. No OCR installation is claimed for the VM. [Tesseract installation and Apache 2.0 licensing](https://github.com/tesseract-ocr/tessdoc/blob/main/Installation.md), [upstream command-line and TSV documentation](https://github.com/tesseract-ocr/tessdoc/blob/main/Command-Line-Usage.md).

Use an independently sourced Windows Tesseract package after reviewing its upstream installation guidance, provenance, exact executable/DLL versions, hashes and license notices. Download neither executables nor models during document processing. Poppler is an external configurable tool, **not a newly bundled permissive renderer**. Its upstream source/license and the chosen Windows package's provenance/distribution terms must be reviewed before packaging; no Codex-bundled Poppler binary is authorized for copying. The upstream site lists signed source releases and identifies third-party Windows builds as unofficial. [Poppler upstream release and source](https://poppler.freedesktop.org/), [upstream source repository](https://gitlab.freedesktop.org/poppler/poppler). No claim is made that Poppler is permissively licensed or that its binary redistribution review has passed.

Model commit: `87416418657359cb625c412a48b6e1d6d41c29bd` from `tesseract-ocr/tessdata_fast`. The adapter checks both the manifest and these compiled expected SHA-256 values, so substituting another manifest cannot approve another model:

| Model | SHA-256 |
|---|---|
| eng | `7d4322bd2a7749724879683fc3912cb542f19906c83bcc1a52132556427170b2` |
| deu | `19d219bbb6672c869d20a9636c6816a81eb9a71796cb93ebe0cb1530e2cdb22d` |

Retain [the model repository's Apache 2.0 license](https://github.com/tesseract-ocr/tessdata_fast/blob/main/LICENSE). Preserve model files and manifest under restricted write ACLs, with no runtime fetches. Each document remains capped at 3 MiB and ten OCR pages; each raster is bounded to 2,200 pixels on its longest side, renderer timeout 15 seconds/page, OCR timeout 25 seconds/page, text total bounded by the existing extraction limit. Native Tesseract uses `OMP_THREAD_LIMIT=1`. Tool errors do not expose stderr or document passages. A hash mismatch, missing tool or timeout fails closed with an unavailable result, not fabricated OCR text.

OCR still creates a new immutable source version. Its status requires the existing **human comparison against the original image and explicit verification** before classification confirmation/review/release. Native and JS output may differ; do not rewrite historical OCR or evidence offsets. Re-run representative English and German scans on the actual target and verify word boxes against the rendered pages before enabling that engine there. A mocked native argv test does not substitute for this acceptance step.

Tesseract recognizes text in images. It cannot provision Azure. Codex can prepare scripts, while Azure Portal, Azure CLI or another authorized management interface creates resources only after authentication, permissions, acceptance gates and explicit approval. Azure CLI2.93.0 is now installed in an isolated workspace venv (`.runtime/azure-tools`), with version/dependency checks passing and a separate workspace profile; owner device authentication is pending. This is tooling evidence only, not deployment evidence.

## PostgreSQL and DPAPI migration plan

[OPEN] **Do not begin migration while any required application acceptance gate remains open.** Complete the full feature/security matrix, migration rehearsal, restore evidence and a reviewed final transfer plan first. The steps below are a design, not an executed migration.

1. Inventory the final Alembic head, PostgreSQL major version/extensions, database size, object counts and document/archive hashes without logging secret values or document passages. Keep the reviewed application revision and dependency versions with the inventory. Stop or quiesce writers and workers at an approved cutover point; preserve approvals and immutable history.
2. Use a compatible PostgreSQL `pg_dump` custom-format logical export, including the reviewed schema/data. A custom-format dump is **not encryption**. Stream through a verified binary-safe encryptor or use an ACL-restricted encrypted staging volume and a reviewed encryption procedure; do not write unencrypted database backups or print credentials. Use secure local credential handling, never a password-bearing command line. Do not assume Windows PowerShell text pipes safely preserve binary dump bytes. [PostgreSQL pg_dump](https://www.postgresql.org/docs/current/app-pgdump.html).
3. Restore only into a fresh isolated target database using `pg_restore --exit-on-error`, preferably one transaction for this small demo where compatible. Use explicit target roles/ownership and `--no-owner --no-acl` where the reviewed role plan requires it. Never use `--clean` against the existing live database. Validate the table inventory, row counts, foreign keys, immutable triggers/views, Alembic head, policy-denial matrix and source/evidence bytes/hash integrity. [PostgreSQL pg_restore](https://www.postgresql.org/docs/current/app-pgrestore.html).
4. Treat local DPAPI files as a distinct migration problem. `provider_secrets.py` encrypts under **Windows CurrentUser**. A provider JSON copied from the workstation usually cannot decrypt under the VM service profile. Leave live AI disabled initially and re-enter the provider credential through the existing write-only configuration workflow under the target service identity. Never export plaintext keys or log them. [Microsoft CurrentUser DPAPI behavior](https://learn.microsoft.com/en-us/windows/win32/api/dpapi/nf-dpapi-cryptprotectdata).
5. `.runtime/archives/*.dpapi` and DPAPI-encrypted backup packages likewise cannot simply be copied and called restored. Each archive needs an authorized source-profile read, integrity verification, a reviewed encrypted transfer and target-profile re-encryption. Re-encryption changes ciphertext/protected hashes, so the design must preserve original immutable records and append appropriate new archive/migration provenance rather than silently rewriting hashes. This adapter workflow is **not implemented here**. Alternatively initialize a new isolated synthetic demo with deliberately selected fixtures, after the user approves the exact retained state; do not replay approvals or manufacture lawyer decisions.
6. Revoke inherited workstation browser sessions for the target using an approved workflow and provision unique interviewer accounts securely. Verify negative access on each exact host before cutover. Keep the original environment intact and inaccessible from the internet until a restored target and encrypted backup restore test pass. A failed restore or policy check means rollback to the intact local environment, not relaxing authorization.

No DPAPI key material, database dump or archive has been inspected/exported by this portability task. The source code of the protection adapters was audited only to identify the portability restriction.

## Validation actually completed and remaining gates

[IMPLEMENTED / VERIFIED]

- New pure runtime/export/OCR-boundary suite: **20 passed** in 6.50 seconds. Covers PDF/Word/XLSX, literal formula-like strings, visible sheets, typed dates, invalid shape/path rejection, subprocess timeout/output bounds, missing executable denial, disclosure physical-content validation, audit PDF and fixed-model/native command contracts.
- Existing tracker, report, AI/OCR and disclosure integration suites: **20 passed** in 45.35 seconds using isolated test fixtures after migration 0034 became stable. No live database migration/restart was performed by this task.
- Real local scan smoke: one synthetic PDF page, **63 recognized words**, extractor `ocr:tesseract.js-7.0.0;874164186573`. This verifies local fallback behavior only.
- Generated synthetic report PDF rendered with Poppler and visually checked; Word rendered with the prescribed `render_docx.py` and installed LibreOffice and visually checked; report annex and tracker XLSX files reopened with openpyxl and independently rendered for every sheet. English/German glyphs, wrapping, headers and literal `=HYPERLINK(...)` text were checked. QA artifacts stay under `.runtime/portability-qa`/`outputs/tracker-previews`; they are not real matter data or final submission deliverables.
- Historical portability preflight passed local report packages/current JS OCR; `--require-native` correctly failed because native OCR was absent. At that earlier run, system Azure CLI presence was false. The newly isolated CLI2.93.0 version and dependency check now pass; this does not prove target OCR or Azure resource readiness.

[OPEN / NOT VERIFIED]

- All other application completion gates belong to the main acceptance record; these 40 focused passing tests do not replace it.
- A clean independently provisioned Windows Server runtime, signed/provenance-reviewed OCR dependencies, actual native English/German OCR/coordinates and reboot/service tests.
- DNS records for the confirmed names, certificate issuance/renewal, host/link/proxy/rate-limit hardening, unknown-host/direct-IP denial and account/cookie/CSRF negative tests at the edge.
- Portal Active/Owner and CLI WAM/MFA login are verified. Read-only inventory proves East US2 new B2as_v2 is blocked (family quota0/0, subscription restriction); North Central US existing B2as_v2 uses2/2 family quota. Existing VM's owner-authorized read-only assessment is active; guest readiness/reuse authorization and complete target acceptance remain open, with final costs/retention/backup destination unverified.
- DPAPI archive portability workflow, logical export/restore rehearsal on the target, source/archive hash reconciliation and service-profile secret re-entry. One retained SourceArchive exists; its original ciphertext hash is immutable and migration0017 prevents UPDATE/DELETE. Target re-encryption requires a reviewed append-only storage-binding design/adapter/tests, never overwriting that retained record or disabling triggers. The17 raw SourceVersion.data rows independently survive a verified DB restore; this does not migrate the old archive's custody. Existing local DPAPI backups are not portable recovery evidence. See the current runbook for the explicit limited-copy alternative and open acceptance decision.
- Full final acceptance/security/dependency scan, synthetic-only verification, actual target Windows SCM/reboot/NTFS/TLS/restore evidence, safe first-boot protocol and public deployment consent. PUBLIC_DEMO implementation exists under document78, but remains closed without actual external owner approvals; no target approval file has been created.

No public readiness, production capacity, legal accuracy, paid Azure service connectivity or budget guarantee is asserted.
