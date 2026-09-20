#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")/.."
PYTHON="${PYTHON:-python3.14}"
"$PYTHON" -c 'import sys; assert sys.version_info >= (3,14), "Python 3.14+ is required"'
node -e 'if(Number(process.versions.node.split(".")[0]) < 24) process.exit(1)'
"$PYTHON" -m venv .venv
.venv/bin/python -m pip install -r requirements-lock.txt
.venv/bin/python -m pip install -e . --no-deps
(cd frontend && npm ci && npm run build)
command -v soffice >/dev/null || echo 'Install LibreOffice or set SOFFICE_PATH before ingesting legacy Office files.'
echo 'Set OPENROUTER_API_KEY, then use bash scripts/run.sh ingest and bash scripts/run.sh serve.'
