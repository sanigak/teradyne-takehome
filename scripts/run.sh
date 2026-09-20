#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")/.."
if [[ -n "${OPENROUTER_API_KEY_ENV:-}" && -z "${OPENROUTER_API_KEY:-}" ]]; then
  alias_value="${!OPENROUTER_API_KEY_ENV:-}"
  if [[ -n "$alias_value" ]]; then export OPENROUTER_API_KEY="$alias_value"; fi
  unset alias_value
fi
case "${1:-serve}" in
  serve) exec .venv/bin/python -m uvicorn app.main:app --host 127.0.0.1 --port "${PORT:-8000}" ;;
  ingest) exec .venv/bin/python -m app ingest ;;
  evaluate) exec .venv/bin/python -m app evaluate ;;
  smoke) exec .venv/bin/python -m app smoke ;;
  test) exec .venv/bin/python -m pytest -q ;;
  ui-test) cd frontend; npm run build; npx --no-install playwright install chromium; exec npm run test:e2e ;;
  generate) exec .venv/bin/python scripts/generate_corpus.py ;;
  *) echo 'Usage: bash scripts/run.sh [serve|ingest|evaluate|smoke|test|ui-test|generate]' >&2; exit 2 ;;
esac
