$ErrorActionPreference='Stop'
$projectRoot=Split-Path -Parent $PSScriptRoot
$python=if ($env:KESTREL_REPORT_PYTHON) { $env:KESTREL_REPORT_PYTHON } else { Join-Path $projectRoot 'backend\.venv\Scripts\python.exe' }
if (-not (Test-Path -LiteralPath $python)) { Write-Host 'Portable Python environment unavailable; workbook routes will report unavailable.'; exit 0 }
& $python -c "import openpyxl; print('Portable XLSX engine available; no credentials loaded.')"
if ($LASTEXITCODE -ne 0) { throw 'Install backend project dependencies into the configured Python environment.' }
