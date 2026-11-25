param([Parameter(Mandatory=$true)][string]$EnvFile)
if (Test-Path -LiteralPath $EnvFile) {
    foreach ($line in Get-Content -LiteralPath $EnvFile) {
        $line=$line.Trim()
        if (-not $line -or $line.StartsWith('#')) { continue }
        $separator=$line.IndexOf('=')
        if ($separator -lt 1) { throw 'Invalid local .env entry' }
        $key=$line.Substring(0,$separator)
        if ($key -notmatch '^KESTREL_[A-Z0-9_]+$') { throw 'Invalid local .env entry' }
        $value=$line.Substring($separator+1).Trim()
        if ($value.StartsWith('"')) { $value=ConvertFrom-Json -InputObject $value }
        elseif ($value.StartsWith("'") -and $value.EndsWith("'")) { $value=$value.Substring(1,$value.Length-2) }
        if (-not [Environment]::GetEnvironmentVariable($key,'Process')) {
            [Environment]::SetEnvironmentVariable($key,$value,'Process')
        }
    }
}
