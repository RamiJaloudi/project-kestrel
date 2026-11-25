# Lifecycle And Audit

Implemented model snapshot. This area owns 4 tables. Key-only parent tables provide cross-area context.

```mermaid
erDiagram
  accounts {
    string id PK
  }
  audit_events {
    string matter_id FK
    string id PK
  }
  lifecycle_decisions {
    string matter_id FK
    string proposed_by FK
    string approved_by FK
    string id PK
  }
  matter_lifecycle {
    string matter_id PK, FK
  }
  matters {
    string id PK
  }
  source_archives {
    string matter_id FK
    string created_by FK
    string id PK
  }
  matters |o..o{ audit_events : "matter_id"
  matters ||..o{ lifecycle_decisions : "matter_id"
  accounts ||..o{ lifecycle_decisions : "proposed_by"
  accounts |o..o{ lifecycle_decisions : "approved_by"
  matters ||--o| matter_lifecycle : "matter_id"
  matters ||..o{ source_archives : "matter_id"
  accounts ||..o{ source_archives : "created_by"
```

[Editable Mermaid](17_lifecycle_and_audit.mmd) · [All data views](../README.md)
