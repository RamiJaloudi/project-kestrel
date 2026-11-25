@echo off
setlocal
title Kestrel Stop - retain all records
set "KESTREL_ENV_FILE=%~dp0.env"
echo Stopping owned Kestrel API, redirector, worker, monitor, SQL console and PostgreSQL.
echo Documents, accounts, approvals, audits, logs and opaque DDR checkpoints are retained.
echo Excel workflow templates and your downloaded completion checklists are retained.
echo Review tasks and assignment history remain in PostgreSQL; browser table selections are temporary.
echo Finding assessment versions remain retained; stopping does not approve or release them.
echo Contract inventory filters and temporary selections never change retained source records.
echo Account metadata and profile revisions remain retained when the directory closes.
echo Scoped audit events and downloaded report manifests are retained; grid filters are temporary.
echo Registry decisions, assignment terms and wall records remain retained.
echo Interrupted provider attempts require reconciliation and are never automatically resent.
echo Browser tabs and pgAdmin remain open. Sign out separately to revoke remembered browser sessions.
powershell.exe -NoProfile -ExecutionPolicy Bypass -File "%~dp0scripts\local.ps1" stop
set "KESTREL_STOP_EXIT=%ERRORLEVEL%"
if not "%KESTREL_STOP_EXIT%"=="0" pause
exit /b %KESTREL_STOP_EXIT%
