param([Parameter(Mandatory=$true)][string]$ProjectRoot,[Parameter(Mandatory=$true)][string]$Python)
$ErrorActionPreference='Stop'
$pgAdminPaths=@(
    (Join-Path $env:ProgramFiles 'PostgreSQL\18\pgAdmin 4\runtime\pgAdmin4.exe'),
    (Join-Path $env:ProgramFiles 'pgAdmin 4\runtime\pgAdmin4.exe')
)
$pgAdmin=$pgAdminPaths | Where-Object { Test-Path -LiteralPath $_ } | Select-Object -First 1
if ($pgAdmin) {
    & $Python (Join-Path $ProjectRoot 'scripts\configure_pgadmin.py')
    if ($LASTEXITCODE -ne 0) { throw 'Project pgAdmin configuration failed.' }
    if (-not (Get-Process pgAdmin4 -ErrorAction SilentlyContinue)) {
        Start-Process -FilePath $pgAdmin -WindowStyle Normal
    }
    Write-Host 'pgAdmin 4 is open. Project server: 127.0.0.1:55432, database kestrel, username kestrel_local.'
} else { Write-Warning 'pgAdmin 4 was not found; PostgreSQL and psql still work.' }
$runtime=Join-Path $ProjectRoot '.runtime'
$stateFile=Join-Path $runtime 'sql-console.json'
$existing=$null
if (Test-Path -LiteralPath $stateFile) {
    $state=Get-Content -LiteralPath $stateFile -Raw | ConvertFrom-Json
    $process=Get-Process -Id $state.processId -ErrorAction SilentlyContinue
    if ($process -and $process.StartTime.ToUniversalTime().Ticks.ToString() -eq $state.startTicks) { $existing=$process }
}
if (-not $existing) {
    $runner=Join-Path $ProjectRoot 'scripts\database_console.py'
    $command='title Kestrel SQL - interactive project database operator & "'+$Python+'" "'+$runner+'"'
    $process=Start-Process -FilePath $env:ComSpec -ArgumentList @('/d','/k',$command) -WindowStyle Normal -PassThru
    @{processId=$process.Id;startTicks=$process.StartTime.ToUniversalTime().Ticks.ToString();executable=$process.Path;projectRoot=$ProjectRoot} | ConvertTo-Json | Set-Content -LiteralPath $stateFile
    Write-Host 'Opened project psql CMD console; password was not placed on the command line.'
} else { Write-Host 'Project psql console is already open.' }

