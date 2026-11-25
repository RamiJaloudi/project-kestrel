# Review Intelligence

Implemented model snapshot. This area owns 8 tables. Key-only parent tables provide cross-area context.

```mermaid
erDiagram
  accounts {
    string id PK
  }
  intelligence_alert_dispositions {
    string alert_id FK
    string actor_id FK
    string id PK
    string matter_id FK
    string source_id FK
  }
  intelligence_alert_reads {
    string alert_id FK
    string account_id FK
    string id PK
  }
  intelligence_alert_recipients {
    string alert_id FK
    string account_id FK
    string id PK
    string matter_id FK
    string source_id FK
  }
  intelligence_alerts {
    string profile_id FK
    string task_id FK
    string created_by FK
    string id PK
    string matter_id FK
    string source_id FK
  }
  intelligence_override_decisions {
    string override_id FK
    string actor_id FK
    string id PK
    string matter_id FK
    string source_id FK
  }
  intelligence_overrides {
    string profile_id FK
    string created_by FK
    string id PK
    string matter_id FK
    string source_id FK
  }
  intelligence_profile_decisions {
    string matter_id FK
    string profile_id FK
    string actor_id FK
    string id PK
  }
  intelligence_profiles {
    string matter_id FK
    string author_id FK
    string id PK
  }
  matters {
    string id PK
  }
  review_tasks {
    string id PK
  }
  source_versions {
    string id PK
  }
  intelligence_alerts ||..o{ intelligence_alert_dispositions : "alert_id"
  accounts ||..o{ intelligence_alert_dispositions : "actor_id"
  matters ||..o{ intelligence_alert_dispositions : "matter_id"
  source_versions ||..o{ intelligence_alert_dispositions : "source_id"
  intelligence_alerts ||..o{ intelligence_alert_reads : "alert_id"
  accounts ||..o{ intelligence_alert_reads : "account_id"
  intelligence_alerts ||..o{ intelligence_alert_recipients : "alert_id"
  accounts ||..o{ intelligence_alert_recipients : "account_id"
  matters ||..o{ intelligence_alert_recipients : "matter_id"
  source_versions ||..o{ intelligence_alert_recipients : "source_id"
  intelligence_profiles ||..o{ intelligence_alerts : "profile_id"
  review_tasks ||..o{ intelligence_alerts : "task_id"
  accounts ||..o{ intelligence_alerts : "created_by"
  matters ||..o{ intelligence_alerts : "matter_id"
  source_versions ||..o{ intelligence_alerts : "source_id"
  intelligence_overrides ||..o{ intelligence_override_decisions : "override_id"
  accounts ||..o{ intelligence_override_decisions : "actor_id"
  matters ||..o{ intelligence_override_decisions : "matter_id"
  source_versions ||..o{ intelligence_override_decisions : "source_id"
  intelligence_profiles ||..o{ intelligence_overrides : "profile_id"
  accounts ||..o{ intelligence_overrides : "created_by"
  matters ||..o{ intelligence_overrides : "matter_id"
  source_versions ||..o{ intelligence_overrides : "source_id"
  matters ||..o{ intelligence_profile_decisions : "matter_id"
  intelligence_profiles ||..o{ intelligence_profile_decisions : "profile_id"
  accounts ||..o{ intelligence_profile_decisions : "actor_id"
  matters ||..o{ intelligence_profiles : "matter_id"
  accounts ||..o{ intelligence_profiles : "author_id"
```

[Editable Mermaid](10_review_intelligence.mmd) · [All data views](../README.md)
