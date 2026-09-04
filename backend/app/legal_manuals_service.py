"""Catálogo de manuais e contratos jurídicos (área logada)."""

from __future__ import annotations

from pathlib import Path

from fastapi import HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import PartnerContractAcceptance, User

MANUALS_ROOT = Path(__file__).resolve().parent.parent / "assets" / "legal-manuals"

MANUALS: tuple[dict, ...] = (
    {
        "slug": "manual-sdc",
        "title": "SDC — Manual do Produto",
        "category": "Crédito",
        "product": "SDC",
        "audience": "Parceiro e cliente",
        "filename": "manual-sdc.docx",
        "description": "Manual operacional do produto SDC (giro de consórcio).",
        "document_type": "manual",
    },
    {
        "slug": "manual-flash-capital",
        "title": "Flash Capital — Manual do Produto",
        "category": "Crédito",
        "product": "Flash Capital",
        "audience": "Parceiro e cliente",
        "filename": "manual-flash-capital.docx",
        "description": "Manual operacional do produto Flash Capital.",
        "document_type": "manual",
    },
    {
        "slug": "manual-flash-invest",
        "title": "Flash Invest — Manual do Produto",
        "category": "Investimentos",
        "product": "Flash Invest",
        "audience": "Investidor e fundo",
        "filename": "manual-flash-invest.docx",
        "description": "Manual operacional do produto Flash Invest.",
        "document_type": "manual",
    },
    {
        "slug": "manual-quitcon",
        "title": "QuitCon — Manual do Produto",
        "category": "Crédito",
        "product": "QuitCon",
        "audience": "Cedente e parceiro",
        "filename": "manual-quitcon.docx",
        "description": "Manual operacional do produto QuitCon.",
        "document_type": "manual",
    },
    {
        "slug": "manual-lease-equity",
        "title": "Lease Equity — Manual do Produto",
        "category": "Crédito",
        "product": "Lease Equity",
        "audience": "Parceiro e cliente",
        "filename": "manual-lease-equity.docx",
        "description": "Manual operacional do produto Lease Equity.",
        "document_type": "manual",
    },
    {
        "slug": "manual-carta-contemplada",
        "title": "Carta Contemplada — Manual do Produto",
        "category": "Marketplace",
        "product": "Carta Contemplada",
        "audience": "Fornecedor e comprador",
        "filename": "manual-carta-contemplada.docx",
        "description": "Manual operacional do marketplace de carta contemplada.",
        "document_type": "manual",
    },
    {
        "slug": "manual-rede-parceiro",
        "title": "Rede LETTER — Manual do Parceiro",
        "category": "Rede",
        "product": "Parceiros",
        "audience": "Parceiro comercial",
        "filename": "manual-rede-parceiro.docx",
        "description": "Manual operacional da rede comercial LETTER.",
        "document_type": "manual",
    },
    {
        "slug": "master-franqueado",
        "title": "Master Franqueado — Contrato",
        "category": "Rede",
        "product": "MMN",
        "audience": "Master franqueado",
        "filename": "master-franqueado.docx",
        "description": "Contrato corrigido para master franqueado LETTER.",
        "document_type": "contract",
    },
    {
        "slug": "parceiros",
        "title": "Parceiros — Contrato",
        "category": "Rede",
        "product": "Parceiros",
        "audience": "Parceiro comercial",
        "filename": "parceiros.docx",
        "description": "Contrato corrigido para parceiros comerciais.",
        "document_type": "contract",
    },
    {
        "slug": "fundos-loi",
        "title": "Fundos — LOI e aceite de operações",
        "category": "Funding",
        "product": "Flash Invest",
        "audience": "Fundo institucional",
        "filename": "fundos-loi.docx",
        "description": "Carta de intenção e aceite operacional para fundos.",
        "document_type": "contract",
    },
    {
        "slug": "term-sheet-fundos",
        "title": "Term Sheet — Contrato Fundos",
        "category": "Funding",
        "product": "Flash Invest",
        "audience": "Fundo institucional",
        "filename": "term-sheet-fundos.docx",
        "description": "Term sheet contratual para entrada de fundos.",
        "document_type": "contract",
    },
    {
        "slug": "flash-invest",
        "title": "Flash Invest — Contrato",
        "category": "Investimentos",
        "product": "Flash Invest",
        "audience": "Investidor",
        "filename": "flash-invest.docx",
        "description": "Contrato corrigido Flash Invest.",
        "document_type": "contract",
    },
    {
        "slug": "flash-capital-fundos",
        "title": "Flash Capital — Contrato Fundos",
        "category": "Crédito",
        "product": "Flash Capital",
        "audience": "Fundo / capital institucional",
        "filename": "flash-capital-fundos.docx",
        "description": "Contrato Flash Capital para veículo de fundos.",
        "document_type": "contract",
    },
    {
        "slug": "flash-capital-pool",
        "title": "Flash Capital — Contrato Pool Investidores",
        "category": "Crédito",
        "product": "Flash Capital",
        "audience": "Pool de investidores",
        "filename": "flash-capital-pool.docx",
        "description": "Contrato Flash Capital para pool de investidores.",
        "document_type": "contract",
    },
    {
        "slug": "flash-capital-pos-quitacao",
        "title": "Flash Capital — Contrato Pós Quitação",
        "category": "Crédito",
        "product": "Flash Capital",
        "audience": "Cliente pós-quitação",
        "filename": "flash-capital-pos-quitacao.docx",
        "description": "Contrato Flash Capital para operações pós quitação.",
        "document_type": "contract",
    },
    {
        "slug": "carta-contemplada-fornecedor",
        "title": "Carta Contemplada — Contrato Fornecedor",
        "category": "Marketplace",
        "product": "Carta Contemplada",
        "audience": "Fornecedor de carta",
        "filename": "carta-contemplada-fornecedor.docx",
        "description": "Contrato para fornecedores de carta contemplada.",
        "document_type": "contract",
    },
    {
        "slug": "carta-contemplada-cliente",
        "title": "Carta Contemplada — Contrato Cliente",
        "category": "Marketplace",
        "product": "Carta Contemplada",
        "audience": "Cliente comprador",
        "filename": "carta-contemplada-cliente.docx",
        "description": "Contrato para clientes de carta contemplada.",
        "document_type": "contract",
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


def signed_contract_slugs(db: Session, user: User) -> set[str]:
    rows = db.scalars(select(PartnerContractAcceptance.template_slug).where(PartnerContractAcceptance.user_id == user.id))
    return {slug for slug in rows if slug}


def user_can_access_document(db: Session, user: User, slug: str) -> bool:
    item = get_manual(slug)
    if item["document_type"] == "manual":
        return True
    return slug in signed_contract_slugs(db, user)


def _public_view(row: dict) -> dict:
    return {
        "slug": row["slug"],
        "title": row["title"],
        "category": row["category"],
        "product": row["product"],
        "audience": row["audience"],
        "description": row["description"],
        "document_type": row["document_type"],
        "requires_login": True,
    }


def list_public_manuals() -> list[dict]:
    return [_public_view(row) for row in MANUALS if row["document_type"] == "manual"]


def list_authenticated_manuals(db: Session, user: User) -> list[dict]:
    signed = signed_contract_slugs(db, user)
    rows: list[dict] = []
    for row in MANUALS:
        if row["document_type"] == "contract" and row["slug"] not in signed:
            continue
        path = MANUALS_ROOT / row["filename"]
        rows.append(
            {
                **_public_view(row),
                "filename": row["filename"],
                "available": path.is_file(),
                "size_bytes": path.stat().st_size if path.is_file() else 0,
            }
        )
    return rows


def read_manual_bytes(db: Session, user: User, slug: str) -> tuple[bytes, str, str]:
    if not user_can_access_document(db, user, slug):
        raise HTTPException(status_code=403, detail="Contrato disponível apenas após assinatura do serviço contratado.")
    item = get_manual(slug)
    path = _manual_path(item["filename"])
    content_type = "application/vnd.openxmlformats-officedocument.wordprocessingml.document"
    return path.read_bytes(), item["filename"], content_type
