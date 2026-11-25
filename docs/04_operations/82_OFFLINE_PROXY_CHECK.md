# 82 Offline reverse-proxy template verification

[IMPLEMENTED PREPARATION, 24 November 2026] The reviewed public Caddy example was adapted using the official Caddy 2.11.9 Windows x64 binary. Only `version` and `adapt` were executed. No listener, service installation, TLS certificate provisioning, DNS operation, owner approval or public activation occurred.

The [official release](https://github.com/caddyserver/caddy/releases/tag/v2.11.9) identifies the downloaded binary distribution. The Windows archive SHA-256 from official release metadata is `ad93112d335ee687100c4c9f11bced16ca590377976b7fe7883882b9e797e472`. It was checked before extraction into ignored `.runtime/tools/caddy-v2.11.9`. The extracted executable SHA-256 is `2622e239c79df700b0eb92cbd950d1edee365e155a7859f358f0e55f002df591`; the reusable checker refuses a different binary.

Run from the project root:

```powershell
backend\.venv\Scripts\python.exe scripts\check_proxy_template.py
```

The checker invokes only Caddy's offline configuration adapter, using an explicit nonsecret canary instead of any saved proxy token. It checks the five exact hosts, declared ports 80/443, disabled administration/persistence, strict SNI/Host matching, bounded headers/body, HTTP1/2 only, exact loopback upstream and stripped/overwritten private protocol. It prints a bounded review receipt and saves `.runtime/azure/proxy-review.json`. It does not load `.env`, a provider key or an owner approval.

The current Caddyfile emits a nonfatal formatting warning. Its syntax and the checked boundary declarations adapt successfully. [Caddy's command-line documentation](https://caddyserver.com/docs/command-line) distinguishes adaptation from the stronger module provisioning/validation step. This evidence does **not** establish actual Windows service ACLs, TLS, certificate issuance, edge header handling under a real connection, firewall rules, DNS ownership or Azure acceptance. Those remain the gates in [docs78](../03_security/78_PUBLIC_DEMO_RUNTIME_GATE.md).

The focused offline infrastructure checks passed **20 tests**: six actual-parser/boundary-drift cases, seven Azure-review input cases and seven local-supervisor cases. They include refusal of an unverified binary, changed administration, upstream, header rules and hostnames. These results overlap no reported application feature count and grant no deployment authority.
