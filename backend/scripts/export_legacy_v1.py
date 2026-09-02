"""Exporta letter_banco_new.sql para bundle JSON de migração."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from app.legacy_export_service import DEFAULT_OUTPUT, DEFAULT_SQL, export_legacy_bundle, write_bundle


def main() -> int:
    parser = argparse.ArgumentParser(description="Exportar dump SQL legado para bundle JSON")
    parser.add_argument("--sql", type=Path, default=DEFAULT_SQL, help="Caminho do dump SQL")
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT, help="Arquivo JSON de saída")
    parser.add_argument("--legacy-source", default="letter_v1", help="Identificador da origem")
    parser.add_argument("--org-name", default="FPS Consórcios / Letter")
    parser.add_argument("--include-inactive", action="store_true", help="Incluir registros inactive=0")
    parser.add_argument("--limit-quotas", type=int, default=0, help="Limitar cotas (0 = todas)")
    parser.add_argument("--limit-customers", type=int, default=0, help="Limitar clientes (0 = todos)")
    parser.add_argument("--limit-affiliates", type=int, default=0, help="Limitar afiliados (0 = todos)")
    args = parser.parse_args()

    if not args.sql.is_file():
        print(f"SQL não encontrado: {args.sql}", file=sys.stderr)
        return 1

    limits: dict[str, int] = {}
    if args.limit_quotas:
        limits["quotas"] = args.limit_quotas
    if args.limit_customers:
        limits["customers"] = args.limit_customers
    if args.limit_affiliates:
        limits["affiliates"] = args.limit_affiliates

    bundle = export_legacy_bundle(
        args.sql,
        legacy_source=args.legacy_source,
        org_name=args.org_name,
        include_inactive=args.include_inactive,
        limit=limits or None,
    )
    write_bundle(bundle, args.output)

    summary = {
        "output": str(args.output),
        "legacy_source": bundle["legacy_source"],
        "exported_counts": bundle["meta"]["exported_counts"],
        "skipped": bundle["meta"]["skipped"],
    }
    print(json.dumps(summary, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
