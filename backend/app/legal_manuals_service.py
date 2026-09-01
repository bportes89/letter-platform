"""Catálogo de manuais e contratos jurídicos (área logada)."""

from __future__ import annotations

from pathlib import Path

from fastapi import HTTPException

MANUALS_ROOT = Path(__file__).resolve().parent.parent / "assets" / "legal-manuals"

MANUALS: tuple[dict, ...] = (
    {
        "slug": "master-franqueado",
        "title": "Master Franqueado — Contrato",
        "category": "Rede",
        "product": "MMN",
        "audience": "Master franqueado",
        "filename": "master-franqueado.docx",
        "description": "Contrato corrigido para master franqueado LETTER.",
    },
    {
        "slug": "parceiros",
        "title": "Parceiros — Contrato",
        "category": "Rede",
        "product": "Parceiros",
        "audience": "Parceiro comercial",
        "filename": "parceiros.docx",
        "description": "Contrato corrigido para parceiros comerciais.",
    },
    {
        "slug": "fundos-loi",
        "title": "Fundos — LOI e aceite de operações",
        "category": "Funding",
        "product": "Flash Invest",
        "audience": "Fundo institucional",
        "filename": "fundos-loi.docx",
        "description": "Carta de intenção e aceite operacional para fundos.",
    },
    {
        "slug": "term-sheet-fundos",
        "title": "Term Sheet — Contrato Fundos",
        "category": "Funding",
        "product": "Flash Invest",
        "audience": "Fundo institucional",
        "filename": "term-sheet-fundos.docx",
        "description": "Term sheet contratual para entrada de fundos.",
    },
    {
        "slug": "flash-invest",
        "title": "Flash Invest — Contrato",
        "category": "Investimentos",
        "product": "Flash Invest",
        "audience": "Investidor",
        "filename": "flash-invest.docx",
        "description": "Contrato corrigido Flash Invest.",
    },
    {
        "slug": "flash-capital-fundos",
        "title": "Flash Capital — Contrato Fundos",
        "category": "Crédito",
        "product": "Flash Capital",
        "audience": "Fundo / capital institucional",
        "filename": "flash-capital-fundos.docx",
        "description": "Contrato Flash Capital para veículo de fundos.",
    },
    {
        "slug": "flash-capital-pool",
        "title": "Flash Capital — Contrato Pool Investidores",
        "category": "Crédito",
        "product": "Flash Capital",
        "audience": "Pool de investidores",
        "filename": "flash-capital-pool.docx",
        "description": "Contrato Flash Capital para pool de investidores.",
    },
    {
        "slug": "flash-capital-pos-quitacao",
        "title": "Flash Capital — Contrato Pós Quitação",
        "category": "Crédito",
        "product": "Flash Capital",
        "audience": "Cliente pós-quitação",
        "filename": "flash-capital-pos-quitacao.docx",
        "description": "Contrato Flash Capital para operações pós quitação.",
    },
    {
        "slug": "carta-contemplada-fornecedor",
        "title": "Carta Contemplada — Contrato Fornecedor",
        "category": "Marketplace",
        "product": "Carta Contemplada",
        "audience": "Fornecedor de carta",
        "filename": "carta-contemplada-fornecedor.docx",
        "description": "Contrato para fornecedores de carta contemplada.",
    },
    {
        "slug": "carta-contemplada-cliente",
        "title": "Carta Contemplada — Contrato Cliente",
        "category": "Marketplace",
        "product": "Carta Contemplada",
        "audience": "Cliente comprador",
        "filename": "carta-contemplada-cliente.docx",
        "description": "Contrato para clientes de carta contemplada.",
    },
)


def _manual_path(filename: str) -> Path:
    path = MANUALS_ROOT / filename
    if not path.is_file():
        raise HTTPException(status_code=404, detail="Arquivo do manual não encontrado no servidor.")
    return path


def get_manual(slug: str) -> dict:
    item = next((row for row in MANUALS if row["slug"] == slug), None)
    if not item:
        raise HTTPException(status_code=404, detail="Manual ou contrato não encontrado.")
    return item


def list_public_manuals() -> list[dict]:
    return [
        {
            "slug": row["slug"],
            "title": row["title"],
            "category": row["category"],
            "product": row["product"],
            "audience": row["audience"],
            "description": row["description"],
            "requires_login": True,
        }
        for row in MANUALS
    ]


def list_authenticated_manuals() -> list[dict]:
    rows: list[dict] = []
    for row in MANUALS:
        path = MANUALS_ROOT / row["filename"]
        rows.append(
            {
                **row,
                "available": path.is_file(),
                "size_bytes": path.stat().st_size if path.is_file() else 0,
            }
        )
    return rows


def read_manual_bytes(slug: str) -> tuple[bytes, str, str]:
    item = get_manual(slug)
    path = _manual_path(item["filename"])
    content_type = "application/vnd.openxmlformats-officedocument.wordprocessingml.document"
    return path.read_bytes(), item["filename"], content_type
