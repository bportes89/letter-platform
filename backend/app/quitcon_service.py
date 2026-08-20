"""Esteira QuitCon — TAPAF R$ 1.500, multas doc252, SLA 45 dias e tokenização RWA."""

import json
from datetime import UTC, datetime, timedelta
from decimal import Decimal

from fastapi import HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import Proposal, QuitConOperacao, QuitConStatusLog, User
from app.quitcon_engine import EngineQuitConLetter, money
from app.storage_service import get_storage


VALID_TRANSITIONS = {
    "AGUARDANDO_TAPAF": {"TAPAF_LIQUIDADA"},
    "TAPAF_LIQUIDADA": {"EM_AUDITORIA_RISCO"},
    "EM_AUDITORIA_RISCO": {"REPROVADO_COMPLIANCE", "AGUARDANDO_ASSINATURA"},
    "AGUARDANDO_ASSINATURA": {"PRONTO_PARA_CARTORIO", "CANCELADO_DESISTENCIA_CEDENTE"},
    "PRONTO_PARA_CARTORIO": {"EM_ANALISE_NO_RGI", "CANCELADO_DESISTENCIA_CEDENTE"},
    "EM_ANALISE_NO_RGI": {"GRAVAME_CONCLUIDO", "CANCELADO_DESISTENCIA_CEDENTE"},
    "GRAVAME_CONCLUIDO": {"ATIVO_OK_EM_PRODUCAO", "CANCELADO_DESISTENCIA_CEDENTE", "CANCELADO_INADIMPLENCIA_CESSIONARIO"},
    "ATIVO_OK_EM_PRODUCAO": {"CANCELADO_INADIMPLENCIA_CESSIONARIO"},
}


def _log_transition(db: Session, operacao: QuitConOperacao, user: User, from_status: str, to_status: str, note: str = "") -> None:
    db.add(
        QuitConStatusLog(
            organization_id=operacao.organization_id,
            operacao_id=operacao.id,
            from_status=from_status,
            to_status=to_status,
            actor_id=user.id,
            note=note,
        )
    )


def _transition(db: Session, operacao: QuitConOperacao, user: User, to_status: str, note: str = "") -> None:
    allowed = VALID_TRANSITIONS.get(operacao.status, set())
    if to_status not in allowed and operacao.status != to_status:
        raise HTTPException(status_code=409, detail=f"Transição inválida: {operacao.status} → {to_status}")
    previous = operacao.status
    operacao.status = to_status
    _log_transition(db, operacao, user, previous, to_status, note)


def operacao_view(item: QuitConOperacao) -> dict:
    engine = EngineQuitConLetter()
    meses = item.meses_restantes or engine.prazos_projecao_meses[-1]
    finance = engine.processar_matriz_financeira(
        item.outstanding_balance,
        item.appraisal_value,
        meses_restantes=meses,
        operational_service=item.operational_service_enabled,
    )
    snapshot = json.loads(item.product_snapshot_json) if item.product_snapshot_json else None
    captured = money(item.funding_captured_amount)
    target = money(item.funding_target_amount or Decimal(str(finance["meta_captacao_quitacao"])))
    capture_pct = money(captured / target * 100) if target > 0 else money(0)
    penalty_preview = None
    if item.administrator_approved_at:
        penalty_preview = {
            "inadimplencia_cessionario": engine.calcular_multa_inadimplencia_cessionario(
                money(item.success_fee_escrow_amount)
            ),
            "desistencia_cedente": engine.calcular_multa_desistencia_cedente(
                money(item.outstanding_balance),
                money(item.inspection_cost_amount),
            ),
        }
    return {
        "id": item.id,
        "proposal_id": item.proposal_id,
        "quota_id": item.quota_id,
        "operacao_code": item.operacao_code,
        "status": item.status,
        "property_type": item.property_type,
        "appraisal_value": str(item.appraisal_value),
        "outstanding_balance": str(item.outstanding_balance),
        "registry_number": item.registry_number,
        "registry_office": item.registry_office,
        "tapaf_payment_reference": item.tapaf_payment_reference,
        "tapaf_paid_at": item.tapaf_paid_at,
        "compliance_dossier_uri": item.compliance_dossier_uri,
        "inspection_photos_count": item.inspection_photos_count,
        "administrator_approved_at": item.administrator_approved_at,
        "sla_estimated_completion_at": item.sla_estimated_completion_at,
        "sla_dias_estimados": EngineQuitConLetter.sla_dias_estimados,
        "success_fee_escrow_amount": str(item.success_fee_escrow_amount),
        "funding_captured_amount": str(captured),
        "funding_target_amount": str(target),
        "funding_capture_percent": str(capture_pct),
        "activation_at": item.activation_at,
        "activated_manually": item.activated_manually,
        "cancellation_reason": item.cancellation_reason,
        "penalty_amount": str(item.penalty_amount) if item.penalty_amount else None,
        "penalty_detail_json": json.loads(item.penalty_detail_json) if item.penalty_detail_json else None,
        "credit_matrix": finance,
        "penalty_preview": penalty_preview,
        "tokenization_json": json.loads(item.tokenization_json) if item.tokenization_json else None,
        "meses_restantes": meses,
        "quitacao_vp_amount": str(item.quitacao_vp_amount) if item.quitacao_vp_amount else finance.get("valor_presente_quitacao"),
        "operational_service_enabled": item.operational_service_enabled,
        "operational_service_fee_amount": str(item.operational_service_fee_amount) if item.operational_service_fee_amount else None,
        "operational_service_paid_at": item.operational_service_paid_at,
        "success_fee_escrow_paid_at": item.success_fee_escrow_paid_at,
        "success_fee_refunded": item.success_fee_refunded,
        "cedente_payment_amount": str(item.cedente_payment_amount) if item.cedente_payment_amount else None,
        "cedente_payment_due_at": item.cedente_payment_due_at,
        "cedente_payment_escrow_reference": item.cedente_payment_escrow_reference,
        "product_snapshot": snapshot,
        "created_at": item.created_at,
        "updated_at": item.updated_at,
    }


def create_operacao(
    db: Session,
    user: User,
    proposal: Proposal,
    *,
    outstanding_balance,
    registry_number: str,
    registry_office: str,
    property_type: str = "CONSORCIO",
    appraisal_value=None,
    quota_id: str | None = None,
    owner_user_id: str | None = None,
    meses_restantes: int = 48,
    operational_service: bool = False,
    contemplada: bool = True,
    bem_faturado: bool = True,
    parcelas_em_dia: bool = True,
) -> QuitConOperacao:
    existing = db.scalar(
        select(QuitConOperacao).where(
            QuitConOperacao.organization_id == user.organization_id,
            QuitConOperacao.proposal_id == proposal.id,
        )
    )
    if existing:
        return existing
    engine = EngineQuitConLetter()
    saldo = money(outstanding_balance)
    elegibilidade = engine.validar_elegibilidade_cedente(
        contemplada=contemplada,
        bem_faturado=bem_faturado,
        parcelas_em_dia=parcelas_em_dia,
        administrator_name=registry_office,
    )
    if not elegibilidade["elegivel"]:
        raise HTTPException(
            status_code=422,
            detail=f"Operação não elegível doc253: {', '.join(elegibilidade['blockers'])}",
        )
    snapshot = engine.simular_quitcon_doc253(
        saldo,
        meses_restantes,
        operational_service=operational_service,
        administrator_name=registry_office,
        contemplada=contemplada,
        bem_faturado=bem_faturado,
        parcelas_em_dia=parcelas_em_dia,
    )
    finance = engine.processar_matriz_financeira(
        saldo, appraisal_value or saldo, meses_restantes=meses_restantes, operational_service=operational_service,
    )
    vp = money(Decimal(str(snapshot["valor_presente_quitacao"])))
    code = f"LETTER_QUITCON_{proposal.id[:8].upper()}"
    now = datetime.now(UTC)
    item = QuitConOperacao(
        organization_id=user.organization_id,
        proposal_id=proposal.id,
        quota_id=quota_id,
        owner_user_id=owner_user_id or user.id,
        operacao_code=code,
        status="AGUARDANDO_TAPAF",
        property_type=property_type.upper(),
        appraisal_value=money(appraisal_value or saldo),
        outstanding_balance=saldo,
        registry_number=registry_number,
        registry_office=registry_office,
        meses_restantes=int(meses_restantes),
        quitacao_vp_amount=vp,
        operational_service_enabled=operational_service,
        operational_service_fee_amount=(
            engine.calcular_taxa_servico_operacional_inicio(vp) if operational_service else None
        ),
        funding_target_amount=Decimal(str(finance["meta_captacao_quitacao"])),
        success_fee_escrow_amount=engine.calcular_taxa_sucesso_escrow(vp),
        sla_estimated_completion_at=now + timedelta(days=engine.sla_dias_estimados),
        product_snapshot_json=json.dumps(snapshot, ensure_ascii=False),
    )
    db.add(item)
    db.flush()
    _log_transition(db, item, user, "NEW", "AGUARDANDO_TAPAF", "Lead consórcio doc253 — checkout TAPAF R$ 1.500,00")
    return item


def generate_tapaf_checkout(operacao: QuitConOperacao) -> dict:
    if operacao.status != "AGUARDANDO_TAPAF":
        raise HTTPException(status_code=409, detail="TAPAF disponível apenas em AGUARDANDO_TAPAF")
    amount = EngineQuitConLetter.taxa_tapaf_nominal
    return {
        "endpoint": "/api/v1/finops/quitcon/tapaf-checkout",
        "status": "READY",
        "valor_tapaf_brl": str(amount),
        "gateway_baas_pix_qrcode": f"00020101021126580014br.gov.bcb.pix0136letter-quitcon-tapaf-{operacao.id[:8]}",
        "status_operacao_db": "AGUARDANDO_TAPAF",
        "texto_tooltip": (
            "TAPAF QuitCon R$ 1.500,00 — taxa não reembolsável que cobre certidões, ONR e laudo AVM."
        ),
    }


def confirm_tapaf_payment(db: Session, user: User, operacao: QuitConOperacao, event_id: str, amount) -> QuitConOperacao:
    if operacao.status != "AGUARDANDO_TAPAF":
        raise HTTPException(status_code=409, detail="TAPAF já liquidada ou indisponível")
    if money(amount) != EngineQuitConLetter.taxa_tapaf_nominal:
        raise HTTPException(status_code=422, detail="Valor TAPAF deve ser exatamente R$ 1.500,00")
    operacao.tapaf_payment_reference = event_id
    operacao.tapaf_paid_at = datetime.now(UTC)
    _transition(db, operacao, user, "TAPAF_LIQUIDADA", "Pix liquidado BaaS D+0")
    dossier_key = f"company-vault/partners/{operacao.operacao_code}/compliance/dossie_higienizado.pdf"
    storage = get_storage()
    storage.put(dossier_key, b"%PDF-1.4\n% QuitCon compliance dossier sandbox\n", "application/pdf")
    operacao.compliance_dossier_uri = f"s3://letter-vault-private/{dossier_key}"
    db.flush()
    return operacao


def generate_operational_service_checkout(operacao: QuitConOperacao) -> dict:
    if not operacao.operational_service_enabled:
        raise HTTPException(status_code=409, detail="Serviço operacional LETTER não contratado")
    if operacao.operational_service_paid_at:
        raise HTTPException(status_code=409, detail="Taxa de serviço operacional já paga")
    amount = money(operacao.operational_service_fee_amount or 0)
    if amount <= 0:
        raise HTTPException(status_code=422, detail="Valor da taxa de serviço indisponível")
    return {
        "endpoint": "/api/v1/finops/quitcon/operational-service-payment-webhook",
        "status": "READY",
        "valor_taxa_servico_operacional_brl": str(amount),
        "momento_cobranca": "ABERTURA_PROCESSO",
        "gateway_baas_pix_qrcode": f"00020101021126580014br.gov.bcb.pix0136letter-quitcon-svc-{operacao.id[:8]}",
        "texto_tooltip": (
            "Taxa de serviço 2% sobre a quitação — paga na abertura quando a LETTER conduz o processo junto à administradora."
        ),
    }


def confirm_operational_service_payment(db: Session, user: User, operacao: QuitConOperacao, event_id: str, amount) -> QuitConOperacao:
    if operacao.status != "TAPAF_LIQUIDADA":
        raise HTTPException(status_code=409, detail="Taxa de serviço disponível após TAPAF_LIQUIDADA")
    if not operacao.operational_service_enabled:
        raise HTTPException(status_code=409, detail="Serviço operacional não contratado")
    expected = money(operacao.operational_service_fee_amount or 0)
    if money(amount) != expected:
        raise HTTPException(status_code=422, detail=f"Valor da taxa de serviço deve ser exatamente R$ {expected}")
    operacao.operational_service_paid_at = datetime.now(UTC)
    db.flush()
    return operacao


def generate_success_fee_checkout(operacao: QuitConOperacao) -> dict:
    if operacao.status != "TAPAF_LIQUIDADA":
        raise HTTPException(status_code=409, detail="Taxa de sucesso disponível após TAPAF_LIQUIDADA")
    if operacao.operational_service_enabled and not operacao.operational_service_paid_at:
        raise HTTPException(status_code=409, detail="Pague a taxa de serviço operacional 2% antes da taxa de sucesso")
    if operacao.success_fee_escrow_paid_at:
        raise HTTPException(status_code=409, detail="Taxa de sucesso já depositada em Escrow")
    amount = money(operacao.success_fee_escrow_amount)
    return {
        "endpoint": "/api/v1/finops/quitcon/success-fee-payment-webhook",
        "status": "READY",
        "valor_taxa_sucesso_brl": str(amount),
        "escrow_conta_protegida": True,
        "reembolso_integral_se_reprovado_adm": True,
        "gateway_baas_pix_qrcode": f"00020101021126580014br.gov.bcb.pix0136letter-quitcon-fee-{operacao.id[:8]}",
        "status_operacao_db": operacao.status,
        "texto_tooltip": (
            "Taxa de sucesso 10% sobre valor liberado — retida em Escrow e 100% devolvida se a administradora reprovar."
        ),
    }


def confirm_success_fee_payment(db: Session, user: User, operacao: QuitConOperacao, event_id: str, amount) -> QuitConOperacao:
    if operacao.status != "TAPAF_LIQUIDADA":
        raise HTTPException(status_code=409, detail="Depósito Escrow indisponível neste status")
    if operacao.operational_service_enabled and not operacao.operational_service_paid_at:
        raise HTTPException(status_code=409, detail="Taxa de serviço operacional 2% pendente")
    expected = money(operacao.success_fee_escrow_amount)
    if money(amount) != expected:
        raise HTTPException(status_code=422, detail=f"Valor da taxa de sucesso deve ser exatamente R$ {expected}")
    operacao.success_fee_escrow_reference = event_id
    operacao.success_fee_escrow_paid_at = datetime.now(UTC)
    db.flush()
    return operacao


def register_administrator_approval(db: Session, user: User, operacao: QuitConOperacao) -> QuitConOperacao:
    if operacao.status not in {
        "AGUARDANDO_ASSINATURA", "PRONTO_PARA_CARTORIO", "EM_ANALISE_NO_RGI",
        "GRAVAME_CONCLUIDO", "ATIVO_OK_EM_PRODUCAO", "LIBERADO_PARA_ANTECIPACAO",
    }:
        raise HTTPException(status_code=409, detail="Aprovação administradora indisponível neste status")
    if not operacao.administrator_approved_at:
        operacao.administrator_approved_at = datetime.now(UTC)
        vp = money(operacao.quitacao_vp_amount or operacao.outstanding_balance)
        engine = EngineQuitConLetter()
        operacao.cedente_payment_amount = engine.calcular_pagamento_total_cedente(vp)
        operacao.cedente_payment_due_at = datetime.now(UTC) + timedelta(
            hours=EngineQuitConLetter.prazo_deposito_quitacao_horas_uteis
        )
    db.flush()
    return operacao


def register_administrator_rejection(db: Session, user: User, operacao: QuitConOperacao, *, reason: str = "") -> QuitConOperacao:
    if operacao.success_fee_escrow_paid_at and not operacao.success_fee_refunded:
        operacao.success_fee_refunded = True
    operacao.cancellation_reason = "REPROVADO_ADMINISTRADORA"
    operacao.penalty_detail_json = json.dumps(
        {
            "tipo": "REPROVACAO_ADMINISTRADORA",
            "taxa_sucesso_reembolsada_integralmente": operacao.success_fee_refunded,
            "motivo": reason or "Cadastro ou garantia não aprovados",
        },
        ensure_ascii=False,
    )
    previous = operacao.status
    operacao.status = "REPROVADO_COMPLIANCE"
    _log_transition(db, operacao, user, previous, "REPROVADO_COMPLIANCE", "Administradora reprovou — Escrow devolvido 100%")
    db.flush()
    return operacao


def generate_cedente_payment_checkout(operacao: QuitConOperacao) -> dict:
    if not operacao.administrator_approved_at:
        raise HTTPException(status_code=409, detail="Pagamento cedente exige aprovação da administradora")
    if operacao.cedente_payment_escrow_reference:
        raise HTTPException(status_code=409, detail="Pagamento cedente já registrado em Escrow")
    if not operacao.cedente_payment_amount:
        raise HTTPException(status_code=422, detail="Valor de quitação cedente indisponível")
    amount = money(operacao.cedente_payment_amount)
    return {
        "endpoint": "/api/v1/finops/quitcon/cedente-payment-webhook",
        "status": "READY",
        "valor_quitacao_cedente_brl": str(amount),
        "escrow_retido_ate_conclusao": True,
        "prazo_limite": operacao.cedente_payment_due_at.isoformat() if operacao.cedente_payment_due_at else None,
        "gateway_baas_pix_qrcode": f"00020101021126580014br.gov.bcb.pix0136letter-quitcon-cedente-{operacao.id[:8]}",
    }


def confirm_cedente_payment_escrow(db: Session, user: User, operacao: QuitConOperacao, event_id: str, amount) -> QuitConOperacao:
    if not operacao.administrator_approved_at:
        raise HTTPException(status_code=409, detail="Pagamento cedente indisponível sem aprovação")
    expected = money(operacao.cedente_payment_amount or 0)
    if money(amount) != expected:
        raise HTTPException(status_code=422, detail=f"Valor de quitação deve ser exatamente R$ {expected}")
    operacao.cedente_payment_escrow_reference = event_id
    db.flush()
    return operacao


def register_inspection_photos(db: Session, user: User, operacao: QuitConOperacao, photos: list[dict]) -> QuitConOperacao:
    if operacao.status != "TAPAF_LIQUIDADA":
        raise HTTPException(status_code=409, detail="Vistoria disponível após TAPAF_LIQUIDADA")
    if operacao.operational_service_enabled and not operacao.operational_service_paid_at:
        raise HTTPException(status_code=409, detail="Pague a taxa de serviço operacional 2% antes da vistoria")
    if not operacao.success_fee_escrow_paid_at:
        raise HTTPException(status_code=409, detail="Deposite a taxa de sucesso 10% em Escrow antes da vistoria")
    from app.collateral_native_inspection_service import upsert_native_inspection

    upsert_native_inspection(
        db, user,
        product="QUITCON",
        proposal_id=operacao.proposal_id,
        photos=photos,
        quitcon_operacao_id=operacao.id,
    )
    operacao.inspection_photos_count = len(photos)
    operacao.inspection_metadata_json = json.dumps(photos, ensure_ascii=False)
    _transition(db, operacao, user, "EM_AUDITORIA_RISCO", "Vistoria fotográfica nativa concluída")
    db.flush()
    return operacao


def run_compliance_review(
    db: Session, user: User, operacao: QuitConOperacao, *, approved: bool, blockers: list[str] | None = None,
) -> QuitConOperacao:
    if operacao.status != "EM_AUDITORIA_RISCO":
        raise HTTPException(status_code=409, detail="Auditoria de risco indisponível neste status")
    if approved:
        _transition(db, operacao, user, "AGUARDANDO_ASSINATURA", "Certidões 100% limpas")
    else:
        operacao.compliance_blockers_json = json.dumps(blockers or ["GRAVAME_OU_PRENOTACAO"], ensure_ascii=False)
        _transition(db, operacao, user, "REPROVADO_COMPLIANCE", "Reprovação sumária compliance")
    db.flush()
    return operacao


def sign_contract(db: Session, user: User, operacao: QuitConOperacao) -> QuitConOperacao:
    if operacao.status != "AGUARDANDO_ASSINATURA":
        raise HTTPException(status_code=409, detail="Assinatura indisponível neste status")
    _transition(db, operacao, user, "PRONTO_PARA_CARTORIO", "Contrato assinado ICP-Brasil")
    db.flush()
    return operacao


def submit_registry_protocol(db: Session, user: User, operacao: QuitConOperacao) -> QuitConOperacao:
    if operacao.status != "PRONTO_PARA_CARTORIO":
        raise HTTPException(status_code=409, detail="Protocolo SERP indisponível neste status")
    _transition(db, operacao, user, "EM_ANALISE_NO_RGI", "Paralegal protocolou SERP/ONR")
    db.flush()
    return operacao


def complete_gravame(db: Session, user: User, operacao: QuitConOperacao, certificate_uri: str | None = None) -> QuitConOperacao:
    if operacao.status != "EM_ANALISE_NO_RGI":
        raise HTTPException(status_code=409, detail="Averbação indisponível neste status")
    operacao.gravame_certificate_uri = certificate_uri or f"s3://letter-vault-private/partners/{operacao.operacao_code}/registry/averbacao.pdf"
    _transition(db, operacao, user, "GRAVAME_CONCLUIDO", "Certidão de averbação ONR")
    db.flush()
    return operacao


def record_funding_capture(db: Session, user: User, operacao: QuitConOperacao, amount) -> QuitConOperacao:
    if operacao.status not in {"GRAVAME_CONCLUIDO", "ATIVO_OK_EM_PRODUCAO"}:
        raise HTTPException(status_code=409, detail="Captação indisponível neste status")
    operacao.funding_captured_amount = money(Decimal(str(operacao.funding_captured_amount)) + money(amount))
    target = money(operacao.funding_target_amount)
    threshold = money(target * EngineQuitConLetter.gatilho_captacao_minima_percent)
    if operacao.status == "GRAVAME_CONCLUIDO" and operacao.funding_captured_amount >= threshold:
        activate_ok(db, user, operacao, manual=False)
    db.flush()
    return operacao


def activate_ok(db: Session, user: User, operacao: QuitConOperacao, *, manual: bool = False) -> QuitConOperacao:
    if operacao.status != "GRAVAME_CONCLUIDO":
        raise HTTPException(status_code=409, detail="Ativação OK exige GRAVAME_CONCLUIDO")
    if not manual:
        target = money(operacao.funding_target_amount)
        threshold = money(target * EngineQuitConLetter.gatilho_captacao_minima_percent)
        if operacao.funding_captured_amount < threshold:
            raise HTTPException(status_code=409, detail="Captação mínima de 30% não atingida")
    operacao.activation_at = datetime.now(UTC)
    operacao.activated_manually = manual
    _transition(db, operacao, user, "ATIVO_OK_EM_PRODUCAO", "Gatilho OK — operação QuitCon em produção")
    db.flush()
    return operacao


def cancel_inadimplencia_cessionario(
    db: Session, user: User, operacao: QuitConOperacao, *, days_overdue: int,
) -> QuitConOperacao:
    if not operacao.administrator_approved_at:
        raise HTTPException(status_code=409, detail="Cancelamento por inadimplência exige aprovação da administradora")
    if days_overdue < EngineQuitConLetter.dias_inadimplencia_cancelamento:
        raise HTTPException(
            status_code=422,
            detail=f"Inadimplência deve exceder {EngineQuitConLetter.dias_inadimplencia_cancelamento} dias",
        )
    engine = EngineQuitConLetter()
    detail = engine.calcular_multa_inadimplencia_cessionario(money(operacao.success_fee_escrow_amount))
    operacao.cancellation_reason = detail["tipo"]
    operacao.penalty_amount = money(operacao.success_fee_escrow_amount)
    operacao.penalty_detail_json = json.dumps(detail, ensure_ascii=False)
    _transition(db, operacao, user, "CANCELADO_INADIMPLENCIA_CESSIONARIO", "Multa Escrow 10% retida integralmente")
    db.flush()
    return operacao


def cancel_desistencia_cedente(db: Session, user: User, operacao: QuitConOperacao) -> QuitConOperacao:
    if not operacao.administrator_approved_at:
        raise HTTPException(status_code=409, detail="Multa de desistência exige aprovação final da administradora")
    if operacao.status not in {
        "AGUARDANDO_ASSINATURA", "PRONTO_PARA_CARTORIO", "EM_ANALISE_NO_RGI", "GRAVAME_CONCLUIDO",
    }:
        raise HTTPException(status_code=409, detail="Desistência do cedente indisponível neste status")
    engine = EngineQuitConLetter()
    detail = engine.calcular_multa_desistencia_cedente(
        money(operacao.outstanding_balance),
        money(operacao.inspection_cost_amount),
    )
    operacao.cancellation_reason = detail["tipo"]
    operacao.penalty_amount = Decimal(detail["total_penalidades_cedente"])
    operacao.penalty_detail_json = json.dumps(detail, ensure_ascii=False)
    _transition(db, operacao, user, "CANCELADO_DESISTENCIA_CEDENTE", "Multa 10% saldo devedor + reembolso cessionário")
    db.flush()
    return operacao


def process_tokenization(operacao: QuitConOperacao, owner_uid: str | None = None) -> dict:
    if operacao.status not in {"GRAVAME_CONCLUIDO", "ATIVO_OK_EM_PRODUCAO"}:
        raise HTTPException(status_code=409, detail="Tokenização exige gravame concluído ou produção ativa")
    engine = EngineQuitConLetter()
    finance = engine.processar_matriz_financeira(
        operacao.outstanding_balance,
        operacao.appraisal_value,
        meses_restantes=operacao.meses_restantes,
        operational_service=operacao.operational_service_enabled,
    )
    lastro = Decimal(finance["meta_captacao_quitacao"])
    pool_cost = Decimal(finance["custo_mensal_remuneracao_pool_investidores"])
    rwa = engine.gerar_fracionamento_securitizado_rwa(lastro, operacao.operacao_code)
    payload = {
        "endpoint": "/api/v1/finops/quitcon/tokenization-processor",
        "status": "SUCCESS",
        "data": {
            "contrato_id": operacao.operacao_code,
            "proprietario_uid": owner_uid or f"USER_PF_{operacao.owner_user_id[:8].upper()}",
            "colateral_consorcio": {
                "matricula_ou_garantia": operacao.registry_number,
                "referencia_cartorio_ou_adm": operacao.registry_office,
                "tipo_operacao": operacao.property_type,
                "valor_avaliacao_referencia": float(operacao.appraisal_value),
                "saldo_devedor_bruto": float(operacao.outstanding_balance),
            },
            "parametrizacao_finops_mesa": {
                "meta_captacao_quitacao": float(lastro),
                "custo_mensal_pool_investment_1_6_porcento": float(pool_cost),
                "taxa_sucesso_escrow_10_porcento": float(operacao.success_fee_escrow_amount),
                "ltv_assimetrico_aplicavel": False,
                "remuneracao_proprietario_0_4_porcento": False,
            },
            "workflow_securitizacao_rwa": {
                "titulo_lastro_vinculado": "NOTA_COMERCIAL_PRIVADA_SERIE_QC01",
                "custo_emissao_bancaria_intermediada": 0.00,
                "averbacao_remota_status": "GRAVAME_CONCLUIDO_ONR",
                "tokenizacao_blockchain_metadata": {
                    "smart_contract_padrao": "ERC-3643_COMPLIANT_RWA",
                    "total_supply_tokens_emitidos": rwa["total_supply_tokens_mint"],
                    "valor_nominal_unitario_token": float(rwa["valor_face_unitario_token_brl"]),
                    "ticker_identificador_rede": f"QC-LT-{operacao.operacao_code.split('_')[-1][:4]}",
                    "distribuicao_rendimento_token_mensal": float(rwa["rendimento_mensal_unitario_smart_contract"]),
                },
            },
            "governanca_risco_doc252": {
                "sla_dias_estimados": engine.sla_dias_estimados,
                "sla_estimado_conclusao": operacao.sla_estimated_completion_at.isoformat() if operacao.sla_estimated_completion_at else None,
                "multa_inadimplencia_cessionario_percent": float(engine.multa_percentual * 100),
                "multa_desistencia_cedente_percent": float(engine.multa_percentual * 100),
            },
        },
    }
    operacao.tokenization_json = json.dumps(payload, ensure_ascii=False)
    return payload
