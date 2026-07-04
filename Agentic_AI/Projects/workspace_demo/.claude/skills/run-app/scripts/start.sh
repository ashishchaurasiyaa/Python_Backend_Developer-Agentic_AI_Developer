#!/usr/bin/env bash
# One-shot launcher for the Workspace Demo app.
# Bundled with the "run-app" skill — an example of a skill shipping a script.
set -euo pipefail

# Resolve the project root (four levels up from this script).
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../../../.." && pwd)"
cd "$ROOT"

echo "→ Installing dependencies…"
pip install -q -r requirements.txt

echo "→ Starting server at http://127.0.0.1:8000  (Ctrl+C to stop)"
exec uvicorn backend.main:app --reload
