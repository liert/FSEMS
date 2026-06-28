#!/bin/bash
# Start FSEMS dev processes on the host (no Docker). Run from repo root.
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT"

if [[ ! -f .env ]]; then
  echo "Copy .env.example to .env and adjust values first." >&2
  exit 1
fi

# shellcheck disable=SC1091
set -a && source .env && set +a

API_HOST="${API_HOST:-127.0.0.1}"
API_PORT="${API_PORT:-8000}"

cleanup() {
  jobs -p | xargs -r kill 2>/dev/null || true
}
trap cleanup EXIT INT TERM

if [[ ! -d backend/.venv ]]; then
  echo "Create backend venv first: cd backend && python3 -m venv .venv && pip install -r requirements.txt" >&2
  exit 1
fi

# shellcheck disable=SC1091
source backend/.venv/bin/activate

echo "Starting FastAPI on ${API_HOST}:${API_PORT} ..."
(cd backend && uvicorn app.main:app --host "$API_HOST" --port "$API_PORT" --reload) &

echo "Starting Celery worker ..."
celery -A app.core.celery_app worker --loglevel=info --workdir backend &

if [[ -d frontend/node_modules ]]; then
  echo "Starting Vite dev server ..."
  (cd frontend && npm run dev) &
else
  echo "Skip frontend: run 'cd frontend && npm install' first." >&2
fi

echo "Dev stack running. Press Ctrl+C to stop."
wait
