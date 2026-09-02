"""Analisador do dump SQL legado — volumes e tabelas.

Uso: py backend/scripts/analyze_legacy_sql.py
"""
from __future__ import annotations

import re
from collections import Counter
from pathlib import Path

SQL = Path(__file__).resolve().parents[2] / "legacy" / "letter_banco_new.sql"


def main() -> None:
    sql = SQL.read_text(encoding="utf-8", errors="replace")
    inserts = Counter(re.findall(r"INSERT INTO [`']?(\w+)[`']?", sql))
    print("INSERT batches:", sum(inserts.values()))
    for table, n in inserts.most_common():
        print(f"  {table}: {n}")

    # row counts per table
    def count_rows(table: str) -> int:
        marker = f"INSERT INTO `{table}`"
        parts = sql.split(marker)
        total = 0
        for chunk in parts[1:]:
            end = chunk.find(";")
            block = chunk[:end] if end >= 0 else chunk
            total += len(re.findall(r"\)\s*,\s*\(", block)) + 1
        return total

    print("\nEstimated rows:")
    for table in (
        "administrators",
        "affiliates",
        "customers",
        "quotas",
        "users",
        "suppliers",
        "customers_sdc",
        "customers_documents",
    ):
        print(f"  {table}: {count_rows(table)}")


if __name__ == "__main__":
    main()
