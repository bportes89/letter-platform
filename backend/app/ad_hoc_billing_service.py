"""Cobranças avulsas: cadastro manual + visão unificada com TAPAF pendente/liquidado."""

from __future__ import annotations

from datetime import UTC, date, datetime
from decimal import Decimal, ROUND_HALF_UP
from uuid import uuid4

from fastapi import HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.infra_inventory_service import list_settlements
from app.models import (
    LeaseEquityPauta,
    PreAnalysisPauta,
    QuitConOperacao,
    StandaloneCharge,
    User,
)
from app.tapaf_constants import LEASE_EQUITY_TAPAF_NOMINAL, TAPAF_NOMINAL

STANDALONE_KINDS = {"TAPAF", "START_FEE", "TAXA", "OUTRA", "MANUAL"}
TAPAF_PENDING_PRE_ANALYSIS = {"DOCUMENTS_OK", "TAPAF_CHECKOUT_ACCEPTED"}
TAPAF_PENDING_QUITCON = {"AGUARDANDO_TAPAF", "TAPAF_CHECKOUT_ACCEPTED"}
TAPAF_PENDING_LEASE = {"AGUARDANDO_TAPAF"}


def money(value: Decimal) -> Decimal:
    return value.quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)


def _charge_number() -> str:
    return f"AVL-{datetime.now(UTC).strftime('%Y%m%d')}-{uuid4().hex[:8].upper()}"


def _view(
    *,
    charge_id: str,
    charge_number: str,
    kind: str,
    description: str,
    due_date: date,
    total_amount: Decimal,
    paid_amount: Decimal,
    status: str,
    source: str,
    reference_type: str | None = None,
    reference_id: str | None = None,
    payment_checkout_url: str | None = None,
    payable: bool = False,
    created_at: datetime | None = None,
) -> dict:
    return {
        "id": charge_id,
        "charge_number": charge_number,
        "kind": kind,
        "description": description,
        "due_date": due_date,
        "total_amount": money(total_amount),
        "paid_amount": money(paid_amount),
        "status": status,
        "source": source,
        "reference_type": reference_type,
        "reference_id": reference_id,
        "payment_checkout_url": payment_checkout_url,
        "payable": payable,
        "created_at": created_at,
    }


def create_standalone_charge(
    db: Session,
    user: User,
    *,
    kind: str,
    description: str,
    due_date: date,
    total_amount: Decimal,
    reference_type: str | None = None,
    reference_id: str | None = None,
    payment_checkout_url: str | None = None,
    notes: str | None = None,
) -> StandaloneCharge:
    normalized_kind = (kind or "MANUAL").strip().upper()
    if normalized_kind not in STANDALONE_KINDS:
        raise HTTPException(status_code=422, detail="Tipo de cobrança avulsa inválido.")
    amount = money(total_amount)
    if amount <= 0:
        raise HTTPException(status_code=422, detail="Valor da cobrança deve ser positivo.")
    item = StandaloneCharge(
        organization_id=user.organization_id,
        charge_number=_charge_number(),
        kind=normalized_kind,
        description=description.strip(),
        reference_type=reference_type,
        reference_id=reference_id,
        due_date=due_date,
        total_amount=amount,
        paid_amount=Decimal("0"),
        status="OPEN",
        payment_checkout_url=payment_checkout_url,
        created_by_id=user.id,
        notes=notes,
    )
    db.add(item)
    db.flush()
    return item


def apply_standalone_payment(
    db: Session,
    user: User,
    item: StandaloneCharge,
    event_id: str,
    amount: Decimal,
) -> StandaloneCharge:
    value = money(amount)
    outstanding = money(Decimal(str(item.total_amount)) - Decimal(str(item.paid_amount)))
    if value <= 0:
        raise HTTPException(status_code=422, detail="Valor do pagamento deve ser positivo.")
    item.paid_amount = money(Decimal(str(item.paid_amount)) + value)
    if value >= outstanding:
        item.status = "PAID" if value == outstanding else "OVERPAID"
        item.paid_at = datetime.now(UTC)
    else:
        item.status = "PARTIALLY_PAID"
    db.flush()
    return item


def _standalone_views(rows: list[StandaloneCharge]) -> list[dict]:
    output: list[dict] = []
    for item in rows:
        output.append(
            _view(
                charge_id=item.id,
                charge_number=item.charge_number,
                kind=item.kind,
                description=item.description,
                due_date=item.due_date,
                total_amount=Decimal(str(item.total_amount)),
                paid_amount=Decimal(str(item.paid_amount)),
                status=item.status,
                source="MANUAL",
                reference_type=item.reference_type,
                reference_id=item.reference_id,
                payment_checkout_url=item.payment_checkout_url,
                payable=item.status not in {"PAID", "CANCELLED"},
                created_at=item.created_at,
            )
        )
    return output


def _pending_tapaf_views(db: Session, user: User) -> list[dict]:
    rows: list[dict] = []
    today = date.today()

    pre_rows = list(
        db.scalars(
            select(PreAnalysisPauta)
            .where(
                PreAnalysisPauta.organization_id == user.organization_id,
                PreAnalysisPauta.status.in_(TAPAF_PENDING_PRE_ANALYSIS),
            )
            .order_by(PreAnalysisPauta.created_at.desc())
        )
    )
    for pauta in pre_rows:
        rows.append(
            _view(
                charge_id=f"tapaf-pre-{pauta.id}",
                charge_number=f"TAPAF-{pauta.pauta_code}",
                kind="TAPAF",
                description=f"TAPAF pré-análise — {pauta.pauta_code}",
                due_date=today,
                total_amount=TAPAF_NOMINAL,
                paid_amount=Decimal("0"),
                status="CHECKOUT_ACCEPTED" if pauta.status == "TAPAF_CHECKOUT_ACCEPTED" else "OPEN",
                source="TAPAF_CHECKOUT",
                reference_type="pre_analysis_pauta",
                reference_id=pauta.id,
                payment_checkout_url=pauta.checkout_url,
                payable=pauta.status == "TAPAF_CHECKOUT_ACCEPTED",
                created_at=pauta.created_at,
            )
        )

    quitcon_rows = list(
        db.scalars(
            select(QuitConOperacao)
            .where(
                QuitConOperacao.organization_id == user.organization_id,
                QuitConOperacao.status.in_(TAPAF_PENDING_QUITCON),
            )
            .order_by(QuitConOperacao.created_at.desc())
        )
    )
    for operacao in quitcon_rows:
        rows.append(
            _view(
                charge_id=f"tapaf-qc-{operacao.id}",
                charge_number=f"TAPAF-{operacao.operacao_code}",
                kind="TAPAF",
                description=f"TAPAF QuitCon — {operacao.operacao_code}",
                due_date=today,
                total_amount=TAPAF_NOMINAL,
                paid_amount=Decimal("0"),
                status="CHECKOUT_ACCEPTED" if operacao.status == "TAPAF_CHECKOUT_ACCEPTED" else "OPEN",
                source="TAPAF_CHECKOUT",
                reference_type="quitcon_operacao",
                reference_id=operacao.id,
                payment_checkout_url=None,
                payable=operacao.status == "TAPAF_CHECKOUT_ACCEPTED",
                created_at=operacao.created_at,
            )
        )

    lease_rows = list(
        db.scalars(
            select(LeaseEquityPauta)
            .where(
                LeaseEquityPauta.organization_id == user.organization_id,
                LeaseEquityPauta.status.in_(TAPAF_PENDING_LEASE),
            )
            .order_by(LeaseEquityPauta.created_at.desc())
        )
    )
    for pauta in lease_rows:
        rows.append(
            _view(
                charge_id=f"tapaf-le-{pauta.id}",
                charge_number=f"TAPAF-{pauta.pauta_code}",
                kind="TAPAF",
                description=f"TAPAF Lease Equity — {pauta.pauta_code}",
                due_date=today,
                total_amount=LEASE_EQUITY_TAPAF_NOMINAL,
                paid_amount=Decimal("0"),
                status="OPEN",
                source="TAPAF_CHECKOUT",
                reference_type="lease_equity_pauta",
                reference_id=pauta.id,
                payment_checkout_url=None,
                payable=False,
                created_at=pauta.created_at,
            )
        )
    return rows


def _settled_tapaf_views(db: Session, user: User, limit: int = 50) -> list[dict]:
    rows: list[dict] = []
    for item in list_settlements(db, user, limit=limit):
        created = item.get("created_at")
        due = date.today()
        if created:
            try:
                due = datetime.fromisoformat(str(created)).date()
            except ValueError:
                pass
        rows.append(
            _view(
                charge_id=f"tapaf-settled-{item['id']}",
                charge_number=f"TAPAF-{item['entity_type'][:8].upper()}-{item['entity_id'][:8].upper()}",
                kind="TAPAF",
                description=f"TAPAF liquidada — {item['entity_type']}",
                due_date=due,
                total_amount=Decimal(str(item["total_brl"])),
                paid_amount=Decimal(str(item["total_brl"])),
                status="PAID",
                source="TAPAF_SETTLEMENT",
                reference_type=item["entity_type"],
                reference_id=item["entity_id"],
                payment_checkout_url=None,
                payable=False,
                created_at=datetime.fromisoformat(str(created)) if created else None,
            )
        )
    return rows


def list_ad_hoc_charges(db: Session, user: User) -> list[dict]:
    manual_rows = list(
        db.scalars(
            select(StandaloneCharge)
            .where(StandaloneCharge.organization_id == user.organization_id)
            .order_by(StandaloneCharge.due_date.desc(), StandaloneCharge.created_at.desc())
        )
    )
    rows = _standalone_views(manual_rows) + _pending_tapaf_views(db, user) + _settled_tapaf_views(db, user)
    rows.sort(key=lambda row: (row["due_date"], row["charge_number"]), reverse=True)
    return rows
