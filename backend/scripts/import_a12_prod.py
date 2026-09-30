"""A12 — importação Paulo/prod a partir de letter_banco_new.sql (+ bundle opcional).

Executa no host que tem o dump SQL e `LETTER_DATABASE_URL` do ambiente alvo
(ex.: shell do serviço API no Render).

Exemplo:
  cd backend
  set LETTER_DATABASE_URL=postgresql://...
  py scripts/import_a12_prod.py --sql ../legacy/letter_banco_new.sql
  py scripts/import_a12_prod.py --sql ../legacy/letter_banco_new.sql --bundle ../legacy/export/bundle.json --apply-bundle
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
REPO_ROOT = ROOT.parent

if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))


def _resolve_sql(path: str | None) -> Path:
    from app.legacy_export_service import DEFAULT_SQL

    if not path:
        return DEFAULT_SQL
    candidate = Path(path)
    for base in (candidate, REPO_ROOT / path, ROOT / path):
        if base.is_file():
            return base
    raise FileNotFoundError(f"SQL não encontrado: {path}")


def _resolve_bundle(path: str | None) -> Path | None:
    if not path:
        return None
    candidate = Path(path)
    for base in (candidate, REPO_ROOT / path, ROOT / path):
        if base.is_file():
            return base
    raise FileNotFoundError(f"Bundle não encontrado: {path}")


def main() -> int:
    parser = argparse.ArgumentParser(description="A12: import legado → LETTER (SQL + bundle)")
    parser.add_argument("--sql", help="Caminho do letter_banco_new.sql (default: legacy/letter_banco_new.sql)")
    parser.add_argument("--actor-email", default="admin@letter.com.br", help="Admin da organização alvo")
    parser.add_argument("--bundle", help="Bundle JSON (export_legacy_v1.py) para admins/cotas/rede")
    parser.add_argument(
        "--apply-bundle",
        action="store_true",
        help="Aplicar bundle (sem isso só dry-run do bundle, se --bundle informado)",
    )
    parser.add_argument("--dry-run-bundle", action="store_true", help="Só validar bundle (ignora --apply-bundle)")
    parser.add_argument("--skip-categories", action="store_true")
    parser.add_argument("--skip-settings", action="store_true")
    parser.add_argument("--skip-texts", action="store_true")
    parser.add_argument("--skip-qualification", action="store_true")
    parser.add_argument("--ensure-marketplace-emails", action="store_true", help="Criar slugs email-marketplace-* no CMS")
    parser.add_argument("--ensure-suppliers", action="store_true", help="Fornecedores padrão marketplace")
    args = parser.parse_args()

    sql_path = _resolve_sql(args.sql)
    bundle_path = _resolve_bundle(args.bundle)

    from sqlalchemy import select

    from app.cms_text_service import import_legacy_texts
    from app.db import SessionLocal
    from app.legacy_export_service import DEFAULT_SQL
    from app.legacy_migration_service import apply_bundle, migration_run_view, normalize_bundle
    from app.org_settings_service import import_legacy_settings
    from app.partner_qualification_service import import_legacy_tiers
    from app.quota_category_service import import_legacy_categories
    from app.models import User

    if not sql_path.is_file():
        print(f"SQL ausente: {sql_path}", file=sys.stderr)
        print(f"Esperado em: {DEFAULT_SQL}", file=sys.stderr)
        return 1

    report: dict[str, object] = {"sql": str(sql_path), "steps": []}

    db = SessionLocal()
    try:
        user = db.scalar(select(User).where(User.email == args.actor_email.lower().strip()))
        if not user:
            print(f"Usuário admin não encontrado: {args.actor_email}", file=sys.stderr)
            return 1
        org_id = user.organization_id

        if not args.skip_categories:
            r = import_legacy_categories(db, org_id, sql_path=sql_path)
            report["steps"].append({"step": "quota_categories", "result": r})
            print("quota_categories:", json.dumps(r, ensure_ascii=False))

        if not args.skip_settings:
            r = import_legacy_settings(db, org_id, sql_path=sql_path)
            report["steps"].append({"step": "org_settings", "result": r})
            print("org_settings:", json.dumps(r, ensure_ascii=False))

        if not args.skip_texts:
            r = import_legacy_texts(db, org_id, sql_path=sql_path)
            report["steps"].append({"step": "cms_texts", "result": r})
            print("cms_texts:", json.dumps(r, ensure_ascii=False))

        if not args.skip_qualification:
            r = import_legacy_tiers(db, org_id, sql_path=sql_path)
            report["steps"].append({"step": "partner_qualification_tiers", "result": r})
            print("partner_qualification_tiers:", json.dumps(r, ensure_ascii=False))

        if args.ensure_marketplace_emails:
            from app.marketplace_cms_email_service import ensure_marketplace_email_templates

            r = ensure_marketplace_email_templates(db, org_id)
            report["steps"].append({"step": "ensure_marketplace_emails", "result": r})
            print("ensure_marketplace_emails:", json.dumps(r, ensure_ascii=False))

        if args.ensure_suppliers:
            from app.quota_supplier_service import ensure_default_suppliers

            ensure_default_suppliers(db, org_id)
            report["steps"].append({"step": "ensure_suppliers", "result": {"ok": True}})
            print("ensure_suppliers: ok")

        if bundle_path:
            raw = json.loads(bundle_path.read_text(encoding="utf-8"))
            bundle = normalize_bundle(raw)
            dry = args.dry_run_bundle or not args.apply_bundle
            run, mig_report = apply_bundle(db, user, bundle, dry_run=dry)
            view = migration_run_view(run)
            blockers = [i for i in mig_report.issues if i.level == "ERROR"]
            report["steps"].append(
                {
                    "step": "migration_bundle",
                    "dry_run": dry,
                    "run": view,
                    "ready": view["summary"].get("ready"),
                    "errors": len(blockers),
                }
            )
            print("migration_bundle:", json.dumps(view, ensure_ascii=False, indent=2))
            if blockers and not dry:
                db.rollback()
                print("Bundle apply falhou — rollback.", file=sys.stderr)
                return 2

        db.commit()
        print(json.dumps({"status": "ok", **report}, ensure_ascii=False, indent=2))
        return 0
    except Exception as exc:
        db.rollback()
        print(str(exc), file=sys.stderr)
        return 1
    finally:
        db.close()


if __name__ == "__main__":
    raise SystemExit(main())
