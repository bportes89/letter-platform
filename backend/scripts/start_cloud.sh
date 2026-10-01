#!/usr/bin/env bash
set -euo pipefail

cd "$(dirname "$0")/.."

echo "[letter] materializing Inter mTLS certs (if LETTER_INTER_*_BASE64 set)..."
python scripts/materialize_inter_certs.py

echo "[letter] running migrations..."
python -m alembic upgrade head
echo "[letter] migrations complete"

if [[ "${LETTER_RUN_STARTUP_SEED:-0}" == "1" ]]; then
  echo "[letter] seeding demo data (idempotent)..."
  python -m app.seed
else
  echo "[letter] startup seed skipped (LETTER_RUN_STARTUP_SEED=1 no Render para rodar seed)"
fi

echo "[letter] starting API on 0.0.0.0:${PORT:-8000}"
exec python -m uvicorn app.main:app --host 0.0.0.0 --port "${PORT:-8000}"
