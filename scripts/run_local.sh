#!/usr/bin/env bash
# Run the API locally without Docker.
#
# Prereq: Postgres on this machine (e.g. brew install postgresql@16 && brew services start postgresql@16).
# One-time: createdb quikinspect
#
# Override URL: export DATABASE_URL='postgresql://user:pass@127.0.0.1:5432/quikinspect'
# Override JWT:  export JWT_SECRET='...'
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT"

if [[ ! -d .venv ]]; then
  python3 -m venv .venv
fi
# shellcheck source=/dev/null
source .venv/bin/activate
pip install -q -e .

# Native Postgres default (Homebrew): role = macOS user, port 5432, DB quikinspect
export DATABASE_URL="${DATABASE_URL:-postgresql://${USER}@127.0.0.1:5432/quikinspect}"
export JWT_SECRET="${JWT_SECRET:-local-dev-secret-change-me-32chars-min}"

if command -v createdb >/dev/null 2>&1; then
  createdb quikinspect 2>/dev/null || true
fi

echo "DATABASE_URL=$DATABASE_URL"
echo "Starting API at http://127.0.0.1:8000 (Ctrl+C to stop)"
exec uvicorn app.main:app --reload --host 127.0.0.1 --port 8000
