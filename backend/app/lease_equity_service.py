"""Esteira Lease Equity — TAPAF R$ 750, estados, compliance, tokenização RWA."""

import json
from datetime import UTC, datetime, timedelta
from decimal import Decimal

from fastapi import HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.lease_equity_engine import EngineLeaseEquityLetter, money
from app.models import LeaseEquityPauta, LeaseEquityStatusLog, Proposal, User
from app.storage_service import get_storage


VALID_TRANSITIONS = {
    "AGUARDANDO_TAPAF": {"TAPAF_LIQUIDADA"},
    "TAPAF_LIQUIDADA": {"EM_AUDITORIA_RISCO"},
    "EM_AUDITORIA_RISCO": {"REPROVADO_COMPLIANCE", "AGUARDANDO_ASSINATURA"},
    "AGUARDANDO_ASSINATURA": {"PRONTO_PARA_CARTORIO"},
    "PRONTO_PARA_CARTORIO": {"EM_ANALISE_NO_RGI"},
    "EM_ANALISE_NO_RGI": {"GRAVAME_CONCLUIDO"},
    "GRAVAME_CONCLUIDO": {"ATIVO_OK_EM_PRODUCAO"},
    "ATIVO_OK_EM_PRODUCAO": {"LIBERADO_PARA_ANTECIPACAO"},
}


def _log_transition(db: Session, pauta: LeaseEquityPauta, user: User, from_status: str, to_status: str, note: str = "") -> None:
    db.add(
        LeaseEquityStatusLog(
            organization_id=pauta.organization_id,
            pauta_id=pauta.id,
            from_status=from_status,
            to_status=to_status,
            actor_id=user.id,
            note=note,
        )
    )


def _transition(db: Session, pauta: LeaseEquityPauta, user: User, to_status: str, note: str = "") -> None:
    allowed = VALID_TRANSITIONS.get(pauta.status, set())
    if to_status not in allowed and pauta.status != to_status:
        raise HTTPException(
            status_code=409,
            detail=f"Transição inválida: {pauta.status} → {to_status}",
        )
    previous = pauta.status
    pauta.status = to_status
    _log_transition(db, pauta, user, previous, to_status, note)


def pauta_view(item: LeaseEquityPauta) -> dict:
    engine = EngineLeaseEquityLetter()
    credit = engine.processar_matriz_credito_ltv(item.property_type, item.appraisal_value)
    captured = money(item.funding_captured_amount)
    target = money(item.funding_target_amount or Decimal(str(credit["limite_teto_ltv_captacao"])))
    capture_pct = money(captured / target * 100) if target > 0 else money(0)
    anticipation = engine.calcular_antecipacao_recebiveis_price(
        Decimal(credit["aluguel_mensal_recorrente_bruto_dono"]),
        parcelas_restantes=36,
        meses_vigencia_atual=item.months_in_force,
    )
    return {
        "id": item.id,
        "proposal_id": item.proposal_id,
        "pauta_code": item.pauta_code,
        "status": item.status,
        "property_type": item.property_type,
        "appraisal_value": str(item.appraisal_value),
        "registry_number": item.registry_number,
        "registry_office": item.registry_office,
        "tapaf_payment_reference": item.tapaf_payment_reference,
        "tapaf_paid_at": item.tapaf_paid_at,
        "compliance_dossier_uri": item.compliance_dossier_uri,
        "inspection_photos_count": item.inspection_photos_count,
        "funding_captured_amount": str(captured),
        "funding_target_amount": str(target),
        "funding_capture_percent": str(capture_pct),
        "activation_at": item.activation_at,
        "activated_manually": item.activated_manually,
        "months_in_force": item.months_in_force,
        "anticipation_unlock_at": item.anticipation_unlock_at,
        "credit_matrix": credit,
        "anticipation_preview": anticipation,
        "tokenization_json": json.loads(item.tokenization_json) if item.tokenization_json else None,
        "created_at": item.created_at,
        "updated_at": item.updated_at,
    }


def create_pauta(
    db: Session,
    user: User,
    proposal: Proposal,
    *,
    property_type: str,
    appraisal_value,
    registry_number: str,
    registry_office: str,
    owner_user_id: str | None = None,
) -> LeaseEquityPauta:
    existing = db.scalar(
        select(LeaseEquityPauta).where(
            LeaseEquityPauta.organization_id == user.organization_id,
            LeaseEquityPauta.proposal_id == proposal.id,
        )
    )
    if existing:
        return existing
    engine = EngineLeaseEquityLetter()
    credit = engine.processar_matriz_credito_ltv(property_type, appraisal_value)
    code = f"LETTER_LEASE_EQ_{proposal.id[:8].upper()}"
    item = LeaseEquityPauta(
        organization_id=user.organization_id,
        proposal_id=proposal.id,
        owner_user_id=owner_user_id or user.id,
        pauta_code=code,
        status="AGUARDANDO_TAPAF",
        property_type=property_type.upper(),
        appraisal_value=money(appraisal_value),
        registry_number=registry_number,
        registry_office=registry_office,
        funding_target_amount=Decimal(str(credit["limite_teto_ltv_captacao"])),
    )
    db.add(item)
    db.flush()
    _log_transition(db, item, user, "NEW", "AGUARDANDO_TAPAF", "Lead imobiliário — checkout TAPAF R$ 750,00")
    return item


def generate_tapaf_checkout(pauta: LeaseEquityPauta) -> dict:
    if pauta.status != "AGUARDANDO_TAPAF":
        raise HTTPException(status_code=409, detail="TAPAF disponível apenas em AGUARDANDO_TAPAF")
    amount = EngineLeaseEquityLetter.taxa_tapaf_nominal
    return {
        "endpoint": "/api/v1/finops/lease-equity/tapaf-checkout",
        "status": "READY",
        "valor_tapaf_brl": str(amount),
        "gateway_baas_pix_qrcode": f"00020101021126580014br.gov.bcb.pix0136letter-lease-tapaf-{pauta.id[:8]}",
        "status_imovel_db": "AGUARDANDO_TAPAF",
        "texto_tooltip": (
            "TAPAF Lease Equity R$ 750,00 — taxa não reembolsável que cobre infraestrutura de compliance "
            "e montagem automática do dossiê de certidões."
        ),
    }


def confirm_tapaf_payment(db: Session, user: User, pauta: LeaseEquityPauta, event_id: str, amount) -> LeaseEquityPauta:
    if pauta.status != "AGUARDANDO_TAPAF":
        raise HTTPException(status_code=409, detail="TAPAF já liquidada ou indisponível")
    if money(amount) != EngineLeaseEquityLetter.taxa_tapaf_nominal:
        raise HTTPException(status_code=422, detail="Valor TAPAF deve ser exatamente R$ 750,00")
    pauta.tapaf_payment_reference = event_id
    pauta.tapaf_paid_at = datetime.now(UTC)
    _transition(db, pauta, user, "TAPAF_LIQUIDADA", "Pix liquidado BaaS D+0")
    dossier_key = f"company-vault/partners/{pauta.pauta_code}/compliance/dossie_higienizado.pdf"
    storage = get_storage()
    storage.put(
        dossier_key,
        b"%PDF-1.4\n% Lease Equity compliance dossier sandbox\n",
        "application/pdf",
    )
    pauta.compliance_dossier_uri = f"s3://letter-vault-private/{dossier_key}"
    db.flush()
    return pauta


def register_inspection_photos(
    db: Session,
    user: User,
    pauta: LeaseEquityPauta,
    photos: list[dict],
) -> LeaseEquityPauta:
    if pauta.status != "TAPAF_LIQUIDADA":
        raise HTTPException(status_code=409, detail="Vistoria disponível após TAPAF_LIQUIDADA")
    if len(photos) < 3:
        raise HTTPException(status_code=422, detail="Mínimo de 3 fotos nativas com EXIF obrigatório")
    for photo in photos:
        if photo.get("source") == "GALLERY":
            raise HTTPException(status_code=422, detail="Upload da galeria bloqueado — use câmera nativa")
        if not photo.get("exif_timestamp_unix") or not photo.get("gps_latitude") or not photo.get("gps_longitude"):
            raise HTTPException(status_code=422, detail="Foto deve conter timestamp Unix e GPS no EXIF")
    pauta.inspection_photos_count = len(photos)
    pauta.inspection_metadata_json = json.dumps(photos, ensure_ascii=False)
    _transition(db, pauta, user, "EM_AUDITORIA_RISCO", "Vistoria fotográfica nativa concluída")
    db.flush()
    return pauta


def run_compliance_review(
    db: Session,
    user: User,
    pauta: LeaseEquityPauta,
    *,
    approved: bool,
    blockers: list[str] | None = None,
) -> LeaseEquityPauta:
    if pauta.status != "EM_AUDITORIA_RISCO":
        raise HTTPException(status_code=409, detail="Auditoria de risco indisponível neste status")
    if approved:
        _transition(db, pauta, user, "AGUARDANDO_ASSINATURA", "Certidões 100% limpas")
    else:
        pauta.compliance_blockers_json = json.dumps(blockers or ["GRAVAME_OU_PRENOTACAO"], ensure_ascii=False)
        _transition(db, pauta, user, "REPROVADO_COMPLIANCE", "Reprovação sumária compliance")
    db.flush()
    return pauta


def sign_contract(db: Session, user: User, pauta: LeaseEquityPauta) -> LeaseEquityPauta:
    if pauta.status != "AGUARDANDO_ASSINATURA":
        raise HTTPException(status_code=409, detail="Assinatura indisponível neste status")
    _transition(db, pauta, user, "PRONTO_PARA_CARTORIO", "Contrato assinado ICP-Brasil")
    db.flush()
    return pauta


def submit_registry_protocol(db: Session, user: User, pauta: LeaseEquityPauta) -> LeaseEquityPauta:
    if pauta.status != "PRONTO_PARA_CARTORIO":
        raise HTTPException(status_code=409, detail="Protocolo SERP indisponível neste status")
    _transition(db, pauta, user, "EM_ANALISE_NO_RGI", "Paralegal protocolou SERP/ONR")
    db.flush()
    return pauta


def complete_gravame(db: Session, user: User, pauta: LeaseEquityPauta, certificate_uri: str | None = None) -> LeaseEquityPauta:
    if pauta.status != "EM_ANALISE_NO_RGI":
        raise HTTPException(status_code=409, detail="Averbação indisponível neste status")
    pauta.gravame_certificate_uri = certificate_uri or f"s3://letter-vault-private/partners/{pauta.pauta_code}/registry/averbacao.pdf"
    _transition(db, pauta, user, "GRAVAME_CONCLUIDO", "Certidão de averbação ONR")
    db.flush()
    return pauta


def record_funding_capture(db: Session, user: User, pauta: LeaseEquityPauta, amount) -> LeaseEquityPauta:
    if pauta.status not in {"GRAVAME_CONCLUIDO", "ATIVO_OK_EM_PRODUCAO"}:
        raise HTTPException(status_code=409, detail="Captação indisponível neste status")
    pauta.funding_captured_amount = money(Decimal(str(pauta.funding_captured_amount)) + money(amount))
    target = money(pauta.funding_target_amount)
    threshold = money(target * EngineLeaseEquityLetter.gatilho_captacao_minima_percent)
    if pauta.status == "GRAVAME_CONCLUIDO" and pauta.funding_captured_amount >= threshold:
        activate_ok(db, user, pauta, manual=False)
    db.flush()
    return pauta


def activate_ok(db: Session, user: User, pauta: LeaseEquityPauta, *, manual: bool = False) -> LeaseEquityPauta:
    if pauta.status != "GRAVAME_CONCLUIDO":
        raise HTTPException(status_code=409, detail="Ativação OK exige GRAVAME_CONCLUIDO")
    if not manual:
        target = money(pauta.funding_target_amount)
        threshold = money(target * EngineLeaseEquityLetter.gatilho_captacao_minima_percent)
        if pauta.funding_captured_amount < threshold:
            raise HTTPException(status_code=409, detail="Captação mínima de 30% não atingida")
    pauta.activation_at = datetime.now(UTC)
    pauta.activated_manually = manual
    pauta.anticipation_unlock_at = pauta.activation_at + timedelta(days=30 * EngineLeaseEquityLetter.carencia_meses_minima)
    _transition(db, pauta, user, "ATIVO_OK_EM_PRODUCAO", "Gatilho OK — payout aluguel D+30")
    db.flush()
    return pauta


def refresh_anticipation_eligibility(db: Session, user: User, pauta: LeaseEquityPauta, months_in_force: int) -> LeaseEquityPauta:
    if pauta.status != "ATIVO_OK_EM_PRODUCAO":
        raise HTTPException(status_code=409, detail="Carência aplicável apenas em ATIVO_OK_EM_PRODUCAO")
    pauta.months_in_force = int(months_in_force)
    if months_in_force >= EngineLeaseEquityLetter.carencia_meses_minima:
        _transition(db, pauta, user, "LIBERADO_PARA_ANTECIPACAO", "6 meses de vigência e adimplência")
    db.flush()
    return pauta


def simulate_anticipation(pauta: LeaseEquityPauta, parcelas_restantes: int = 36) -> dict:
    engine = EngineLeaseEquityLetter()
    credit = engine.processar_matriz_credito_ltv(pauta.property_type, pauta.appraisal_value)
    result = engine.calcular_antecipacao_recebiveis_price(
        Decimal(credit["aluguel_mensal_recorrente_bruto_dono"]),
        parcelas_restantes=parcelas_restantes,
        meses_vigencia_atual=pauta.months_in_force,
    )
    result["carencia_meses_minima"] = EngineLeaseEquityLetter.carencia_meses_minima
    result["data_liberacao_clique_app"] = (
        pauta.anticipation_unlock_at.isoformat() if pauta.anticipation_unlock_at else None
    )
    return result


def process_tokenization(pauta: LeaseEquityPauta, owner_uid: str | None = None) -> dict:
    if pauta.status not in {"GRAVAME_CONCLUIDO", "ATIVO_OK_EM_PRODUCAO", "LIBERADO_PARA_ANTECIPACAO"}:
        raise HTTPException(status_code=409, detail="Tokenização exige gravame concluído ou produção ativa")
    engine = EngineLeaseEquityLetter()
    credit = engine.processar_matriz_credito_ltv(pauta.property_type, pauta.appraisal_value)
    ltv_amount = Decimal(credit["limite_teto_ltv_captacao"])
    owner_rent = Decimal(credit["aluguel_mensal_recorrente_bruto_dono"])
    pool_cost = Decimal(credit["custo_mensal_remuneracao_pool_investidores"])
    rwa = engine.gerar_fracionamento_securitizado_rwa(ltv_amount, pauta.pauta_code)
    anticipation = engine.calcular_antecipacao_recebiveis_price(owner_rent, 36, pauta.months_in_force)
    payload = {
        "endpoint": "/api/v1/finops/lease-equity/tokenization-processor",
        "status": "SUCCESS",
        "data": {
            "contrato_id": pauta.pauta_code,
            "proprietario_uid": owner_uid or f"USER_PF_{pauta.owner_user_id[:8].upper()}",
            "colateral_imobiliario": {
                "matricula_numero": pauta.registry_number,
                "comarca_cartorio_rgi": pauta.registry_office,
                "tipo_bem": pauta.property_type,
                "valor_avaliacao_homologado": float(pauta.appraisal_value),
            },
            "parametrizacao_finops_mesa": {
                "ltv_alavancagem_teto_60_porcento": float(ltv_amount),
                "base_calculo_recompensa_dono_40_porcento": float(credit["base_calculo_recompensa_dono"]),
                "faturamento_mensal_bruto_recorrente_dono": float(owner_rent),
                "custo_mensal_pool_investment_1_6_porcento": float(pool_cost),
            },
            "workflow_securitizacao_rwa": {
                "titulo_lastro_vinculado": "NOTA_COMERCIAL_PRIVADA_SERIE_LE01",
                "custo_emissao_bancaria_intermediada": 0.00,
                "averbacao_remota_status": "GRAVAME_CONCLUIDO_ONR",
                "tokenizacao_blockchain_metadata": {
                    "smart_contract_padrao": "ERC-3643_COMPLIANT_RWA",
                    "total_supply_tokens_emitidos": rwa["total_supply_tokens_mint"],
                    "valor_nominal_unitario_token": float(rwa["valor_face_unitario_token_brl"]),
                    "ticker_identificador_rede": f"LE-LT-{pauta.pauta_code.split('_')[-1][:4]}",
                    "distribuicao_rendimento_token_mensal": float(rwa["rendimento_mensal_unitario_smart_contract"]),
                },
            },
            "trava_seguranca_antecipacao_futura": {
                "carecia_meses_minima": EngineLeaseEquityLetter.carencia_meses_minima,
                "data_liberacao_clique_app": (
                    pauta.anticipation_unlock_at.strftime("%Y-%m-%d %H:%M:%S")
                    if pauta.anticipation_unlock_at
                    else None
                ),
                "taxa_desconto_price_fixada": float(EngineLeaseEquityLetter.taxa_desconto_antecipacao_mensal),
                "status_antecipacao_atual": anticipation["status_antecipacao"],
            },
        },
    }
    pauta.tokenization_json = json.dumps(payload, ensure_ascii=False)
    return payload
