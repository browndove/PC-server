#!/usr/bin/env bash
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT"

if [[ ! -d .venv ]]; then
  python3 -m venv .venv
fi
# shellcheck source=/dev/null
source .venv/bin/activate
pip install -q -e .

export DATABASE_URL="${DATABASE_URL:-postgresql://postgres:postgres@127.0.0.1:54322/quikinspect}"
export JWT_SECRET="${JWT_SECRET:-local-dev-secret-change-me-32chars-min}"

echo "DATABASE_URL=$DATABASE_URL"
echo "Starting API at http://127.0.0.1:8000 (Ctrl+C to stop)"
exec uvicorn app.main:app --reload --host 127.0.0.1 --port 8000
