# Pass manage.py arguments, e.g. .\scripts\Invoke-Systema.ps1 check_database
$ErrorActionPreference = 'Stop'
$manageArguments = $args
if ($manageArguments.Count -eq 0) {
    throw 'Specify a manage.py command, for example: check_database'
}
$projectRoot = Split-Path -Parent $PSScriptRoot
$pythonPath = Join-Path $projectRoot '.venv/Scripts/python.exe'
$configurationPath = Join-Path $projectRoot '.local/database.clixml'
$keys = @('DB_ENGINE', 'DB_NAME', 'DB_USER', 'DB_PASSWORD', 'DB_HOST', 'DB_PORT')
$previous = @{}
foreach ($key in $keys) {
    $previous[$key] = [Environment]::GetEnvironmentVariable($key, 'Process')
}
$commandExitCode = 1
try {
    if (Test-Path -LiteralPath $configurationPath) {
        try {
            $configuration = Import-Clixml -LiteralPath $configurationPath
            if ($configuration.Credential -isnot [System.Management.Automation.PSCredential]) {
                throw 'Invalid credential type'
            }
            $defaults = @{
                DB_ENGINE = 'postgresql'
                DB_NAME = $configuration.DatabaseName
                DB_HOST = $configuration.DatabaseHost
                DB_PORT = [string]$configuration.DatabasePort
                DB_USER = $configuration.Credential.UserName
                DB_PASSWORD = $configuration.Credential.GetNetworkCredential().Password
            }
        } catch {
            throw 'Cannot load local database credentials. Run Set-SystemaDatabase.ps1 as the current Windows user.'
        }
        foreach ($key in $keys) {
            if ([string]::IsNullOrWhiteSpace($previous[$key])) {
                [Environment]::SetEnvironmentVariable($key, $defaults[$key], 'Process')
            }
        }
    }
    if ($env:DB_ENGINE -ne 'sqlite') {
        foreach ($key in @('DB_NAME', 'DB_USER', 'DB_PASSWORD')) {
            if ([string]::IsNullOrWhiteSpace([Environment]::GetEnvironmentVariable($key, 'Process'))) {
                throw "Missing $key. Run scripts/Set-SystemaDatabase.ps1 interactively first."
            }
        }
    }
    Push-Location -LiteralPath $projectRoot
    try {
        & $pythonPath manage.py @manageArguments
        $commandExitCode = $LASTEXITCODE
    } finally {
        Pop-Location
    }
} finally {
    foreach ($key in $keys) {
        if ($null -eq $previous[$key]) {
            Remove-Item -LiteralPath "Env:$key" -ErrorAction SilentlyContinue
        } else {
            [Environment]::SetEnvironmentVariable($key, $previous[$key], 'Process')
        }
    }
    $defaults = $null
    $configuration = $null
}
exit $commandExitCode
