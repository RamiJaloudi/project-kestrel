# 43 — Retained logs, source archives and database recovery

[IMPLEMENTED, LOCAL DEMO, 21 NOV 2026] No automatic deletion is configured for technical logs, governance/audit records, archives or backups.

## Audit reports

Audit supports JSONL, CSV, HTML and PDF ZIP exports with the same permission-filtered event selection and SHA-256 manifest. The manifest records filters, event IDs, exporting identity, timestamp, format and schema. Matter and optional time bounds narrow long histories to the 1,000-event export limit; they do not remove older events. PDF rendering rechecks the selected events and current access before return. Real 13-event and final 14-event PDFs were rendered and visually inspected, including readable UTC dates.

Clean-team audit selection resolves source, finding, release, job and grant object IDs back to their document policy before checking scope. Active named membership remains mandatory; wider timelines require the separately scoped auditor/antitrust role. Root has no clean-team override. Ordinary diagnostic logs contain sanitized exception types/frames and correlation IDs rather than prompts, keys or source passages.

## Source archive workflow

Signing & Retention includes **Protected local source archives** for cleared legal users. Creation reads authorized retained source versions, original bytes and extracted-unit JSON. It writes a new DPAPI-protected artifact, then decrypts and reconstructs every version to compare byte/text hashes. Verification is restricted to the creating user with continuing source clearance. Archive records have immutable database guards and no automatic deletion.

This is a Windows-account-bound local adapter. Append-only creation and integrity checks do **not** provide external WORM storage or portable long-term custody. Requests requiring WORM fail closed until that integration is configured. The live test reconstructed nine source versions; later fixture imports do not alter that point-in-time archive. Source archive verification is separate from database recovery.

## Actual PostgreSQL backup/restore check

Run from the project root with services/database started:

```powershell
.\backend\.venv\Scripts\python.exe scripts\verify_database_recovery.py --execute
```

The script:

1. Restricts itself to loopback PostgreSQL and exports a read-only repeatable snapshot of the `public` schema.
2. Captures a custom logical dump; secrets are passed to the PostgreSQL child process through its environment, never as printed command arguments.
3. Retains the backup encrypted with CurrentUser DPAPI under `.runtime/database-backups`. There is no plaintext dump file.
4. Creates a separately named scratch database with a validated generated identifier, decrypts the backup and restores **only into that scratch database**.
5. Compares every table's row count and sorted content digests, including original byte fields. It also compares views, functions, triggers, constraints and indexes.
6. Retains a verification manifest and removes only the generated scratch database. The active database is never restored over. Failed backups are retained; restricted restore stderr, if captured, is DPAPI-protected.

Observed successful run: **46 tables / 2,545 rows**, plus matching schema digests. Later application events and fixtures change row counts; each verification manifest records its own consistent snapshot. The initial scratch restore hit the existing `public` schema; clean/if-exists restore is now confined to the validated scratch database and the strengthened check passed.

Database recovery excludes `.runtime` provider configuration, certificates, OCR models, source archive files and application source/dependencies. Preserving a database dump alone is not full application recovery. DPAPI artifacts require the original Windows account/key context; Azure needs a separate portable secret/key and backup design. No external immutable-storage connection or disaster-recovery assurance is claimed.
