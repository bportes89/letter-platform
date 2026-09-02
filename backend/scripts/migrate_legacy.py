"""CLI de migração legado — dry-run e apply parcial (organizations/branches)."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from sqlalchemy import select

from app.db import SessionLocal
from app.legacy_migration_service import apply_bundle, migration_run_view, normalize_bundle
from app.models import User


def main() -> int:
    parser = argparse.ArgumentParser(description="Migração de dados legados LETTER")
    parser.add_argument("--file", required=True, help="Caminho do bundle JSON exportado do sistema antigo")
    parser.add_argument("--dry-run", action="store_true", help="Validar lote sem gravar entidades de negócio")
    parser.add_argument("--apply", action="store_true", help="Aplicar carga parcial (organizations e branches)")
    parser.add_argument("--actor-email", default="admin@letter.com.br", help="E-mail do admin executor")
    args = parser.parse_args()

    if bool(args.dry_run) == bool(args.apply):
        parser.error("Informe exatamente um modo: --dry-run ou --apply")

    bundle_path = Path(args.file)
    if not bundle_path.is_file():
        print(f"Arquivo não encontrado: {bundle_path}", file=sys.stderr)
        return 1

    raw = json.loads(bundle_path.read_text(encoding="utf-8"))
    bundle = normalize_bundle(raw)
    db = SessionLocal()
    try:
        user = db.scalar(select(User).where(User.email == args.actor_email.lower()))
        if not user:
            print(f"Usuário não encontrado: {args.actor_email}", file=sys.stderr)
            return 1
        run, report = apply_bundle(db, user, bundle, dry_run=args.dry_run)
        db.commit()
        print(json.dumps(migration_run_view(run), indent=2, ensure_ascii=False))
        blockers = [issue for issue in report.issues if issue.level == "ERROR"]
        return 2 if blockers else 0
    except Exception as exc:
        db.rollback()
        print(str(exc), file=sys.stderr)
        return 1
    finally:
        db.close()


if __name__ == "__main__":
    raise SystemExit(main())
