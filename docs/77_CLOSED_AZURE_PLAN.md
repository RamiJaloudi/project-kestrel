# 77 Closed Azure infrastructure proposal

[USER DECISION] Windows Server, local PostgreSQL, approximately $100/month target, interviewer HTTPS access and five owned `portal.ramijaloudi.com` hostnames. [DESIGN] East US 2 and Standard_B2as_v2,2 vCPU / 8 GiB, are the proposed small-demo region and SKU, subject to the subscription's actual permissions, quote, image support, quota and capacity.

[IMPLEMENTED PREPARATION] `deployment/azure/main.bicep` and compiled `main.json` describe the isolated VM, persistent disks, network and closed NSG. `Review-Plan.ps1` validates explicit nonsecret planning inputs and compiles locally using a SHA-256-pinned official compiler. It emits a local receipt with hashes, cost assumptions and pending gates. None of this authenticates to Azure, validates the template against Azure Resource Manager, provisions services or changes DNS.

Public web is closed by default. RDP is absent unless one exact owner IPv4 is supplied; the template appends `/32`. All remaining inbound traffic is denied, including database, pgAdmin and direct application ports. The owner password is a required secure template parameter and is absent from the example. No automatic installation extension receives any credentials. Disks are detached when the VM is removed; teardown and data disposal require a separate reviewed inventory.

The dated Microsoft retail subtotal is $79.66 for 730 hours: Windows compute $61.61,OS disk $9.60,data disk $4.80 and static IPv4 $3.65. This is an estimate, with only $20.34 allowance left against the target. Disk operations/mount applicability, encrypted off-VM backup, transfer, monitoring, taxes and paid AI need an actual quote and usage allowance. See [the saved official pricing receipt](evidence/66_azure_retail_prices_2026-11-24.json). Stopping/deallocating compute does not remove disk/IP charges.

The next deployment review must contain:

- The subscription/resource group, confirmed East US 2 quota/capacity and an actual itemized quote.
- The owner administration IPv4 and Windows credential entered securely by the owner.
- The exact reviewed application release and passing integrated/security evidence.
- Dedicated Windows service identities, profile-owned secrets, restricted ACLs, firewall/NSG checks and loopback-only PostgreSQL.
- An authorized backup-transfer method, isolated restore verification and new VM-owned provider secrets; workstation CurrentUser DPAPI files are not portable credentials.
- The independently owned public approval manifest, exact proxy boundary, DNS/TLS checks, reboot/recovery exercise and explicit public-launch approval.

[OPEN] These target operations and approval receipts are pending. The user's request to prepare a migration authorizes this local work; it does not mean resources already exist or that a public security gate has passed. The optional personal US demo must remain distinct from the real firm's approved EU enterprise architecture and first-wave delivery through existing tools.
