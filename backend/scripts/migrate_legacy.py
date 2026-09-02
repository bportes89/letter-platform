"""CLI de migração legado — dry-run e apply parcial (organizations/branches)."""

from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
REPO_ROOT = ROOT.parent

# Banco isolado para dry-run local (evita letter.db desatualizado na máquina de dev)
DEFAULT_MIGRATION_DB = ROOT / "letter_migration_dryrun.db"
os.chdir(ROOT)
os.environ.setdefault("LETTER_DATABASE_URL", f"sqlite:///{DEFAULT_MIGRATION_DB.as_posix()}")
os.environ.setdefault("LETTER_SECRET_KEY", "migration-dryrun-secret-key-with-32-chars")

if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))


def ensure_local_database(force_rebuild: bool = False) -> None:
    from sqlalchemy import inspect, select

    from app.core.config import get_settings
    from app.db import Base, SessionLocal, engine
    from app.models import User
    from app.seed import seed

    get_settings.cache_clear()

    if force_rebuild and DEFAULT_MIGRATION_DB.exists():
        engine.dispose()
        DEFAULT_MIGRATION_DB.unlink(missing_ok=True)
        get_settings.cache_clear()

    if not DEFAULT_MIGRATION_DB.exists() or not inspect(engine).has_table("users"):
        if DEFAULT_MIGRATION_DB.exists():
            engine.dispose()
            DEFAULT_MIGRATION_DB.unlink(missing_ok=True)
            get_settings.cache_clear()
        Base.metadata.create_all(engine)
        seed()

    db = SessionLocal()
    try:
        admin = db.scalar(select(User).where(User.email == "admin@letter.com.br"))
        if not admin:
            seed()
    finally:
        db.close()


def main() -> int:
    from sqlalchemy import select

    from app.db import SessionLocal
    from app.legacy_migration_service import apply_bundle, migration_run_view, normalize_bundle
    from app.models import User

    parser = argparse.ArgumentParser(description="Migração de dados legados LETTER")
    parser.add_argument("--file", required=True, help="Caminho do bundle JSON exportado do sistema antigo")
    parser.add_argument("--dry-run", action="store_true", help="Validar lote sem gravar entidades de negócio")
    parser.add_argument("--apply", action="store_true", help="Aplicar carga parcial (organizations e branches)")
    parser.add_argument("--actor-email", default="admin@letter.com.br", help="E-mail do admin executor")
    parser.add_argument("--rebuild-db", action="store_true", help="Recriar banco local de dry-run do zero")
    args = parser.parse_args()

    if bool(args.dry_run) == bool(args.apply):
        parser.error("Informe exatamente um modo: --dry-run ou --apply")

    bundle_path = Path(args.file)
    if not bundle_path.is_file():
        bundle_path = REPO_ROOT / args.file
    if not bundle_path.is_file():
        bundle_path = ROOT / args.file
    if not bundle_path.is_file():
        print(f"Arquivo não encontrado: {args.file}", file=sys.stderr)
        return 1

    raw = json.loads(bundle_path.read_text(encoding="utf-8"))
    bundle = normalize_bundle(raw)
    ensure_local_database(force_rebuild=args.rebuild_db or args.dry_run)
    db = SessionLocal()
    try:
        user = db.scalar(select(User).where(User.email == args.actor_email.lower()))
        if not user:
            print(f"Usuário não encontrado: {args.actor_email}", file=sys.stderr)
            return 1
        run, report = apply_bundle(db, user, bundle, dry_run=args.dry_run)
        db.commit()
        result = migration_run_view(run)
        print(json.dumps(result, indent=2, ensure_ascii=False))

        blockers = [issue for issue in report.issues if issue.level == "ERROR"]
        warnings = [issue for issue in report.warnings if issue.level == "WARNING"]
        print(
            json.dumps(
                {
                    "ready": result["summary"].get("ready"),
                    "issue_count": len(blockers),
                    "warning_count": len(warnings),
                    "top_issues": [issue.__dict__ for issue in blockers[:15]],
                    "top_warnings": [issue.__dict__ for issue in warnings[:10]],
                },
                ensure_ascii=False,
                indent=2,
            )
        )
        return 2 if blockers else 0
    except Exception as exc:
        db.rollback()
        print(str(exc), file=sys.stderr)
        return 1
    finally:
        db.close()


if __name__ == "__main__":
    raise SystemExit(main())
