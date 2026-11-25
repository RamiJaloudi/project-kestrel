@echo off
setlocal
title Kestrel Start - local services
set "KESTREL_ENV_FILE=%~dp0.env"
echo Starting Project Kestrel: HTTPS portals/API, PostgreSQL, redirector, worker and monitor.
echo The worker processes OCR, governed DDR and document-analysis jobs with visible activity pulses.
echo Portal Home and database tools open automatically. Use Portal Home for portals and grouped Swagger.
echo Resources provides role-specific Excel workflow scripts; startup verifies the retained workbook bundle.
echo Firm portal: Tasks ^& assignments provides authorized task filters, evidence, exports and reassignment.
echo Risk Review uses paged finding registers with exact-version review and export controls.
echo Diligence Trackers uses a contract/licence inventory grid with fresh source-review links.
echo Admin Accounts provides a paged directory and revision-checked name/employee ID editor.
echo Scoped audit grids and ZIP reports use the same applied window and searches.
echo Registry grids show matter assignments, effective walls and retained decision history.
echo Private settings use .env. Existing accounts, approvals, documents and logs are retained.
echo Live AI requires enabled provider settings, current policy/approvals and available budget; no automatic paid resend.
powershell.exe -NoProfile -ExecutionPolicy Bypass -File "%~dp0scripts\local.ps1" start
set "KESTREL_START_EXIT=%ERRORLEVEL%"
if not "%KESTREL_START_EXIT%"=="0" pause
exit /b %KESTREL_START_EXIT%
