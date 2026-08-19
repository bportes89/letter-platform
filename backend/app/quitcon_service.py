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
    credit = engine.processar_matriz_credito_ltv(item.property_type, item.appraisal_value)
    captured = money(item.funding_captured_amount)
    target = money(item.funding_target_amount or Decimal(str(credit["limite_teto_ltv_captacao"])))
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
        "credit_matrix": credit,
        "penalty_preview": penalty_preview,
        "tokenization_json": json.loads(item.tokenization_json) if item.tokenization_json else None,
        "created_at": item.created_at,
        "updated_at": item.updated_at,
    }


def create_operacao(
    db: Session,
    user: User,
    proposal: Proposal,
    *,
    property_type: str,
    appraisal_value,
    outstanding_balance,
    registry_number: str,
    registry_office: str,
    quota_id: str | None = None,
    owner_user_id: str | None = None,
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
    credit = engine.processar_matriz_credito_ltv(property_type, appraisal_value)
    saldo = money(outstanding_balance)
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
        appraisal_value=money(appraisal_value),
        outstanding_balance=saldo,
        registry_number=registry_number,
        registry_office=registry_office,
        funding_target_amount=Decimal(str(credit["limite_teto_ltv_captacao"])),
        success_fee_escrow_amount=engine.calcular_taxa_sucesso_escrow(saldo),
        sla_estimated_completion_at=now + timedelta(days=engine.sla_dias_estimados),
    )
    db.add(item)
    db.flush()
    _log_transition(db, item, user, "NEW", "AGUARDANDO_TAPAF", "Lead consórcio — checkout TAPAF R$ 1.500,00")
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


def register_inspection_photos(db: Session, user: User, operacao: QuitConOperacao, photos: list[dict]) -> QuitConOperacao:
    if operacao.status != "TAPAF_LIQUIDADA":
        raise HTTPException(status_code=409, detail="Vistoria disponível após TAPAF_LIQUIDADA")
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


def register_administrator_approval(db: Session, user: User, operacao: QuitConOperacao) -> QuitConOperacao:
    if operacao.status not in {
        "AGUARDANDO_ASSINATURA", "PRONTO_PARA_CARTORIO", "EM_ANALISE_NO_RGI",
        "GRAVAME_CONCLUIDO", "ATIVO_OK_EM_PRODUCAO", "LIBERADO_PARA_ANTECIPACAO",
    }:
        raise HTTPException(status_code=409, detail="Aprovação administradora indisponível neste status")
    if not operacao.administrator_approved_at:
        operacao.administrator_approved_at = datetime.now(UTC)
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
    credit = engine.processar_matriz_credito_ltv(operacao.property_type, operacao.appraisal_value)
    ltv_amount = Decimal(credit["limite_teto_ltv_captacao"])
    pool_cost = Decimal(credit["custo_mensal_remuneracao_pool_investidores"])
    rwa = engine.gerar_fracionamento_securitizado_rwa(ltv_amount, operacao.operacao_code)
    payload = {
        "endpoint": "/api/v1/finops/quitcon/tokenization-processor",
        "status": "SUCCESS",
        "data": {
            "contrato_id": operacao.operacao_code,
            "proprietario_uid": owner_uid or f"USER_PF_{operacao.owner_user_id[:8].upper()}",
            "colateral_imobiliario": {
                "matricula_numero": operacao.registry_number,
                "comarca_cartorio_rgi": operacao.registry_office,
                "tipo_bem": operacao.property_type,
                "valor_avaliacao_homologado": float(operacao.appraisal_value),
                "saldo_devedor_bruto": float(operacao.outstanding_balance),
            },
            "parametrizacao_finops_mesa": {
                "ltv_captacao_percent": float(credit["ltv_percent"]),
                "ltv_alavancagem_teto": float(ltv_amount),
                "custo_mensal_pool_investment_1_6_porcento": float(pool_cost),
                "taxa_sucesso_escrow_10_porcento": float(operacao.success_fee_escrow_amount),
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
