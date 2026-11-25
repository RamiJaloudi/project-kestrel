# Governance And Analysis

Implemented model snapshot. This area owns 13 tables. Key-only parent tables provide cross-area context.

```mermaid
erDiagram
  accounts {
    string id PK
  }
  ai_budget_periods {
    string period PK
  }
  ai_operations {
    string actor_id FK
    string matter_id FK
    string id PK
  }
  ai_reservations {
    string job_id PK, FK
    string period FK
  }
  analysis_jobs {
    string matter_id FK
    string playbook_id FK
    string requested_by FK
    string document_version_id FK
    string impact_task_id FK
    string id PK
  }
  governance_tasks {
    string impact_id FK
    string claimed_by FK
    string id PK
  }
  governance_versions {
    string matter_id FK
    string author_id FK
    string reviewer_id FK
    string base_playbook_id FK
    string id PK
  }
  impact_decisions {
    string task_id FK
    string actor_id FK
    string id PK
  }
  impact_publications {
    string target_id FK
    string base_id FK
    string id PK
  }
  impact_snapshots {
    string target_id FK
    string source_id FK
    string baseline_job_id FK
    string matter_id FK
    string id PK
  }
  matters {
    string id PK
  }
  operation_reservations {
    string operation_id PK, FK
    string period FK
  }
  processing_replacements {
    string old_id FK
    string new_id FK
    string proposed_by FK
    string approved_by FK
    string id PK
  }
  source_versions {
    string id PK
  }
  task_closures {
    string task_id FK
    string actor_id FK
    string id PK
  }
  task_notifications {
    string task_id FK
    string account_id FK
    string id PK
  }
  accounts ||..o{ ai_operations : "actor_id"
  matters ||..o{ ai_operations : "matter_id"
  analysis_jobs ||--o| ai_reservations : "job_id"
  ai_budget_periods ||..o{ ai_reservations : "period"
  matters ||..o{ analysis_jobs : "matter_id"
  governance_versions ||..o{ analysis_jobs : "playbook_id"
  accounts ||..o{ analysis_jobs : "requested_by"
  source_versions |o..o{ analysis_jobs : "document_version_id"
  governance_tasks |o..o{ analysis_jobs : "impact_task_id"
  impact_snapshots ||..o| governance_tasks : "impact_id"
  accounts |o..o{ governance_tasks : "claimed_by"
  matters ||..o{ governance_versions : "matter_id"
  accounts ||..o{ governance_versions : "author_id"
  accounts |o..o{ governance_versions : "reviewer_id"
  governance_versions |o..o{ governance_versions : "base_playbook_id"
  governance_tasks ||..o| impact_decisions : "task_id"
  accounts ||..o{ impact_decisions : "actor_id"
  governance_versions ||..o| impact_publications : "target_id"
  governance_versions ||..o{ impact_publications : "base_id"
  governance_versions ||..o{ impact_snapshots : "target_id"
  source_versions ||..o{ impact_snapshots : "source_id"
  analysis_jobs ||..o{ impact_snapshots : "baseline_job_id"
  matters ||..o{ impact_snapshots : "matter_id"
  ai_operations ||--o| operation_reservations : "operation_id"
  ai_budget_periods ||..o{ operation_reservations : "period"
  governance_versions ||..o| processing_replacements : "old_id"
  governance_versions ||..o{ processing_replacements : "new_id"
  accounts ||..o{ processing_replacements : "proposed_by"
  accounts |o..o{ processing_replacements : "approved_by"
  governance_tasks ||..o| task_closures : "task_id"
  accounts ||..o{ task_closures : "actor_id"
  governance_tasks ||..o{ task_notifications : "task_id"
  accounts ||..o{ task_notifications : "account_id"
```

[Editable Mermaid](15_governance_and_analysis.mmd) · [All data views](../README.md)
