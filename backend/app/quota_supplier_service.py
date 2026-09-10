"""CRUD de fornecedores de cotas + resolução de markup/comissão para o robô."""

from __future__ import annotations

import re
from decimal import Decimal

from fastapi import HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import QuotaSupplier, User
from app.services import money

# Markup na entrada = % do crédito (Paulo). Fallback quando cadastro ainda não existe.
SUPPLIER_ENTRADA_MARKUP_PERCENT: dict[str, Decimal] = {
    "FRAGA": Decimal("3"),
    "BITTELO": Decimal("3"),
    "LANCE": Decimal("3"),
    "UNI_CONTEMPLADOS": Decimal("10"),
    "UNI CONTEMPLADOS": Decimal("10"),
    "CONTEMPLADO_SP": Decimal("10"),
    "CONTEMPLADO SP": Decimal("10"),
    "LUME": Decimal("10"),
}

DEFAULT_SUPPLIERS: tuple[dict, ...] = (
    {"name": "Fraga Contemplados", "source_key": "FRAGA", "markup_percent": Decimal("3"), "document": "11111111000111"},
    {"name": "Bittelo", "source_key": "BITTELO", "markup_percent": Decimal("3"), "document": "22222222000122"},
    {"name": "Lance Contemplados", "source_key": "LANCE", "markup_percent": Decimal("3"), "document": "33333333000133"},
    {"name": "Uni Contemplados", "source_key": "UNI_CONTEMPLADOS", "markup_percent": Decimal("10"), "document": "44444444000144"},
    {"name": "Contemplado SP", "source_key": "CONTEMPLADO_SP", "markup_percent": Decimal("10"), "document": "55555555000155"},
    {"name": "Lume Contemplados", "source_key": "LUME", "markup_percent": Decimal("10"), "document": "66666666000166"},
)


def normalize_supplier_key(value: str | None) -> str:
    return (value or "").strip().upper().replace("-", "_")


def _digits(value: str | None) -> str:
    return re.sub(r"\D", "", value or "")


def normalize_source_key(value: str) -> str:
    key = normalize_supplier_key(value)
    if not key:
        raise HTTPException(status_code=422, detail="source_key obrigatório (ex.: FRAGA, LUME).")
    return key.replace(" ", "_")


def supplier_view(item: QuotaSupplier) -> dict:
    return {
        "id": item.id,
        "active": item.active,
        "person_type": item.person_type,
        "name": item.name,
        "trade_name": item.trade_name,
        "document": item.document,
        "email": item.email,
        "phone": item.phone,
        "source_key": item.source_key,
        "markup_percent": str(money(Decimal(str(item.markup_percent or 0)))),
        "quem_paga_comissao": int(item.quem_paga_comissao or 0),
        "platform_fee_percent": str(money(Decimal(str(item.platform_fee_percent or 0)))),
        "bank_name": item.bank_name,
        "bank_agency": item.bank_agency,
        "bank_account": item.bank_account,
        "pix_key": item.pix_key,
        "notes": item.notes,
        "sync_mode": item.sync_mode or "NONE",
        "api_url": item.api_url,
        "last_sync_at": item.last_sync_at,
        "last_sync_status": item.last_sync_status,
        "last_sync_detail_json": item.last_sync_detail_json or "{}",
        "created_at": item.created_at,
        "updated_at": item.updated_at,
    }


def list_suppliers(db: Session, user: User, *, active_only: bool = False) -> list[QuotaSupplier]:
    stmt = select(QuotaSupplier).where(QuotaSupplier.organization_id == user.organization_id)
    if active_only:
        stmt = stmt.where(QuotaSupplier.active.is_(True))
    return list(db.scalars(stmt.order_by(QuotaSupplier.name)))


def get_supplier(db: Session, user: User, supplier_id: str) -> QuotaSupplier:
    item = db.scalar(
        select(QuotaSupplier).where(
            QuotaSupplier.id == supplier_id,
            QuotaSupplier.organization_id == user.organization_id,
        )
    )
    if not item:
        raise HTTPException(status_code=404, detail="Fornecedor não encontrado")
    return item


def create_supplier(db: Session, user: User, data: dict) -> QuotaSupplier:
    source_key = normalize_source_key(str(data.get("source_key") or ""))
    document = _digits(str(data.get("document") or ""))
    if len(document) not in {11, 14}:
        raise HTTPException(status_code=422, detail="Informe CPF (11) ou CNPJ (14) válido.")
    exists = db.scalar(
        select(QuotaSupplier).where(
            QuotaSupplier.organization_id == user.organization_id,
            QuotaSupplier.source_key == source_key,
        )
    )
    if exists:
        raise HTTPException(status_code=409, detail=f"Já existe fornecedor com source_key {source_key}.")
    person_type = str(data.get("person_type") or ("PF" if len(document) == 11 else "PJ")).upper()
    if person_type not in {"PF", "PJ"}:
        raise HTTPException(status_code=422, detail="person_type deve ser PF ou PJ.")
    quem = int(data.get("quem_paga_comissao") or 0)
    if quem not in {0, 1}:
        raise HTTPException(status_code=422, detail="quem_paga_comissao deve ser 0 (fornecedor) ou 1 (cliente).")
    sync_mode = str(data.get("sync_mode") or "NONE").upper()
    if sync_mode not in {"NONE", "JSON", "SCRAPE"}:
        raise HTTPException(status_code=422, detail="sync_mode deve ser NONE, JSON ou SCRAPE.")
    api_url = (str(data["api_url"]).strip() if data.get("api_url") else None) or None
    if sync_mode == "JSON" and not api_url:
        raise HTTPException(status_code=422, detail="api_url obrigatória quando sync_mode=JSON.")
    item = QuotaSupplier(
        organization_id=user.organization_id,
        active=bool(data.get("active", True)),
        person_type=person_type,
        name=str(data["name"]).strip(),
        trade_name=(str(data["trade_name"]).strip() if data.get("trade_name") else None),
        document=document,
        email=(str(data["email"]).strip() if data.get("email") else None),
        phone=(str(data["phone"]).strip() if data.get("phone") else None),
        source_key=source_key,
        markup_percent=Decimal(str(data.get("markup_percent") or 0)),
        quem_paga_comissao=quem,
        platform_fee_percent=Decimal(str(data.get("platform_fee_percent") or 0)),
        bank_name=data.get("bank_name"),
        bank_agency=data.get("bank_agency"),
        bank_account=data.get("bank_account"),
        pix_key=data.get("pix_key"),
        notes=data.get("notes"),
        sync_mode=sync_mode,
        api_url=api_url,
    )
    db.add(item)
    db.flush()
    return item


def update_supplier(db: Session, user: User, supplier_id: str, data: dict) -> QuotaSupplier:
    item = get_supplier(db, user, supplier_id)
    if "source_key" in data and data["source_key"] is not None:
        new_key = normalize_source_key(str(data["source_key"]))
        if new_key != item.source_key:
            clash = db.scalar(
                select(QuotaSupplier).where(
                    QuotaSupplier.organization_id == user.organization_id,
                    QuotaSupplier.source_key == new_key,
                    QuotaSupplier.id != item.id,
                )
            )
            if clash:
                raise HTTPException(status_code=409, detail=f"Já existe fornecedor com source_key {new_key}.")
            item.source_key = new_key
    if "document" in data and data["document"] is not None:
        document = _digits(str(data["document"]))
        if len(document) not in {11, 14}:
            raise HTTPException(status_code=422, detail="Informe CPF (11) ou CNPJ (14) válido.")
        item.document = document
    for field in (
        "active",
        "person_type",
        "name",
        "trade_name",
        "email",
        "phone",
        "bank_name",
        "bank_agency",
        "bank_account",
        "pix_key",
        "notes",
    ):
        if field in data and data[field] is not None:
            setattr(item, field, data[field] if field != "name" else str(data[field]).strip())
    if "markup_percent" in data and data["markup_percent"] is not None:
        item.markup_percent = Decimal(str(data["markup_percent"]))
    if "platform_fee_percent" in data and data["platform_fee_percent"] is not None:
        item.platform_fee_percent = Decimal(str(data["platform_fee_percent"]))
    if "quem_paga_comissao" in data and data["quem_paga_comissao"] is not None:
        quem = int(data["quem_paga_comissao"])
        if quem not in {0, 1}:
            raise HTTPException(status_code=422, detail="quem_paga_comissao deve ser 0 ou 1.")
        item.quem_paga_comissao = quem
    if "sync_mode" in data and data["sync_mode"] is not None:
        sync_mode = str(data["sync_mode"]).upper()
        if sync_mode not in {"NONE", "JSON", "SCRAPE"}:
            raise HTTPException(status_code=422, detail="sync_mode deve ser NONE, JSON ou SCRAPE.")
        item.sync_mode = sync_mode
    if "api_url" in data:
        item.api_url = (str(data["api_url"]).strip() if data["api_url"] else None) or None
    final_mode = item.sync_mode or "NONE"
    if final_mode == "JSON" and not (item.api_url or "").strip():
        raise HTTPException(status_code=422, detail="api_url obrigatória quando sync_mode=JSON.")
    db.flush()
    return item


def ensure_default_suppliers(db: Session, organization_id: str) -> list[QuotaSupplier]:
    created: list[QuotaSupplier] = []
    for row in DEFAULT_SUPPLIERS:
        key = row["source_key"]
        exists = db.scalar(
            select(QuotaSupplier).where(
                QuotaSupplier.organization_id == organization_id,
                QuotaSupplier.source_key == key,
            )
        )
        if exists:
            continue
        item = QuotaSupplier(
            organization_id=organization_id,
            active=True,
            person_type="PJ",
            name=row["name"],
            document=row["document"],
            source_key=key,
            markup_percent=row["markup_percent"],
            quem_paga_comissao=0,
            platform_fee_percent=Decimal("0"),
        )
        db.add(item)
        created.append(item)
    if created:
        db.flush()
    return created


def suppliers_index(db: Session, organization_id: str) -> dict[str, QuotaSupplier]:
    rows = list(
        db.scalars(
            select(QuotaSupplier).where(
                QuotaSupplier.organization_id == organization_id,
                QuotaSupplier.active.is_(True),
            )
        )
    )
    return {normalize_supplier_key(r.source_key): r for r in rows}


def resolve_supplier_fees(
    supplier_source: str | None,
    *,
    suppliers: dict[str, QuotaSupplier] | None = None,
) -> dict:
    """Markup API + comissão embutida (quem_paga_comissao=1)."""
    key = normalize_supplier_key(supplier_source)
    supplier = None
    if suppliers and key:
        supplier = suppliers.get(key)
        if supplier is None:
            for sk, row in suppliers.items():
                if sk in key or key in sk:
                    supplier = row
                    break

    if supplier is not None:
        markup = money(Decimal(str(supplier.markup_percent or 0)))
        platform = (
            money(Decimal(str(supplier.platform_fee_percent or 0)))
            if int(supplier.quem_paga_comissao or 0) == 1
            else Decimal("0.00")
        )
        return {
            "markup_percent": markup,
            "platform_fee_percent": platform,
            "quem_paga_comissao": int(supplier.quem_paga_comissao or 0),
            "supplier_id": supplier.id,
            "supplier_name": supplier.name,
        }

    # Fallback mapa Paulo (hardcoded) quando cadastro ainda não existe
    markup = Decimal("0")
    if key in SUPPLIER_ENTRADA_MARKUP_PERCENT:
        markup = SUPPLIER_ENTRADA_MARKUP_PERCENT[key]
    else:
        for known, pct in SUPPLIER_ENTRADA_MARKUP_PERCENT.items():
            if known.replace("_", " ") in key.replace("_", " ") or known in key:
                markup = pct
                break
    return {
        "markup_percent": money(markup),
        "platform_fee_percent": Decimal("0.00"),
        "quem_paga_comissao": 0,
        "supplier_id": None,
        "supplier_name": None,
    }
