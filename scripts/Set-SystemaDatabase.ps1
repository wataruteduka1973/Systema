# Run interactively once. Windows DPAPI protects the saved password for this user.
# -FromEnvironment saves DB_USER/DB_PASSWORD (and DB_NAME/DB_HOST/DB_PORT when set) from the
# current process instead of asking; run_systema.bat uses it after prompting, so the password
# never appears on a command line.
[CmdletBinding()]
param(
    [string]$DatabaseName = 'Yahuoku_analyze_DB',
    [string]$DatabaseHost = 'localhost',
    [ValidateRange(1, 65535)][int]$DatabasePort = 5432,
    [switch]$FromEnvironment
)
$ErrorActionPreference = 'Stop'
$projectRoot = Split-Path -Parent $PSScriptRoot
if ($FromEnvironment) {
    if ($env:DB_NAME) { $DatabaseName = $env:DB_NAME }
    if ($env:DB_HOST) { $DatabaseHost = $env:DB_HOST }
    if ($env:DB_PORT) { $DatabasePort = [int]$env:DB_PORT }
    if ([string]::IsNullOrEmpty($env:DB_USER) -or [string]::IsNullOrEmpty($env:DB_PASSWORD)) {
        throw 'DB_USER and DB_PASSWORD are required. Nothing was saved.'
    }
    $password = ConvertTo-SecureString -String $env:DB_PASSWORD -AsPlainText -Force
    $credential = [System.Management.Automation.PSCredential]::new($env:DB_USER, $password)
} else {
    $credential = Get-Credential -Message 'Systema PostgreSQL user and password'
}
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
