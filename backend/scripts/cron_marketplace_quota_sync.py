#!/usr/bin/env python3
"""Cron Render: sincroniza inventário JSON de todos os fornecedores ativos."""

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
    from app.quota_sync_service import default_sync_organization_id, sync_organization_inventory

    db = SessionLocal()
    try:
        org_id = default_sync_organization_id(db)
        result = sync_organization_inventory(db, org_id)
        db.commit()
        print(json.dumps(result, ensure_ascii=False, default=str))
        failed = int(result.get("failed") or 0)
        suppliers = int(result.get("suppliers") or 0)
        # Falha o job só se todos os fornecedores falharem (parcial ainda sincroniza estoque).
        return 1 if suppliers > 0 and failed >= suppliers else 0
    except Exception as exc:
        db.rollback()
        print(json.dumps({"status": "ERROR", "error": str(exc)}, ensure_ascii=False))
        return 1
    finally:
        db.close()


if __name__ == "__main__":
    raise SystemExit(main())
