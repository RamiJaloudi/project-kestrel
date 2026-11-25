TECH STACK AND SCHEMA EXPLANATIONS
24 November 2026

Tech_Stack_and_Linux_Portability.csv: major application, security, document,
runtime and deployment components; versions, purpose, rationale and Linux work.
Current_status distinguishes inspected code, user-stated environment, plans
and recommended replacements. No actual VM credentials/configuration were read.

Schema_Fields_Story_and_Linux_Portability.csv: all 809 rows and all 16 original
explained-dictionary columns, plus story_stage, field_family, why_it_exists,
linux_portability and linux_action. These are documentation columns, not DDL.

Schema_CSV_Column_Guide.csv: all 21 dictionary headers explained.
Tech_Stack_and_Schema_Guide.docx: concise narrative and map to the detailed CSV.

All CSVs use UTF-8 with BOM and CRLF for Excel on Windows. Component portability
is a source-based engineering assessment, not Linux acceptance or a migration.
Windows-only public approval checks, DPAPI keys/archives and launch scripts need
reviewed replacements. Copying the database is not full application migration.
