param([ValidateSet('start','stop','status','account')][string]$Action = 'start', [switch]$NoOpen)
$ErrorActionPreference = 'Stop'
$projectRoot = [IO.Path]::GetFullPath((Join-Path $PSScriptRoot '..'))
$runtime = Join-Path $projectRoot '.runtime'
if (-not $env:KESTREL_ENV_FILE) { $env:KESTREL_ENV_FILE = Join-Path $projectRoot '.env' }
& (Join-Path $PSScriptRoot 'import_env.ps1') -EnvFile $env:KESTREL_ENV_FILE
$stateFile = Join-Path $runtime 'server.json'
$transcribing = $false
if ($Action -eq 'start') {
    $logDirectory = Join-Path $runtime 'logs'
    New-Item -ItemType Directory -Path $logDirectory -Force | Out-Null
    $launchLog = Join-Path $logDirectory ('startup-' + [DateTime]::UtcNow.ToString('yyyyMMdd-HHmmss') + '-' + [guid]::NewGuid().ToString('N') + '.txt')
    Start-Transcript -LiteralPath $launchLog | Out-Null
    $transcribing = $true
}
$python = Join-Path $projectRoot 'backend\.venv\Scripts\python.exe'
$port = 8443
$env:KESTREL_ENV = 'LOCAL'
if (-not $env:KESTREL_DATABASE_URL) {
    $databaseConfig = Join-Path $runtime 'database.json'
    if (Test-Path -LiteralPath $databaseConfig) {
        $env:KESTREL_DATABASE_URL = (Get-Content -LiteralPath $databaseConfig -Raw | ConvertFrom-Json).url
    }
}
$mutexKey = [Convert]::ToBase64String([Text.Encoding]::UTF8.GetBytes($projectRoot)).Replace('\','_').Replace('/','_')
$mutex = [Threading.Mutex]::new($false, ('Local\Kestrel-' + $mutexKey))
if (-not $mutex.WaitOne(0)) { throw 'Another Kestrel lifecycle command is running.' }

function Run-Checked([string]$Executable, [string[]]$Arguments) {
    & $Executable @Arguments
    if ($LASTEXITCODE -ne 0) { throw "Command failed: $Executable (exit $LASTEXITCODE)" }
}

function Open-AllSurfaces {
    if ($NoOpen) { return }
    Start-Process -FilePath 'https://localhost:8443/' -ErrorAction Stop
    & (Join-Path $PSScriptRoot 'database_apps.ps1') -ProjectRoot $projectRoot -Python $python
    Write-Host 'Opened Portal Home only. Portal, Swagger and Resources links open on demand in new tabs.'
}

function Seed-DocumentDemo {
    if ($env:KESTREL_SEED_DOCUMENT_DEMO -eq 'true') {
        Run-Checked $python @((Join-Path $PSScriptRoot 'seed_document_demo.py'))
        Run-Checked $python @((Join-Path $PSScriptRoot 'seed_board_demo.py'))
        Run-Checked $python @((Join-Path $PSScriptRoot 'prepare_ai_review_demo.py'))
        Run-Checked $python @((Join-Path $PSScriptRoot 'seed_wall_checker_lab.py'))
        Run-Checked $python @((Join-Path $PSScriptRoot 'seed_action_center_lab.py'))
        Run-Checked $python @((Join-Path $PSScriptRoot 'seed_tracker_lab.py'))
    }
}

function Get-OwnedProcess {
    if (-not (Test-Path -LiteralPath $stateFile)) {
        # Recover only exact project supervisor commands after a lost state file.
        # A port number or a process name alone never proves ownership.
        $supervisorPath = Join-Path $PSScriptRoot 'serve_local.py'
        $pattern = '(?:^|\s)"?' + [regex]::Escape($supervisorPath) + '"?\s*$'
        $candidates = @(Get-CimInstance Win32_Process -Filter "Name='python.exe'" -ErrorAction Stop | Where-Object { $_.CommandLine -match $pattern })
        $ids = @($candidates | ForEach-Object { $_.ProcessId })
        $roots = @($candidates | Where-Object { $_.ParentProcessId -notin $ids })
        if ($roots.Count -gt 1) { throw 'Multiple project supervisors found. Refusing ambiguous ownership.' }
        if ($roots.Count -eq 0) { return $null }
        $recovered = Get-Process -Id $roots[0].ProcessId -ErrorAction Stop
        if (-not $recovered.Path -or $recovered.Path -ne $roots[0].ExecutablePath) { throw 'Unable to verify project supervisor executable.' }
        @{processId=$recovered.Id;startTicks=$recovered.StartTime.ToUniversalTime().Ticks.ToString();projectRoot=$projectRoot;executable=$recovered.Path} | ConvertTo-Json | Set-Content -LiteralPath $stateFile
        Write-Host 'Recovered exact project supervisor ownership from its executable and script path.'
    }
    $state = Get-Content -LiteralPath $stateFile -Raw | ConvertFrom-Json
    $actual = Get-Process -Id $state.processId -ErrorAction SilentlyContinue
    if (-not $actual) { return $null }
    if ($actual.StartTime.ToUniversalTime().Ticks.ToString() -ne $state.startTicks -or
        $state.projectRoot -ne $projectRoot -or $actual.Path -ne $state.executable) {
        throw 'Recorded PID no longer matches this project. Refusing to stop an unrelated process.'
    }
    return $actual
}

try {
    $owned = Get-OwnedProcess
    if ($Action -eq 'stop') {
        if ($owned) { Run-Checked 'taskkill.exe' @('/PID',"$($owned.Id)",'/T','/F'); Write-Host 'Stopped Kestrel local server.' }
        else { Write-Host 'Kestrel is already stopped.' }
        if (Test-Path -LiteralPath $stateFile) { Remove-Item -LiteralPath $stateFile }
        $sqlStateFile=Join-Path $runtime 'sql-console.json'
        if (Test-Path -LiteralPath $sqlStateFile) {
            $sqlState=Get-Content -LiteralPath $sqlStateFile -Raw | ConvertFrom-Json
            $sqlProcess=Get-Process -Id $sqlState.processId -ErrorAction SilentlyContinue
            if ($sqlProcess -and $sqlState.projectRoot -eq $projectRoot -and
                $sqlProcess.StartTime.ToUniversalTime().Ticks.ToString() -eq $sqlState.startTicks -and
                $sqlProcess.Path -eq $sqlState.executable) {
                Run-Checked 'taskkill.exe' @('/PID',"$($sqlProcess.Id)",'/T','/F')
            }
            Remove-Item -LiteralPath $sqlStateFile
        }
        if (Test-Path -LiteralPath (Join-Path $runtime 'database.json')) {
            Run-Checked $python @((Join-Path $PSScriptRoot 'postgres_local.py'),'stop')
        }
        exit 0
    }
    if ($Action -eq 'status') {
        if ($owned) { Write-Host "Running PID $($owned.Id): https://localhost:8443/" } else { Write-Host 'Stopped' }
        exit 0
    }
    if (-not (Test-Path -LiteralPath $python)) {
        $candidates = @((Get-Command py.exe -ErrorAction SilentlyContinue).Source,
                       (Get-Command python.exe -All -ErrorAction SilentlyContinue | Where-Object Source -NotLike '*WindowsApps*' | Select-Object -ExpandProperty Source))
        $created = $false
        foreach ($candidate in $candidates) {
            if (-not $candidate) { continue }
            try {
                & $candidate -m venv (Join-Path $projectRoot 'backend\.venv')
                if ($LASTEXITCODE -eq 0) { $created = $true; break }
            } catch { continue }
        }
        if (-not $created) { throw 'Install Python 3.11+ and create backend\.venv; see backend\README.md.' }
    }
    if ($Action -eq 'account') {
        Push-Location (Join-Path $projectRoot 'backend')
        try {
            $operation = Read-Host 'Action: create, reset, or revoke'
            if ($operation -notin @('create','reset','revoke')) { throw 'Invalid action' }
            $username = Read-Host 'Username'
            $arguments = @('-m','kestrel.bootstrap',$operation,$username)
            if ($operation -eq 'create') {
                $org = Read-Host 'Organization: firm, halden, or castlegate'
                $roles = (Read-Host 'Roles separated by spaces (e.g. root_admin, firm_lawyer, legal_sme, client_user, bank_analyst)') -split ' '
                $arguments += @('--org',$org,'--roles') + $roles
                $email = Read-Host 'Email for integration checks (optional)'
                if ($email) { $arguments += @('--email',$email) }
            }
            Run-Checked $python $arguments
        } finally { Pop-Location }
        exit 0
    }
    Run-Checked $python @((Join-Path $PSScriptRoot 'verify_workflow_scripts.py'))
    if ($owned) {
        & $python (Join-Path $PSScriptRoot 'local_health.py')
        if ($LASTEXITCODE -eq 0) {
            Write-Host "Already running: opening Portal Home without duplicating services."
            Run-Checked $python @((Join-Path $PSScriptRoot 'prepare_demo_env.py'))
            & (Join-Path $PSScriptRoot 'import_env.ps1') -EnvFile $env:KESTREL_ENV_FILE
            Push-Location (Join-Path $projectRoot 'backend')
            try { Run-Checked $python @('-m','kestrel.interview_setup') } finally { Pop-Location }
            Push-Location (Join-Path $projectRoot 'backend')
            try { Run-Checked $python @('-m','kestrel.demo_setup') } finally { Pop-Location }
            Seed-DocumentDemo
            Open-AllSurfaces
            exit 0
        }
        Write-Warning 'Existing project is unhealthy. Start was explicitly requested: performing a manual project restart. Logs and database are retained.'
        Run-Checked 'taskkill.exe' @('/PID',"$($owned.Id)",'/T','/F')
        Remove-Item -LiteralPath $stateFile
    }
    if ([Net.NetworkInformation.IPGlobalProperties]::GetIPGlobalProperties().GetActiveTcpListeners() | Where-Object { $_.Port -in @(8000,8443) }) {
        throw "Port $port is occupied. No existing process was stopped."
    }
    New-Item -ItemType Directory -Path $runtime -Force | Out-Null
    Push-Location (Join-Path $projectRoot 'backend')
    try {
        if (-not (Test-Path -LiteralPath '.venv\Lib\site-packages\cryptography') -or
            -not (Test-Path -LiteralPath '.venv\Lib\site-packages\alembic') -or
            -not (Test-Path -LiteralPath '.venv\Lib\site-packages\psycopg') -or
            -not (Test-Path -LiteralPath '.venv\Lib\site-packages\pypdf') -or
            -not (Test-Path -LiteralPath '.venv\Lib\site-packages\openpyxl') -or
            -not (Test-Path -LiteralPath '.venv\Lib\site-packages\docx') -or
            -not (Test-Path -LiteralPath '.venv\Lib\site-packages\reportlab') -or
            -not (Test-Path -LiteralPath '.venv\Lib\site-packages\langchain_openai') -or
            -not (Test-Path -LiteralPath '.venv\Lib\site-packages\langgraph\checkpoint\sqlite')) {
            Run-Checked $python @('-m','pip','install','-r','requirements-tested.txt','-r','requirements-ddr.lock','-e','.[dev,postgres,ddr]')
        }
        $env:KESTREL_ENV = 'LOCAL'
        if (-not $env:KESTREL_DATABASE_URL -or (Test-Path -LiteralPath (Join-Path $runtime 'database.json'))) {
            Run-Checked $python @((Join-Path $PSScriptRoot 'postgres_local.py'),'start')
            if (-not $env:KESTREL_DATABASE_URL) {
                $env:KESTREL_DATABASE_URL = (Get-Content -LiteralPath (Join-Path $runtime 'database.json') -Raw | ConvertFrom-Json).url
            }
        }
        Run-Checked $python @('-m','alembic','upgrade','head')
        Run-Checked $python @((Join-Path $PSScriptRoot 'prepare_demo_env.py'))
        & (Join-Path $PSScriptRoot 'import_env.ps1') -EnvFile $env:KESTREL_ENV_FILE
        Run-Checked $python @('-m','kestrel.interview_setup')
        Run-Checked $python @('-m','kestrel.demo_setup')
        & (Join-Path $PSScriptRoot 'prepare_tracker_runtime.ps1')
    } finally { Pop-Location }
    Push-Location (Join-Path $projectRoot 'frontend')
    try {
        if (-not (Test-Path -LiteralPath 'node_modules\vite\bin\vite.js')) {
            Run-Checked 'npm.cmd' @('ci','--no-audit','--no-fund')
        }
        Run-Checked $python @((Join-Path $PSScriptRoot 'build_frontend.py'))
    } finally { Pop-Location }
    Run-Checked $python @((Join-Path $PSScriptRoot 'local_certificate.py'))
    $arguments = @(('"' + (Join-Path $PSScriptRoot 'serve_local.py') + '"'))
    $runId = [DateTime]::UtcNow.ToString('yyyyMMdd-HHmmss') + '-' + [guid]::NewGuid().ToString('N')
    $serverOutput = Join-Path $runtime ('logs\supervisor-' + $runId + '.out.log')
    $serverError = Join-Path $runtime ('logs\supervisor-' + $runId + '.err.log')
    $server = Start-Process -FilePath $python -ArgumentList $arguments -WorkingDirectory $projectRoot -WindowStyle Hidden -PassThru `
              -RedirectStandardOutput $serverOutput -RedirectStandardError $serverError
    @{processId=$server.Id; startTicks=$server.StartTime.ToUniversalTime().Ticks.ToString(); projectRoot=$projectRoot; executable=$server.Path; outputLog=$serverOutput; errorLog=$serverError} | ConvertTo-Json | Set-Content -LiteralPath $stateFile
    $healthy = $false
    for ($i=0; $i -lt 30; $i++) {
        & $python (Join-Path $PSScriptRoot 'local_health.py')
        if ($LASTEXITCODE -eq 0) { $healthy = $true; break }
        Start-Sleep -Milliseconds 500
        if ($server.HasExited) { break }
    }
    if (-not $healthy) {
        if (-not $server.HasExited) { Run-Checked 'taskkill.exe' @('/PID',"$($server.Id)",'/T','/F') }
        Remove-Item -LiteralPath $stateFile
        throw "Server did not become ready; inspect retained diagnostics: $serverError"
    }
    Write-Host "Portal Home: https://localhost:8443/"
    foreach ($hostName in @('admin.localhost','firm.localhost','client.localhost','bank.localhost')) {
        Write-Host "Portal: https://${hostName}:$port/portal    Swagger: https://${hostName}:$port/docs"
    }
    Write-Host 'Local HTTPS certificate trusted for the current Windows user. Use CREATE_ACCOUNT.bat for your own credentials.'
    Seed-DocumentDemo
    Open-AllSurfaces
} finally {
    $mutex.ReleaseMutex()
    $mutex.Dispose()
    if ($transcribing) { Stop-Transcript | Out-Null }
}









