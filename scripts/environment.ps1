# Shared local runtime discovery. Dot-source from other project scripts.
$ErrorActionPreference = 'Stop'
$ProjectRoot = Split-Path $PSScriptRoot -Parent
Set-Location -LiteralPath $ProjectRoot

$nodeDirs = Get-ChildItem -LiteralPath (Join-Path $ProjectRoot '.tools') -Directory -Filter 'node-*-win-x64' -ErrorAction SilentlyContinue
if ($nodeDirs) {
    $env:PATH = $nodeDirs[-1].FullName + [IO.Path]::PathSeparator + $env:PATH
}

# Windows processes inherit environment variables at launch. Refresh this one
# explicitly so a key just saved in Windows Settings works without restarting.
if (-not $env:OPENROUTER_API_KEY) {
    $keyName = if ($env:OPENROUTER_API_KEY_ENV) { $env:OPENROUTER_API_KEY_ENV } else { 'OPENROUTER_API_KEY' }
    $keyValue = [Environment]::GetEnvironmentVariable($keyName, 'Process')
    if (-not $keyValue) { $keyValue = [Environment]::GetEnvironmentVariable($keyName, 'User') }
    if (-not $keyValue) { $keyValue = [Environment]::GetEnvironmentVariable($keyName, 'Machine') }
    if ($keyValue) { $env:OPENROUTER_API_KEY = $keyValue }
    Remove-Variable keyValue
}

if (-not $env:SOFFICE_PATH) {
    $loCandidates = @(
        (Join-Path $ProjectRoot '.tools\libreoffice\LibreOffice\program\soffice.com'),
        (Join-Path $ProjectRoot '.tools\libreoffice\program\soffice.com'),
        'C:\Program Files\LibreOffice\program\soffice.com'
    )
    foreach ($loCandidate in $loCandidates) {
        if (Test-Path -LiteralPath $loCandidate) { $env:SOFFICE_PATH = $loCandidate; break }
    }
}

function Invoke-Checked {
    param([string]$Program, [string[]]$Arguments)
    & $Program @Arguments
    if ($LASTEXITCODE -ne 0) { throw "$Program exited with code $LASTEXITCODE" }
}
