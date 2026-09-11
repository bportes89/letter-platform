"""CRUD + seed Paulo do FAQ do chat Marketplace."""

from __future__ import annotations

from fastapi import HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import MarketplaceChatFaq, User

# Seed Paulo (Items type=faq) — ids legados usados pelo widget.
PAULO_FAQ_SEED: tuple[dict[str, str | int], ...] = (
    {
        "legacy_key": "23",
        "name": "Essa compra é realmente segura?",
        "txt": (
            "Todas as opções de créditos cadastrados em nosso sistema são devidamente checadas "
            "por nosso setor de BackOffice e Compliance. Operamos em conformidade com a LGPD."
        ),
        "sort_order": 10,
    },
    {
        "legacy_key": "25",
        "name": "O que acontece com o meu dinheiro caso o processo não conclua?",
        "txt": (
            "Os valores pagos de entrada ficam retidos na plataforma. Se a transferência não "
            "concluir por parte do fornecedor, a entrada é devolvida em até 2 dias úteis."
        ),
        "sort_order": 20,
    },
    {
        "legacy_key": "24",
        "name": "Como funciona o faturamento do bem que irei comprar?",
        "txt": (
            "Após a transferência do crédito para o seu nome, você inicia o faturamento "
            "diretamente com a administradora. O crédito fica disponível para uso imediato."
        ),
        "sort_order": 30,
    },
    {
        "legacy_key": "40",
        "name": "O que é a Taxa de Transferência?",
        "txt": (
            "É a taxa cobrada pela administradora do crédito para concluir a transferência "
            "para o seu nome."
        ),
        "sort_order": 40,
    },
    {
        "legacy_key": "41",
        "name": "Quanto tempo demora em média a transferência?",
        "txt": (
            "Em condições normais, até 10 dias — varia por administradora e pela agilidade "
            "no envio de documentos por você e pelo fornecedor."
        ),
        "sort_order": 50,
    },
    {
        "legacy_key": "42",
        "name": "Estou negativado, consigo comprar?",
        "txt": (
            "Sim. Direcionamos créditos que permitem compra mesmo com restrição; na transferência "
            "pode ser necessário avalista sem restrições e com renda comprovada."
        ),
        "sort_order": 60,
    },
)


def faq_public_id(item: MarketplaceChatFaq) -> str:
    return str(item.legacy_key or item.id).strip()


def faq_view(item: MarketplaceChatFaq) -> dict:
    return {
        "id": item.id,
        "legacy_key": item.legacy_key,
        "public_id": faq_public_id(item),
        "name": item.name,
        "txt": item.txt,
        "active": bool(item.active),
        "sort_order": int(item.sort_order or 0),
        "created_at": item.created_at,
        "updated_at": item.updated_at,
    }


def list_faqs(
    db: Session,
    user: User,
    *,
    active_only: bool = False,
) -> list[MarketplaceChatFaq]:
    stmt = select(MarketplaceChatFaq).where(MarketplaceChatFaq.organization_id == user.organization_id)
    if active_only:
        stmt = stmt.where(MarketplaceChatFaq.active.is_(True))
    return list(db.scalars(stmt.order_by(MarketplaceChatFaq.sort_order, MarketplaceChatFaq.name)))


def get_faq(db: Session, user: User, faq_id: str) -> MarketplaceChatFaq:
    item = db.scalar(
        select(MarketplaceChatFaq).where(
            MarketplaceChatFaq.id == faq_id,
            MarketplaceChatFaq.organization_id == user.organization_id,
        )
    )
    if not item:
        raise HTTPException(status_code=404, detail="FAQ não encontrada")
    return item


def ensure_default_faqs(db: Session, organization_id: str) -> list[MarketplaceChatFaq]:
    created: list[MarketplaceChatFaq] = []
    for seed in PAULO_FAQ_SEED:
        key = str(seed["legacy_key"])
        existing = db.scalar(
            select(MarketplaceChatFaq).where(
                MarketplaceChatFaq.organization_id == organization_id,
                MarketplaceChatFaq.legacy_key == key,
            )
        )
        if existing:
            continue
        row = MarketplaceChatFaq(
            organization_id=organization_id,
            legacy_key=key,
            name=str(seed["name"]),
            txt=str(seed["txt"]),
            active=True,
            sort_order=int(seed["sort_order"]),
        )
        db.add(row)
        created.append(row)
    if created:
        db.flush()
    return created


def list_active_for_chat(db: Session, organization_id: str) -> list[dict[str, str]]:
    """Lista ativa para o widget (auto-seed Paulo se vazio)."""
    ensure_default_faqs(db, organization_id)
    rows = list(
        db.scalars(
            select(MarketplaceChatFaq)
            .where(
                MarketplaceChatFaq.organization_id == organization_id,
                MarketplaceChatFaq.active.is_(True),
            )
            .order_by(MarketplaceChatFaq.sort_order, MarketplaceChatFaq.name)
        )
    )
    return [{"id": faq_public_id(r), "name": r.name, "txt": r.txt} for r in rows]


def find_active_for_chat(db: Session, organization_id: str, faq_id: str | None) -> dict[str, str] | None:
    if not faq_id:
        return None
    key = str(faq_id).strip()
    if not key:
        return None
    ensure_default_faqs(db, organization_id)
    rows = list(
        db.scalars(
            select(MarketplaceChatFaq).where(
                MarketplaceChatFaq.organization_id == organization_id,
                MarketplaceChatFaq.active.is_(True),
            )
        )
    )
    for row in rows:
        if faq_public_id(row) == key or row.id == key:
            return {"id": faq_public_id(row), "name": row.name, "txt": row.txt}
    return None


def create_faq(db: Session, user: User, payload: dict) -> MarketplaceChatFaq:
    name = str(payload.get("name") or "").strip()
    txt = str(payload.get("txt") or "").strip()
    if len(name) < 3:
        raise HTTPException(status_code=422, detail="Pergunta (name) obrigatória")
    if len(txt) < 3:
        raise HTTPException(status_code=422, detail="Resposta (txt) obrigatória")
    legacy_key = payload.get("legacy_key")
    legacy = str(legacy_key).strip() if legacy_key is not None and str(legacy_key).strip() else None
    if legacy:
        clash = db.scalar(
            select(MarketplaceChatFaq).where(
                MarketplaceChatFaq.organization_id == user.organization_id,
                MarketplaceChatFaq.legacy_key == legacy,
            )
        )
        if clash:
            raise HTTPException(status_code=409, detail=f"legacy_key '{legacy}' já existe")
    sort_order = int(payload.get("sort_order") if payload.get("sort_order") is not None else 100)
    active = bool(payload.get("active", True))
    item = MarketplaceChatFaq(
        organization_id=user.organization_id,
        legacy_key=legacy,
        name=name,
        txt=txt,
        active=active,
        sort_order=sort_order,
    )
    db.add(item)
    db.flush()
    return item


def update_faq(db: Session, user: User, faq_id: str, payload: dict) -> MarketplaceChatFaq:
    item = get_faq(db, user, faq_id)
    if "name" in payload and payload["name"] is not None:
        name = str(payload["name"]).strip()
        if len(name) < 3:
            raise HTTPException(status_code=422, detail="Pergunta (name) obrigatória")
        item.name = name
    if "txt" in payload and payload["txt"] is not None:
        txt = str(payload["txt"]).strip()
        if len(txt) < 3:
            raise HTTPException(status_code=422, detail="Resposta (txt) obrigatória")
        item.txt = txt
    if "active" in payload and payload["active"] is not None:
        item.active = bool(payload["active"])
    if "sort_order" in payload and payload["sort_order"] is not None:
        item.sort_order = int(payload["sort_order"])
    if "legacy_key" in payload:
        raw = payload["legacy_key"]
        legacy = str(raw).strip() if raw is not None and str(raw).strip() else None
        if legacy and legacy != item.legacy_key:
            clash = db.scalar(
                select(MarketplaceChatFaq).where(
                    MarketplaceChatFaq.organization_id == user.organization_id,
                    MarketplaceChatFaq.legacy_key == legacy,
                    MarketplaceChatFaq.id != item.id,
                )
            )
            if clash:
                raise HTTPException(status_code=409, detail=f"legacy_key '{legacy}' já existe")
        item.legacy_key = legacy
    db.flush()
    return item


def delete_faq(db: Session, user: User, faq_id: str) -> None:
    item = get_faq(db, user, faq_id)
    db.delete(item)
    db.flush()
