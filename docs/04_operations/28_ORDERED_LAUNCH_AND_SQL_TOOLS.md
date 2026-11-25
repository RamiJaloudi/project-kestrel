# Ordered tabs and database applications

The earlier 25 targets included four design previews and the full shared Swagger schema repeated on all four portal hosts. They were alternate UI/documentation views, not 25 applications or duplicate API processes. This launch behavior supersedes docs/27's inventory.

Start now opens a dedicated Chrome/Edge window with an ordered argument list:
1. Administration portal.
2. Firm portal.
3. Halden portal.
4. Castlegate portal.
5. Shared Swagger overview.
6. All 12 filtered API Swagger groups, following the overview to the right.

Total: 17 distinct URLs. Portal tabs are adjacent; Swagger tabs form the right-hand block. These are ordered blocks, not claims of named/color-coded native browser tab groups. Existing windows/tabs are not closed or modified. Each Start opens the ordered set again as requested; previously opened browser windows can still contain older tabs. The full Swagger schemas on each host and the design previews remain accessible via links, but are not redundantly opened at startup. If neither Chrome nor Edge is found, fallback uses the default URL handler and warns that order is not guaranteed.

## Database tools

PostgreSQL was already started by the launcher as a background engine. Its desktop/console tools were not previously launched. Start now also opens:
- Installed pgAdmin 4 (existing process reused). First-time registration/connection in pgAdmin may still be needed. Server: 127.0.0.1, port 55432, maintenance DB kestrel, username kestrel_local. No password is printed or inserted into browser URLs.
- A visible project psql CMD operator console connected to that dedicated database. The connection password is passed only in its child process environment, not command arguments, transcripts or repository. An existing recorded operator console is not duplicated.

Stop closes only the recorded operator console after PID/start time/executable/project checks, then stops the project database and backends. pgAdmin remains open because it can contain unrelated server connections or unsaved user queries; it is not blindly killed. No existing SQL Server or PostgreSQL Windows services are reconfigured.

## Verification

PowerShell parser check passed. All 17 URL targets are unique and returned 200 with correct local Host routing. Their inventory puts all four portals before any Swagger target. Executing START_KESTREL.bat launched the ordered browser batch and database tools. Process inspection confirmed pgAdmin4 and psql; pg_stat_activity confirmed one connection with the project's operator-console application name. The first immediate process query ran before psql finished opening; a subsequent database-side check verified its successful connection. No credentials or application document records were read into tool output.
