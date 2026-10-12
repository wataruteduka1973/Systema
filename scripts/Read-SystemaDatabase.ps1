# Prints saved database settings as KEY=VALUE lines for run_systema.bat.
# Only keys missing from the current environment are printed, so values set in the
# launching shell always win. Prints nothing when no settings were saved.
$ErrorActionPreference = 'Stop'
$projectRoot = Split-Path -Parent $PSScriptRoot
$configurationPath = Join-Path $projectRoot '.local/database.clixml'
if (-not (Test-Path -LiteralPath $configurationPath)) {
    exit 0
}
try {
    $configuration = Import-Clixml -LiteralPath $configurationPath
    if ($configuration.Credential -isnot [System.Management.Automation.PSCredential]) {
        throw 'Invalid credential type'
    }
    $values = [ordered]@{
        DB_NAME = $configuration.DatabaseName
        DB_HOST = $configuration.DatabaseHost
        DB_PORT = [string]$configuration.DatabasePort
        DB_USER = $configuration.Credential.UserName
        DB_PASSWORD = $configuration.Credential.GetNetworkCredential().Password
    }
} catch {
    # Saved by another Windows user or machine, or damaged: fall back to prompting.
    [Console]::Error.WriteLine('Saved database settings could not be read. Run scripts\Set-SystemaDatabase.ps1 again.')
    exit 1
}
foreach ($key in $values.Keys) {
    $value = [string]$values[$key]
    if ([string]::IsNullOrEmpty([Environment]::GetEnvironmentVariable($key, 'Process')) -and $value -and $value -notmatch '[\r\n]') {
        Write-Output "$key=$value"
    }
}
