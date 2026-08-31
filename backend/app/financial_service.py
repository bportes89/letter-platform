import json
from datetime import UTC, datetime
from decimal import Decimal
from uuid import uuid4

from fastapi import HTTPException
from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.models import (
    ChartAccount, EscrowAccount, EscrowEvent, LedgerEntry, PayoutApproval,
    PayoutRequest, User,
)
from app.schemas import EscrowSubaccountProfile
from app.services import money, post_double_entry

DEFAULT_ACCOUNTS = [
    ("ESCROW_CASH", "Disponibilidades em escrow", "ASSET", "DEBIT"),
    ("ESCROW_LOCKED", "Recursos bloqueados em escrow", "ASSET", "DEBIT"),
    ("CLIENT_FUNDS_PAYABLE", "Recursos de clientes a liquidar", "LIABILITY", "CREDIT"),
    ("SELLER_PAYABLE", "Valores a pagar a vendedores", "LIABILITY", "CREDIT"),
    ("PLATFORM_FEE_REVENUE", "Receita de fee da plataforma", "REVENUE", "CREDIT"),
    ("PROCESSING_EXPENSE", "Despesas de processamento", "EXPENSE", "DEBIT"),
]


def ensure_chart(db: Session, user: User):
    existing = set(db.scalars(select(ChartAccount.code).where(ChartAccount.organization_id == user.organization_id)))
    for code, name, account_type, normal in DEFAULT_ACCOUNTS:
        if code not in existing:
            db.add(ChartAccount(organization_id=user.organization_id, code=code, name=name, account_type=account_type, normal_balance=normal))


def account_balances(db: Session, user: User) -> list[dict]:
    ensure_chart(db, user); db.flush()
    accounts = list(db.scalars(select(ChartAccount).where(ChartAccount.organization_id == user.organization_id, ChartAccount.active.is_(True)).order_by(ChartAccount.code)))
    result = []
    for account in accounts:
        debit = Decimal(str(db.scalar(select(func.coalesce(func.sum(LedgerEntry.amount), 0)).where(LedgerEntry.organization_id == user.organization_id, LedgerEntry.account == account.code, LedgerEntry.direction == "DEBIT")) or 0))
        credit = Decimal(str(db.scalar(select(func.coalesce(func.sum(LedgerEntry.amount), 0)).where(LedgerEntry.organization_id == user.organization_id, LedgerEntry.account == account.code, LedgerEntry.direction == "CREDIT")) or 0))
        balance = debit-credit if account.normal_balance == "DEBIT" else credit-debit
        result.append({"code":account.code,"name":account.name,"account_type":account.account_type,"balance":money(balance)})
    return result


def create_mock_escrow(
    db: Session,
    user: User,
    operation_id: str | None,
    *,
    create_subaccount: bool = True,
    enable_escrow: bool = True,
    profile: EscrowSubaccountProfile | None = None,
) -> EscrowAccount:
    from app.asaas_common import asaas_configured
    from app.asaas_escrow_service import create_asaas_escrow

    if asaas_configured() or create_subaccount:
        return create_asaas_escrow(
            db,
            user,
            operation_id,
            create_subaccount=create_subaccount,
            enable_escrow=enable_escrow,
            profile=profile,
        )

    if operation_id and db.scalar(select(EscrowAccount).where(EscrowAccount.operation_id == operation_id)):
        raise HTTPException(status_code=409, detail="Operação já possui conta vinculada")
    account = EscrowAccount(
        organization_id=user.organization_id,
        operation_id=operation_id,
        provider="MOCK",
        external_account_id=f"mock_escrow_{uuid4().hex}",
        escrow_enabled=enable_escrow,
    )
    db.add(account); ensure_chart(db,user); return account


def process_escrow_event(db: Session, user: User, account: EscrowAccount, event_id: str, event_type: str, amount: Decimal, metadata: dict) -> tuple[EscrowEvent, bool]:
    existing = db.scalar(select(EscrowEvent).where(EscrowEvent.provider_event_id == event_id))
    if existing: return existing, False
    if event_type != "FUNDS_CONFIRMED": raise HTTPException(status_code=422, detail="Evento simulado suportado: FUNDS_CONFIRMED")
    event = EscrowEvent(organization_id=user.organization_id, escrow_account_id=account.id, provider_event_id=event_id, event_type=event_type, amount=money(amount), payload_json=json.dumps(metadata))
    db.add(event)
    post_double_entry(db,user,reference=f"ESCROW:{event_id}",event_type=event_type,description="Entrada confirmada em escrow",debit_account="ESCROW_CASH",credit_account="CLIENT_FUNDS_PAYABLE",amount=amount,operation_id=account.operation_id)
    account.available_balance = money(Decimal(str(account.available_balance))+amount)
    return event, True


def mask_pix(value: str) -> str:
    clean=value.strip(); return f"***{clean[-4:]}" if len(clean)>4 else "****"


def create_payout(db: Session, user: User, account: EscrowAccount, *, beneficiary_name: str, beneficiary_document: str, pix_key: str, amount: Decimal, condition_evidence: dict) -> PayoutRequest:
    value=money(amount)
    if Decimal(str(account.available_balance)) < value: raise HTTPException(status_code=422, detail="Saldo escrow disponível insuficiente")
    if not condition_evidence: raise HTTPException(status_code=422, detail="Evidências das condições precedentes são obrigatórias")
    account.available_balance=money(Decimal(str(account.available_balance))-value);account.locked_balance=money(Decimal(str(account.locked_balance))+value)
    payout=PayoutRequest(organization_id=user.organization_id,escrow_account_id=account.id,requested_by_id=user.id,beneficiary_name=beneficiary_name,beneficiary_document=beneficiary_document,pix_key_masked=mask_pix(pix_key),amount=value,condition_evidence_json=json.dumps(condition_evidence))
    db.add(payout);db.flush()
    post_double_entry(db,user,reference=f"PAYOUT_LOCK:{payout.id}",event_type="PAYOUT_LOCKED",description="Bloqueio para payout",debit_account="ESCROW_LOCKED",credit_account="ESCROW_CASH",amount=value,operation_id=account.operation_id)
    return payout


def approve_payout(db: Session, user: User, payout: PayoutRequest, decision: str, comment: str | None) -> PayoutRequest:
    if payout.status not in {"PENDING_APPROVAL","PARTIALLY_APPROVED"}: raise HTTPException(status_code=409, detail="Payout não está aguardando aprovação")
    if payout.requested_by_id == user.id: raise HTTPException(status_code=403, detail="Solicitante não pode aprovar o próprio payout")
    if decision not in {"APPROVE","REJECT"}: raise HTTPException(status_code=422, detail="Decisão deve ser APPROVE ou REJECT")
    db.add(PayoutApproval(payout_request_id=payout.id,approver_id=user.id,decision=decision,comment=comment))
    try: db.flush()
    except IntegrityError: db.rollback(); raise HTTPException(status_code=409, detail="Usuário já decidiu este payout")
    account=db.get(EscrowAccount,payout.escrow_account_id);value=Decimal(str(payout.amount))
    if decision=="REJECT":
        payout.status="REJECTED";account.locked_balance=money(Decimal(str(account.locked_balance))-value);account.available_balance=money(Decimal(str(account.available_balance))+value)
        post_double_entry(db,user,reference=f"PAYOUT_UNLOCK:{payout.id}",event_type="PAYOUT_REJECTED",description="Desbloqueio de payout rejeitado",debit_account="ESCROW_CASH",credit_account="ESCROW_LOCKED",amount=value,operation_id=account.operation_id)
        return payout
    approvals=db.scalar(select(func.count()).select_from(PayoutApproval).where(PayoutApproval.payout_request_id==payout.id,PayoutApproval.decision=="APPROVE")) or 0
    payout.status="READY_FOR_PROVIDER" if approvals>=2 else "PARTIALLY_APPROVED"
    if approvals>=2: payout.provider_transaction_id=f"mock_ready_{uuid4().hex}"
    return payout
