#!/usr/bin/env python3
"""Cron Render: avalia assinaturas LSS e emite renovação Inter quando vencido."""

from __future__ import annotations

import json
import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
os.chdir(ROOT)
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))


def main() -> int:
    from app.db import SessionLocal
    from app.lss_billing_service import run_lss_billing_evaluation_job

    db = SessionLocal()
    try:
        result = run_lss_billing_evaluation_job(db)
        db.commit()
        print(json.dumps(result, ensure_ascii=False, default=str))
        return 0
    except Exception as exc:
        db.rollback()
        print(json.dumps({"status": "ERROR", "error": str(exc)}, ensure_ascii=False))
        return 1
    finally:
        db.close()


if __name__ == "__main__":
    raise SystemExit(main())
