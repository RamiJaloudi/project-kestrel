# Sanitized Disclosures

Implemented model snapshot. This area owns 5 tables. Key-only parent tables provide cross-area context.

```mermaid
erDiagram
  accounts {
    string id PK
  }
  disclosure_artifacts {
    string plan_id FK
    string policy_id FK
    string created_by FK
    string id PK
    string matter_id FK
    string source_id FK
  }
  disclosure_decisions {
    string artifact_id FK
    string actor_id FK
    string id PK
    string matter_id FK
    string source_id FK
  }
  disclosure_plan_reviews {
    string plan_id FK
    string actor_id FK
    string id PK
    string matter_id FK
    string source_id FK
  }
  disclosure_plans {
    string created_by FK
    string id PK
    string matter_id FK
    string source_id FK
  }
  disclosure_validations {
    string artifact_id FK
    string id PK
    string matter_id FK
    string source_id FK
  }
  document_policy_versions {
    string id PK
  }
  matters {
    string id PK
  }
  source_versions {
    string id PK
  }
  disclosure_plans ||..o| disclosure_artifacts : "plan_id"
  document_policy_versions ||..o| disclosure_artifacts : "policy_id"
  accounts ||..o{ disclosure_artifacts : "created_by"
  matters ||..o{ disclosure_artifacts : "matter_id"
  source_versions ||..o{ disclosure_artifacts : "source_id"
  disclosure_artifacts ||..o{ disclosure_decisions : "artifact_id"
  accounts ||..o{ disclosure_decisions : "actor_id"
  matters ||..o{ disclosure_decisions : "matter_id"
  source_versions ||..o{ disclosure_decisions : "source_id"
  disclosure_plans ||..o| disclosure_plan_reviews : "plan_id"
  accounts ||..o{ disclosure_plan_reviews : "actor_id"
  matters ||..o{ disclosure_plan_reviews : "matter_id"
  source_versions ||..o{ disclosure_plan_reviews : "source_id"
  accounts ||..o{ disclosure_plans : "created_by"
  matters ||..o{ disclosure_plans : "matter_id"
  source_versions ||..o{ disclosure_plans : "source_id"
  disclosure_artifacts ||..o| disclosure_validations : "artifact_id"
  matters ||..o{ disclosure_validations : "matter_id"
  source_versions ||..o{ disclosure_validations : "source_id"
```

[Editable Mermaid](06_sanitized_disclosures.mmd) · [All data views](../README.md)
