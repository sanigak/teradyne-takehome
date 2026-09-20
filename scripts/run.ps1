param(
    [Parameter(Position=0)][ValidateSet('serve','ingest','evaluate','smoke','test','ui-test','generate')][string]$Command = 'serve',
    [int]$Port = 8000
)
. "$PSScriptRoot\environment.ps1"
$pythonPath = Join-Path $ProjectRoot '.venv\Scripts\python.exe'
if (-not (Test-Path -LiteralPath $pythonPath)) { throw 'Run .\scripts\setup.ps1 first.' }
switch ($Command) {
    'serve' { Invoke-Checked $pythonPath @('-m','uvicorn','app.main:app','--host','127.0.0.1','--port',"$Port") }
    'ingest' { Invoke-Checked $pythonPath @('-m','app','ingest') }
    'evaluate' { Invoke-Checked $pythonPath @('-m','app','evaluate') }
    'smoke' { Invoke-Checked $pythonPath @('-m','app','smoke') }
    'test' { Invoke-Checked $pythonPath @('-m','pytest','-q') }
    'ui-test' {
        Push-Location frontend
        try {
            Invoke-Checked 'npm.cmd' @('run','build')
            Invoke-Checked 'npx.cmd' @('--no-install','playwright','install','chromium')
            Invoke-Checked 'npm.cmd' @('run','test:e2e')
        } finally { Pop-Location }
    }
    'generate' { Invoke-Checked $pythonPath @('scripts/generate_corpus.py') }
}
