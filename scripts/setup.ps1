param([string]$Python = 'python')
. "$PSScriptRoot\environment.ps1"

$pythonVersion = & $Python -c 'import platform; print(platform.python_version())'
if ($LASTEXITCODE -ne 0 -or [Version]$pythonVersion -lt [Version]'3.14') { throw 'Python 3.14+ is required.' }
if (-not (Get-Command node -ErrorAction SilentlyContinue)) { throw 'Install Node.js 24 LTS and reopen your terminal.' }
$nodeVersion = & node --version
if ($LASTEXITCODE -ne 0 -or [Version]($nodeVersion.TrimStart('v')) -lt [Version]'24.0') { throw 'Node.js 24 LTS is required.' }
if (-not (Test-Path -LiteralPath '.venv\Scripts\python.exe')) { Invoke-Checked $Python @('-m', 'venv', '.venv') }
Invoke-Checked '.venv\Scripts\python.exe' @('-m', 'pip', 'install', '-r', 'requirements-lock.txt')
Invoke-Checked '.venv\Scripts\python.exe' @('-m', 'pip', 'install', '-e', '.', '--no-deps')
Push-Location frontend
try {
    Invoke-Checked 'npm.cmd' @('ci')
    Invoke-Checked 'npm.cmd' @('run', 'build')
} finally { Pop-Location }
if (-not $env:SOFFICE_PATH -and -not (Get-Command soffice -ErrorAction SilentlyContinue)) {
    Write-Warning 'LibreOffice was not found. Install it or set SOFFICE_PATH before ingesting legacy Office files.'
}
Write-Host 'Setup complete. Set OPENROUTER_API_KEY, then run .\scripts\run.ps1 ingest and .\scripts\run.ps1 serve.'
