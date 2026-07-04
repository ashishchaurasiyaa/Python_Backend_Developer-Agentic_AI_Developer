#!/bin/bash
set -e

PROJECT_ROOT="$(cd "$(dirname "$0")/../../.." && pwd)"
cd "$PROJECT_ROOT"

# Activate venv if present
if [ -d ".venv" ]; then
  source .venv/bin/activate
fi

# Load .env
if [ -f ".env" ]; then
  export $(grep -v '^#' .env | xargs)
fi

echo "[run-app] Starting Multi-Agent Code Review System..."

if [ -z "$ANTHROPIC_API_KEY" ]; then
  echo "[run-app] No ANTHROPIC_API_KEY — running skeleton (demo mode)"
  python main.py
else
  echo "[run-app] API key found — launching full FastAPI server on port ${PORT:-8000}"
  uvicorn app.api.webhook:app --host "${HOST:-127.0.0.1}" --port "${PORT:-8000}" --reload
fi
