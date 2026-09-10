# Run interactively once. Windows DPAPI protects the saved password for this user.
[CmdletBinding()]
param(
    [string]$DatabaseName = 'Yahuoku_analyze_DB',
    [string]$DatabaseHost = 'localhost',
    [ValidateRange(1, 65535)][int]$DatabasePort = 5432
)
$ErrorActionPreference = 'Stop'
$projectRoot = Split-Path -Parent $PSScriptRoot
$credential = Get-Credential -Message 'Systema PostgreSQL user and password'
if ($null -eq $credential -or [string]::IsNullOrWhiteSpace($credential.UserName) -or $credential.Password.Length -eq 0) {
    throw 'Database user and password are required. Nothing was saved.'
}
if ([string]::IsNullOrWhiteSpace($DatabaseName) -or [string]::IsNullOrWhiteSpace($DatabaseHost)) {
    throw 'Database name and host are required. Nothing was saved.'
}
$localDirectory = Join-Path $projectRoot '.local'
New-Item -ItemType Directory -Path $localDirectory -Force | Out-Null
[pscustomobject]@{
    DatabaseName = $DatabaseName
    DatabaseHost = $DatabaseHost
    DatabasePort = $DatabasePort
    Credential = $credential
} | Export-Clixml -LiteralPath (Join-Path $localDirectory 'database.clixml')
Write-Host 'Database configuration saved locally. Password is protected by Windows DPAPI.'
