# 12 — Mock adapters, operational requirements and integration paths

## Replaceable ports with demo and firm target adapters
| Port | Synthetic candidate adapter | Hypothetical approved firm adapter |
|---|---|---|
| `VDRConnector` | manifest + batch folder loader; fake seller Q&A | provider export/API under deal rights |
| `DMSPort` | local versioned objects + DB metadata | iManage approved API |
| `EthicalWallProvider` | local wall rule registry | Intapp Walls approved API with cache/deny-on-outage |
| `CollaborationPort` | app comments/messages/uploads | approved M365/SharePoint/Teams guest workflows |
| `IdentityPort` | real demo accounts + server sessions | Entra ID + governed B2B, tenant policies |
| `OCRPort` | text-extraction; optional local Tesseract | approved Azure Document Intelligence EU region |
| `ModelPort` | deterministic fixtures; optional controlled API | approved Azure OpenAI/Vertex EU deployments |
| `SearchPort` | local SQLite keyword or FAISS sandbox | scalable Azure AI Search/index partitions |
| `QueuePort` | local background worker, durable table | Azure Service Bus with DLQ |
| `AuditPort` | append-only SQL events | governed tamper-evident logs/SIEM |

## API mocking guidance
Write abstract interfaces + typed payloads + contract tests; never claim mocked `iManage` or `Intapp` calls access their real systems. In demo, any JSON `source_system='mock_vdr'` must display that label. No need to purchase those products.

## Resilience
- Use idempotent ingest/process jobs, bounded retries w/ exponential backoff and jitter, dead-letter for persistent OCR/LLM failure, per-document observability, partial result status.
- Model timeout/circuit breaker/fallback to manual review; never silently switch to unapproved external model or region.
- Health, readiness, structured logging, token/OCR budgets, latency/cost dashboards, worker scaling, separate prod/sandbox accounts, secret manager, backups, migrations and rollback, automated tests, vulnerability scan.
- Production: queue workers for OCR/batch processing (not request thread), doc version hashes, model/provider/prompt/playbook version pinned per run, compare quality drift.
