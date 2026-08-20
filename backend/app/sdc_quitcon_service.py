"""Ponte SDC → esteira QuitCon: simulação com confirmação abre operação AGUARDANDO_TAPAF."""

import json
from decimal import Decimal

from fastapi import HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import Administrator, CalculationMemory, Contract, Proposal, Quota, QuitConOperacao, User
from app.quitcon_engine import EngineQuitConLetter
from app.quitcon_service import create_operacao, generate_tapaf_checkout


def _load_calculation(
    db: Session,
    user: User,
    *,
    proposal: Proposal,
    calculation_memory_id: str | None,
    contract: Contract | None,
) -> CalculationMemory:
    calc_id = calculation_memory_id or (contract.calculation_memory_id if contract else None)
    if calc_id:
        calc = db.scalar(
            select(CalculationMemory).where(
                CalculationMemory.id == calc_id,
                CalculationMemory.organization_id == user.organization_id,
                CalculationMemory.proposal_id == proposal.id,
            )
        )
        if not calc:
            raise HTTPException(status_code=404, detail="Memória de cálculo SDC não encontrada")
        return calc
    calc = db.scalar(
        select(CalculationMemory)
        .where(
            CalculationMemory.proposal_id == proposal.id,
            CalculationMemory.organization_id == user.organization_id,
        )
        .order_by(CalculationMemory.version.desc())
    )
    if not calc:
        raise HTTPException(status_code=422, detail="Simule o SDC antes de iniciar QuitCon")
    return calc


def resolve_sdc_quitcon_context(
    db: Session,
    user: User,
    *,
    proposal_id: str | None,
    contract_id: str | None,
    calculation_memory_id: str | None,
    meses_restantes: int | None,
) -> tuple[Proposal, CalculationMemory, Decimal, int, str | None, str, str, str]:
    contract: Contract | None = None
    if contract_id:
        contract = db.scalar(
            select(Contract).where(
                Contract.id == contract_id,
                Contract.organization_id == user.organization_id,
            )
        )
        if not contract:
            raise HTTPException(status_code=404, detail="Contrato não encontrado")
        if not contract.template_version.startswith("sdc-"):
            raise HTTPException(status_code=422, detail="Contrato não é SDC")
        proposal_id = contract.proposal_id

    if not proposal_id:
        raise HTTPException(status_code=422, detail="Informe proposal_id ou contract_id")

    proposal = db.scalar(
        select(Proposal).where(
            Proposal.id == proposal_id,
            Proposal.organization_id == user.organization_id,
        )
    )
    if not proposal:
        raise HTTPException(status_code=404, detail="Proposta não encontrada")
    if proposal.product != "SDC":
        raise HTTPException(status_code=422, detail="QuitCon via SDC exige proposta SDC")

    calculation = _load_calculation(db, user, proposal=proposal, calculation_memory_id=calculation_memory_id, contract=contract)
    if not calculation.formula_version.startswith("sdc-"):
        raise HTTPException(status_code=422, detail="Memória de cálculo não é SDC")

    output = json.loads(calculation.output_json)
    input_data = json.loads(calculation.input_json)
    saldo_raw = output.get("maturity_total") or output.get("principal")
    if not saldo_raw:
        raise HTTPException(status_code=422, detail="Saldo devedor SDC indisponível na memória de cálculo")

    meses = meses_restantes
    if meses is None:
        meses = output.get("duration_months") or input_data.get("duration_months")
    if meses is None:
        raise HTTPException(status_code=422, detail="Prazo SDC indisponível para projeção QuitCon")

    quota_ids = input_data.get("quota_ids") or []
    quota_id = quota_ids[0] if quota_ids else None
    registry_number = f"SDC-{proposal.id[:8].upper()}"
    registry_office = "Administradora — confirmar na TAPAF"
    property_type = "CONSORCIO"

    if quota_id:
        quota = db.scalar(
            select(Quota).where(
                Quota.id == quota_id,
                Quota.organization_id == user.organization_id,
            )
        )
        if quota:
            admin = db.get(Administrator, quota.administrator_id)
            registry_number = f"{quota.group_code}/{quota.quota_code}"
            registry_office = admin.name if admin else registry_office
            property_type = "REAL_ESTATE" if quota.category == "REAL_ESTATE" else "VEHICLE"

    return proposal, calculation, Decimal(str(saldo_raw)), int(meses), quota_id, registry_number, registry_office, property_type


def start_quitcon_from_sdc(
    db: Session,
    user: User,
    *,
    proposal_id: str | None,
    contract_id: str | None,
    calculation_memory_id: str | None,
    meses_restantes: int | None,
) -> dict:
    proposal, calculation, saldo, meses, quota_id, registry_number, registry_office, property_type = resolve_sdc_quitcon_context(
        db,
        user,
        proposal_id=proposal_id,
        contract_id=contract_id,
        calculation_memory_id=calculation_memory_id,
        meses_restantes=meses_restantes,
    )

    engine = EngineQuitConLetter()
    quitcon_sdc = engine.gerar_integracao_sdc_quitcon(saldo, meses)

    existing = db.scalar(
        select(QuitConOperacao).where(
            QuitConOperacao.organization_id == user.organization_id,
            QuitConOperacao.proposal_id == proposal.id,
        )
    )
    if existing:
        return {
            "created": False,
            "operacao_id": existing.id,
            "operacao_code": existing.operacao_code,
            "status": existing.status,
            "quitcon_sdc": quitcon_sdc,
            "tapaf_checkout": generate_tapaf_checkout(existing),
            "next_step": "TAPAF_CHECKOUT",
            "finops_route": "/modules/finops",
            "message": "Operação QuitCon já aberta para esta proposta SDC.",
        }

    operacao = create_operacao(
        db,
        user,
        proposal,
        outstanding_balance=saldo,
        registry_number=registry_number,
        registry_office=registry_office,
        property_type=property_type,
        appraisal_value=saldo,
        quota_id=quota_id,
        owner_user_id=user.id,
        meses_restantes=meses,
        operational_service=False,
        contemplada=True,
        bem_faturado=True,
        parcelas_em_dia=True,
    )
    vp = quitcon_sdc["card"]["quitacao_vista_quitcon_vp"]
    operacao.compliance_blockers_json = json.dumps(
        {
            "origem": "SDC_QUITCON_SIMULADOR",
            "calculation_memory_id": calculation.id,
            "contract_id": contract_id,
            "saldo_devedor_bruto": str(saldo),
            "quitacao_vista_vp": vp,
            "meses_restantes_referencia": meses,
        },
        ensure_ascii=False,
    )

    return {
        "created": True,
        "operacao_id": operacao.id,
        "operacao_code": operacao.operacao_code,
        "status": operacao.status,
        "quitcon_sdc": quitcon_sdc,
        "tapaf_checkout": generate_tapaf_checkout(operacao),
        "next_step": "TAPAF_CHECKOUT",
        "finops_route": "/modules/finops",
        "message": "Operação QuitCon aberta — prossiga com TAPAF R$ 1.500,00.",
    }
