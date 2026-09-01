import hashlib
import json
from datetime import UTC, datetime, timedelta
from decimal import Decimal, ROUND_HALF_UP
from uuid import uuid4

from fastapi import HTTPException, status
from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.core.config import settings
from app.models import (
    AuditLog, CalculationMemory, Contract, Lead, LedgerEntry, LedgerTransaction,
    Operation, Proposal, Quota, QuotaReservation, User,
)


MODULES = [
    ("identity", "Identidade e organizações", "Usuários, organizações, KYC/KYB e consentimentos", "FOUNDATION", "/identity", True),
    ("rbac", "RBAC e segurança", "Papéis, escopos, MFA, sessões e auditoria", "FOUNDATION", "/security", True),
    ("crm", "CRM e originação", "Leads, parceiros, funil e prevenção de bypass", "ACTIVE", "/leads", False),
    ("administrators", "Administradoras", "Homologação e regras versionadas", "ACTIVE", "/administrators", False),
    ("inventory", "Cotas e inventário", "Estoque, reservas, locks e seleção", "ACTIVE", "/quotas", True),
    ("nina", "NINA Engine", "Combinação, underwriting, contingência e automações", "ACTIVE", "/nina", True),
    ("structured-properties", "Imóveis estruturados", "LTV 40%, interveniente quitante, payout em fases e averbação", "ACTIVE", "/structured-properties", True),
    ("lss", "LETTER Servicing Suite", "Licença SaaS, aceite versionado, recorrência e servicing", "ACTIVE", "/lss", True),
    ("proposals", "Propostas e simulações", "Price, Bullet, fees e memória de cálculo", "ACTIVE", "/proposals", True),
    ("finops", "FinOps e quitação", "Cenários Price/IPCA, balão, quitação antecipada e eventos assinados", "ACTIVE", "/finops", True),
    ("contracts", "Contratos e documentos", "Templates, assinatura e evidências", "FOUNDATION", "/contracts", True),
    ("payments", "Pagamentos e escrow", "Pix, locks, payouts, estornos e conciliação", "ADAPTER_REQUIRED", "/payments", True),
    ("my-wallet", "Minha Carteira", "Dados bancários Asaas, Pix, extrato, KYC e pagamentos", "ACTIVE", "/my-wallet", False),
    ("wallet", "Wallet e ledger", "Razão de dupla entrada, saldos e extratos", "FOUNDATION", "/wallet", True),
    ("funding", "Funding e investimentos", "Oportunidades, reservas, posições e resgates", "ACTIVE", "/investments", True),
    ("collections", "Cobrança e inadimplência", "Faturas, régua, mora e recuperação", "ACTIVE", "/collections", True),
    ("mmn", "Rede e comissões", "Árvores de venda/captação e cinco níveis", "ACTIVE", "/network", True),
    ("taxtech", "TaxTech", "NFS-e, conferência fiscal e payout", "ACTIVE", "/taxtech", True),
    ("auctions", "Leilões", "Ativos, gated content, waterfall e liquidação", "ACTIVE", "/auctions", True),
    ("communications", "Comunicações", "WhatsApp, e-mail, push e opt-out", "ACTIVE", "/communications", False),
    ("reports", "BI e relatórios", "Funil, carteira, risco, receita e auditoria", "ACTIVE", "/reports", False),
    ("operations", "Operações e observabilidade", "Jobs, retries, readiness, métricas e incidentes", "ACTIVE", "/operations", True),
    ("admin", "Backoffice", "Configurações, filas, aprovações e suporte", "ACTIVE", "/admin", True),
]


def audit(db: Session, user: User, action: str, entity_type: str, entity_id: str | None, metadata: dict | None = None):
    db.add(AuditLog(
        organization_id=user.organization_id,
        actor_id=user.id,
        action=action,
        entity_type=entity_type,
        entity_id=entity_id,
        metadata_json=json.dumps(metadata or {}, ensure_ascii=False),
    ))


def dashboard_summary(db: Session, user: User) -> dict:
    org = user.organization_id
    count = lambda model, *filters: db.scalar(select(func.count()).select_from(model).where(model.organization_id == org, *filters)) or 0
    return {
        "leads": count(Lead),
        "available_quotas": count(Quota, Quota.status == "AVAILABLE"),
        "active_proposals": count(Proposal, Proposal.status.notin_(["CANCELLED", "EXPIRED"])),
        "active_operations": count(Operation, Operation.status.notin_(["CLOSED", "CANCELLED"])),
        "modules": len(MODULES),
        "financial_transactions_enabled": settings.financial_transactions_enabled,
    }


def validate_quota_combination(quotas: list[Quota], target_amount: float, db: Session | None = None, user_id: str | None = None) -> dict:
    if not quotas:
        raise HTTPException(status_code=422, detail="Selecione ao menos uma cota")
    administrator_ids = {q.administrator_id for q in quotas}
    categories = {q.category for q in quotas}
    if len(administrator_ids) != 1:
        raise HTTPException(status_code=422, detail="As cotas devem pertencer à mesma administradora")
    if len(categories) != 1:
        raise HTTPException(status_code=422, detail="As cotas devem pertencer à mesma categoria")
    for quota in quotas:
        if quota.status == "AVAILABLE":
            continue
        if quota.status == "RESERVED" and db is not None and user_id:
            from app.quota_inventory_service import quota_available_for_user

            if quota_available_for_user(db, quota, user_id):
                continue
        raise HTTPException(status_code=409, detail="Uma ou mais cotas não estão disponíveis")
    total = sum(float(q.credit_value) for q in quotas)
    deviation = ((total - target_amount) / target_amount) * 100 if target_amount else 0
    return {
        "valid": abs(deviation) <= 10,
        "total_credit": total,
        "target_amount": target_amount,
        "deviation_percent": round(deviation, 2),
        "category": quotas[0].category,
        "administrator_id": quotas[0].administrator_id,
    }


def utcnow() -> datetime:
    return datetime.now(UTC)


def release_expired_reservations(db: Session, organization_id: str) -> int:
    now = utcnow()
    expired = list(db.scalars(select(QuotaReservation).where(
        QuotaReservation.organization_id == organization_id,
        QuotaReservation.status == "ACTIVE",
        QuotaReservation.expires_at <= now,
    )))
    for reservation in expired:
        reservation.status = "EXPIRED"
        reservation.released_at = now
        reservation.release_reason = "TTL_EXPIRED"
        quota = db.get(Quota, reservation.quota_id)
        if quota and quota.status == "RESERVED":
            quota.status = "AVAILABLE"
            quota.nina_scan_status = None
            quota.nina_scanned_at = None
    return len(expired)


def reserve_quota(db: Session, user: User, quota: Quota, proposal_id: str | None, ttl_minutes: int) -> QuotaReservation:
    from app.quota_inventory_service import ensure_nina_scan_before_lock

    release_expired_reservations(db, user.organization_id)
    db.flush()
    active = db.scalar(select(QuotaReservation).where(
        QuotaReservation.quota_id == quota.id,
        QuotaReservation.status == "ACTIVE",
        QuotaReservation.expires_at > utcnow(),
    ))
    if active or quota.status != "AVAILABLE":
        raise HTTPException(status_code=409, detail="Cota indisponível ou já reservada")
    ensure_nina_scan_before_lock(quota)
    if proposal_id:
        proposal = db.scalar(select(Proposal).where(
            Proposal.id == proposal_id, Proposal.organization_id == user.organization_id,
        ))
        if not proposal:
            raise HTTPException(status_code=404, detail="Proposta não encontrada")
    reservation = QuotaReservation(
        organization_id=user.organization_id,
        quota_id=quota.id,
        reserved_by_id=user.id,
        proposal_id=proposal_id,
        expires_at=utcnow() + timedelta(minutes=ttl_minutes),
    )
    quota.status = "RESERVED"
    db.add(reservation)
    return reservation


def release_reservation(db: Session, user: User, reservation: QuotaReservation, reason: str = "MANUAL_RELEASE") -> None:
    if reservation.status != "ACTIVE":
        raise HTTPException(status_code=409, detail="Reserva não está ativa")
    reservation.status = "RELEASED"
    reservation.released_at = utcnow()
    reservation.release_reason = reason
    quota = db.get(Quota, reservation.quota_id)
    if quota and quota.organization_id == user.organization_id:
        quota.status = "AVAILABLE"
        if reason in {"MANUAL_RELEASE", "TTL_EXPIRED"}:
            quota.nina_scan_status = None
            quota.nina_scanned_at = None


def money(value: Decimal) -> Decimal:
    return value.quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)


def calculate_marketplace(db: Session, user: User, proposal: Proposal, quotas: list[Quota], fee_percent: Decimal, start_fee: Decimal) -> CalculationMemory:
    validated = validate_quota_combination(quotas, float(proposal.requested_amount), db=db, user_id=user.id)
    if not validated["valid"]:
        raise HTTPException(status_code=422, detail=f"Combinação fora da tolerância de ±10%: {validated['deviation_percent']}%")
    credit_total = money(sum((Decimal(str(q.credit_value)) for q in quotas), Decimal("0")))
    premium_total = money(sum((Decimal(str(q.premium_value)) for q in quotas), Decimal("0")))
    platform_fee = money(credit_total * fee_percent / Decimal("100"))
    total_due = money(premium_total + platform_fee + start_fee)
    current_version = db.scalar(select(func.max(CalculationMemory.version)).where(CalculationMemory.proposal_id == proposal.id)) or 0
    input_data = {"quota_ids": [q.id for q in quotas], "fee_percent": str(fee_percent), "start_fee": str(start_fee)}
    output_data = {
        "credit_total": str(credit_total), "premium_total": str(premium_total),
        "platform_fee": str(platform_fee), "start_fee": str(money(start_fee)),
        "total_due": str(total_due), "deviation_percent": validated["deviation_percent"],
        "category": validated["category"], "administrator_id": validated["administrator_id"],
    }
    calculation = CalculationMemory(
        organization_id=user.organization_id, proposal_id=proposal.id, version=current_version + 1,
        product=proposal.product, input_json=json.dumps(input_data), output_json=json.dumps(output_data),
        formula_version="marketplace-v1",
    )
    db.add(calculation)
    proposal.calculation_version = f"marketplace-v1.{current_version + 1}"
    proposal.terms_json = json.dumps({**json.loads(proposal.terms_json or "{}"), "calculation": output_data}, ensure_ascii=False)
    return calculation


def create_contract(db: Session, user: User, proposal: Proposal, calculation: CalculationMemory) -> Contract:
    from app.quota_inventory_service import mark_quotas_sold_from_calculation

    existing = db.scalar(select(Contract).where(Contract.proposal_id == proposal.id))
    if existing:
        raise HTTPException(status_code=409, detail="Já existe contrato para esta proposta")
    if calculation.proposal_id != proposal.id:
        raise HTTPException(status_code=422, detail="Memória de cálculo não pertence à proposta")
    number = f"LTR-{utcnow().strftime('%Y%m')}-{uuid4().hex[:8].upper()}"
    source = f"{number}|{proposal.id}|{calculation.id}|{calculation.output_json}|{calculation.formula_version}"
    contract = Contract(
        organization_id=user.organization_id, proposal_id=proposal.id,
        calculation_memory_id=calculation.id, contract_number=number,
        template_version=calculation.formula_version,
        content_hash=hashlib.sha256(source.encode()).hexdigest(),
    )
    proposal.status = "CONTRACT_DRAFTED"
    db.add(contract)
    mark_quotas_sold_from_calculation(db, calculation)
    return contract


def post_double_entry(db: Session, user: User, *, reference: str, event_type: str, description: str, debit_account: str, credit_account: str, amount: Decimal, operation_id: str | None = None) -> LedgerTransaction:
    if debit_account == credit_account:
        raise HTTPException(status_code=422, detail="Contas de débito e crédito devem ser diferentes")
    transaction = LedgerTransaction(
        organization_id=user.organization_id, operation_id=operation_id, event_type=event_type,
        reference=reference, description=description,
    )
    db.add(transaction)
    try:
        db.flush()
    except IntegrityError:
        db.rollback()
        raise HTTPException(status_code=409, detail="Referência contábil já processada")
    value = money(amount)
    db.add_all([
        LedgerEntry(organization_id=user.organization_id, transaction_id=transaction.id, operation_id=operation_id, account=debit_account, direction="DEBIT", amount=value, reference=reference),
        LedgerEntry(organization_id=user.organization_id, transaction_id=transaction.id, operation_id=operation_id, account=credit_account, direction="CREDIT", amount=value, reference=reference),
    ])
    return transaction


def generate_valid_stamp(operation: Operation) -> str:
    source = f"{operation.id}|{operation.proposal_id}|{operation.amount}|{datetime.now(UTC).isoformat()}"
    return hashlib.sha256(source.encode()).hexdigest()


def financial_guard():
    if not settings.financial_transactions_enabled:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Transações financeiras estão bloqueadas até a homologação do fornecedor BaaS/escrow",
        )
