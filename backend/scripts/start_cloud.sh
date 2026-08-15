#!/usr/bin/env bash
set -euo pipefail

cd "$(dirname "$0")/.."

echo "[letter] running migrations..."
python -m alembic upgrade head
echo "[letter] migrations complete"

echo "[letter] seeding demo data (idempotent)..."
python -m app.seed

echo "[letter] starting API on 0.0.0.0:${PORT:-8000}"
exec python -m uvicorn app.main:app --host 0.0.0.0 --port "${PORT:-8000}"
