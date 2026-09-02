"""Motor de pré-análise fiduciária V6 e esteira TAPAF."""

import hashlib
import json
from datetime import UTC, datetime
from decimal import Decimal, ROUND_HALF_UP
from uuid import uuid4

from fastapi import HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.administrator_service import homologated_codes, rules_for_administrator_name
from app.flash_valid_lss_service import issue_stamp
from app.company_profile_service import company_profile
from app.infra_http import digits
from app.models import PreAnalysisPauta, Proposal, User
from app.pre_analysis_constants import (
    DOCUMENT_LABELS,
    REQUIRED_DOCUMENT_CODES,
    TAPAF_CHECKBOX_01,
    TAPAF_CHECKBOX_02,
    TAPAF_MANIFESTO_HTML,
    TAPAF_TOOLTIP,
)
from app.storage_service import get_storage
from app.tapaf_constants import TAPAF_NOMINAL
from app.tapaf_settlement_service import settle_tapaf_payment


HUNDRED = Decimal("100")


def money(value: Decimal) -> Decimal:
    return value.quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)


class MotorPreAnaliseFiduciariaV6:
    margem_maxima_renda = Decimal("0.30")
    fee_plataforma_percent = Decimal("0.10")
    taxa_tapaf_nominal = TAPAF_NOMINAL
    administradoras_homologadas = [
        "HS_CONSORCIOS", "EMBRACON", "ADEMICON", "ANCORA", "WHITELABEL_ANCORA",
    ]

    def calcular_media_extratos_bancarios_limpos(self, extratos_6_meses_data: dict) -> tuple[Decimal, str]:
        if len(extratos_6_meses_data) < 6:
            return Decimal("0"), "REPROVADO_POR_JANELA_INCOMPLETA_DE_EXTRATOS"
        soma = Decimal("0")
        for transacoes in extratos_6_meses_data.values():
            creditos = [
                Decimal(str(t["valor"])) for t in transacoes
                if t.get("tipo_credito") in {"PIX_RECEBIDO", "TED_RECEBIDA", "FATURAMENTO_CARTÃO", "FATURAMENTO_CARTAO"}
                and not t.get("mesmo_titular_TED_bool", False)
            ]
            soma += sum(creditos, Decimal("0"))
        return money(soma / Decimal("6")), "CONSOLIDADO_SUCCESS"

    def processar_esteira_score_e_roteamento(
        self,
        *,
        adm_nome: str,
        extratos_6_meses_data: dict,
        parcela_simulada: Decimal,
        valor_avaliacao_bem: Decimal,
        saldo_devedor_cotas: Decimal,
        ano_fabricacao_bem: int,
        restricoes_cadastrais_bool: bool,
        possui_gravame_bool: bool,
        valor_gravame_anterior: Decimal = Decimal("0"),
        homologated_codes: list[str] | None = None,
        max_asset_age_years: int = 10,
        min_commitment_margin: Decimal | None = None,
    ) -> dict:
        parcela = money(parcela_simulada)
        val_bem = money(valor_avaliacao_bem)
        saldo_cotas = money(saldo_devedor_cotas)
        val_gravame = money(valor_gravame_anterior)
        ano_atual = datetime.now(UTC).year

        allowed = homologated_codes or self.administradoras_homologadas
        adm_key = adm_nome.upper().replace(" ", "_")
        if adm_key not in [c.upper() for c in allowed] and adm_nome.upper() not in [c.upper() for c in allowed]:
            return {"status_core": "REPROVADO_ADMINISTRADORA_NAO_CONVENIADA"}

        renda_liquida, status_renda = self.calcular_media_extratos_bancarios_limpos(extratos_6_meses_data)
        if status_renda != "CONSOLIDADO_SUCCESS":
            return {"status_core": "REPROVADO_POR_INCONSISTENCIA_DE_MESES_NO_CHECKLIST"}

        if restricoes_cadastrais_bool:
            return {
                "status_core": "ROTEAMENTO_OBRIGATORIO_FLASH_CAPITAL",
                "motivo_gatilho": (
                    "Identificada restrição cadastral ativa ou apontamento preferencial no CPF dos sócios, "
                    "cônjuges ou CNPJ da PJ."
                ),
                "produto_direcionado": "Flash Capital (Compra com Pacto de Retrovenda Imobiliária a 14% a.a. + IPCA)",
            }

        if possui_gravame_bool:
            limite_gravame = money(val_bem * Decimal("0.25"))
            if val_gravame > limite_gravame:
                return {
                    "status_core": "REPROVADO_SUMARIAMENTE_POR_EXCESSO_DE_GRAVAME",
                    "motivo_gatilho": "O saldo devedor do gravame ultrapassa o teto prudencial de 25% do valor do bem.",
                }

        if val_bem < saldo_cotas:
            return {
                "status_core": "REPROVADO_POR_INSUFICIENCIA_DE_LASTRO",
                "motivo_gatilho": (
                    f"O valor de avaliação da garantia (R$ {val_bem}) é inferior ao saldo devedor "
                    f"das cotas (R$ {saldo_cotas})."
                ),
            }

        idade_bem = ano_atual - int(ano_fabricacao_bem)
        if idade_bem > max_asset_age_years:
            return {
                "status_core": "ROTEAMENTO_OBRIGATORIO_FLASH_CAPITAL",
                "motivo_gatilho": (
                    f"O ano de fabricação do bem ({ano_fabricacao_bem}) ultrapassa a idade máxima "
                    f"permitida pelas regras da administradora {adm_nome} ({max_asset_age_years} anos)."
                ),
            }

        margin = min_commitment_margin if min_commitment_margin is not None else self.margem_maxima_renda
        limite_margem = money(renda_liquida * margin)
        if parcela > limite_margem:
            resumo_oculto = {
                "media_entradas_mensais_apurada_extratos_6_meses": str(renda_liquida),
                "limite_maximo_parcela_permitido_30percent": str(limite_margem),
                "parcela_solicitada_estourada": str(parcela),
            }
            return {
                "status_core": "REPROVADO_POR_PARCELA_MAIOR_QUE_30_PERCENT_DA_RENDA",
                "resumo_fiduciario_interno_oculto_para_o_fundo": resumo_oculto,
                "bifurcacao_opcoes_interface_cliente": {
                    "opcao_01_liberar_valor_menor_comportado": {
                        "mensagem": "Seguir com o valor de Payout menor adequado à sua renda atual.",
                        "limite_maximo_parcela": str(limite_margem),
                    },
                    "opcao_02_apresentar_renda_extra_adicional": {
                        "mensagem": "Apresentar documentação complementar para somar à renda da empresa.",
                        "faturamento_mensal_adicional_necessario": str(
                            money(parcela / margin - renda_liquida)
                        ),
                        "aviso_travado_text_html": (
                            "COMPLEMENTAÇÕES ADICIONAIS ACEITAS PELO COMITÊ: CONTRATO DE PRESTAÇÃO DE "
                            "SERVIÇOS DE EXECUÇÃO ATIVA ACOPLADO ÀS RECTIVAS NOTAS FISCAIS EMITIDAS; "
                            "DECORE ELETRÔNICA COM SELO CRC DOS ÚLTIMOS 03 MESES; OU RENDA COMPLEMENTAR "
                            "DO CÔNJUGE DO SÓCIO MAJORITÁRIO EM CONFORMIDADE COM O CHECKLIST DE IDENTIFICAÇÃO."
                        ),
                    },
                    "opcao_03_migrar_para_esteira_flash_capital": {
                        "mensagem": "Migrar para o Flash Capital (Sem comprovação de faturamento e sem score Bacen).",
                        "produto": "Flash Capital (Compra com Pacto de Retrovenda Imobiliária B2B)",
                        "botao_ajuda_interrogacao_url": "/api/v1/help/what-is-flash-capital",
                    },
                },
                "_client_visible": {
                    "status_core": "REPROVADO_POR_PARCELA_MAIOR_QUE_30_PERCENT_DA_RENDA",
                    "bifurcacao_opcoes_interface_cliente": True,
                },
            }

        stamp_hash = "sha256_" + hashlib.sha256(
            f"{adm_nome}_{parcela}_{renda_liquida}_{datetime.now(UTC).isoformat()}".encode()
        ).hexdigest()
        return {
            "status_core": "APROVADO_COMPLIANCE_NINA",
            "Selo_LETTER_Valid_Stamp": {
                "status": "ISSUED_VALID_STAMP_SUCCESS",
                "hash_criptografico_rs256": stamp_hash,
            },
            "encaminhamento_workflow": {
                "status_esteira": "ESTEIRA_INTERNA_DE_CHECK_MANDATORIO_SPE",
                "responsavel_auditoria_id": "SUPERINTENDENTE_GERAL_OPERAGOES",
            },
            "resumo_fiduciario_interno_oculto_para_o_fundo": {
                "media_entradas_mensais_apurada_extratos_6_meses": str(renda_liquida),
                "limite_maximo_parcela_permitido_30percent": str(limite_margem),
            },
        }


def get_or_create_pauta(db: Session, user: User, proposal: Proposal) -> PreAnalysisPauta:
    item = db.scalar(
        select(PreAnalysisPauta).where(
            PreAnalysisPauta.proposal_id == proposal.id,
            PreAnalysisPauta.organization_id == user.organization_id,
        )
    )
    if item:
        return item
    code = f"PAUTA_{proposal.product}_{datetime.now(UTC).strftime('%Y')}_{uuid4().hex[:4].upper()}"
    item = PreAnalysisPauta(
        organization_id=user.organization_id,
        proposal_id=proposal.id,
        pauta_code=code,
        status="PENDING_DOCUMENTS",
        documents_json="[]",
    )
    db.add(item)
    db.flush()
    return item


def validate_documents_phase1(db: Session, user: User, proposal: Proposal, documents: list[dict]) -> PreAnalysisPauta:
    pauta = get_or_create_pauta(db, user, proposal)
    errors: list[dict] = []
    submitted = {d["code"]: d for d in documents}
    for code in REQUIRED_DOCUMENT_CODES:
        doc = submitted.get(code)
        if not doc or not doc.get("present", True):
            errors.append({"code": code, "label": DOCUMENT_LABELS[code], "reason": "AUSENTE"})
            continue
        dpi = int(doc.get("dpi") or 0)
        if dpi and dpi < 150:
            errors.append({"code": code, "label": DOCUMENT_LABELS[code], "reason": "QUALIDADE_INFERIOR_150_DPI"})
        if doc.get("illegible") or doc.get("rasurado"):
            errors.append({"code": code, "label": DOCUMENT_LABELS[code], "reason": "ILEGIVEL_OU_RASURADO"})
    pauta.documents_json = json.dumps({"submitted": documents, "errors": errors}, ensure_ascii=False)
    if errors:
        pauta.status = "PENDING_DOCUMENTS"
    else:
        pauta.status = "DOCUMENTS_OK"
    return pauta


def generate_tapaf_checkout(pauta: PreAnalysisPauta) -> dict:
    if pauta.status not in {"DOCUMENTS_OK", "TAPAF_CHECKOUT_ACCEPTED", "TAPAF_PAID"}:
        raise HTTPException(status_code=409, detail="Documentação deve estar validada na Fase 1 antes da TAPAF")
    return {
        "endpoint": "/api/v1/finops/pre-analysis/generate-tapaf",
        "status": "SUCCESS",
        "pauta_id": pauta.pauta_code,
        "interface_checkout_tapaf": {
            "valor_nominal_taxa": "1500.00",
            "gateway_baas_pix_qrcode": f"00020101021126580014br.gov.bcb.pix0136letter-spe-tapaf-{pauta.id[:8]}",
            "texto_explicativo_tooltip_interrogacao": TAPAF_TOOLTIP,
            "checkbox_obrigatorio_01": TAPAF_CHECKBOX_01,
            "checkbox_obrigatorio_02": TAPAF_CHECKBOX_02,
            "manifesto_html": TAPAF_MANIFESTO_HTML,
            "botao_habilitado": False,
            "botao_label": "GERAR BOLETO / PIX DE ANÁLISE",
        },
    }


def accept_tapaf_checkout(
    db: Session, pauta: PreAnalysisPauta, *,
    scroll_completed: bool, checkbox_1: bool, checkbox_2: bool,
) -> PreAnalysisPauta:
    if pauta.status != "DOCUMENTS_OK":
        raise HTTPException(status_code=409, detail="Checkout TAPAF indisponível neste status")
    if not all([scroll_completed, checkbox_1, checkbox_2]):
        raise HTTPException(status_code=422, detail="Rolagem do manifesto e duas caixas de aceite são obrigatórias")
    pauta.tapaf_scroll_completed = True
    pauta.tapaf_checkbox_1 = True
    pauta.tapaf_checkbox_2 = True
    pauta.status = "TAPAF_CHECKOUT_ACCEPTED"
    return pauta


def confirm_tapaf_payment(db: Session, user: User, pauta: PreAnalysisPauta, event_id: str, amount: Decimal) -> PreAnalysisPauta:
    if pauta.status != "TAPAF_CHECKOUT_ACCEPTED":
        raise HTTPException(status_code=409, detail="Aceite do checkout TAPAF é obrigatório antes do pagamento")
    if money(amount) != MotorPreAnaliseFiduciariaV6.taxa_tapaf_nominal:
        raise HTTPException(status_code=422, detail="Valor TAPAF deve ser exatamente R$ 1.500,00")
    pauta.tapaf_payment_reference = event_id
    pauta.tapaf_paid_at = datetime.now(UTC)
    pauta.status = "TAPAF_PAID"
    proposal = db.get(Proposal, pauta.proposal_id)
    submitted = json.loads(pauta.documents_json or "{}").get("submitted", [])
    registry_number = next(
        (
            str(item.get("reference") or item.get("filename") or "")
            for item in submitted
            if str(item.get("code", "")).upper() in {"MATRICULA_ENOTARIADO", "MATRICULA", "LAUDO_AVALIACAO"}
            and (item.get("reference") or item.get("filename"))
        ),
        None,
    )
    company_document = company_profile()["cnpj_digits"]
    if proposal and proposal.terms_json:
        try:
            terms = json.loads(proposal.terms_json)
            if isinstance(terms, dict):
                company_document = digits(terms.get("company_cnpj")) or company_document
        except json.JSONDecodeError:
            pass
    settle_tapaf_payment(
        db,
        user,
        track="REAL_ESTATE",
        entity_type="pre_analysis_pauta",
        entity_id=pauta.id,
        payment_event_id=event_id,
        total_amount=money(amount),
        inventory_context={
            "proposal_id": pauta.proposal_id,
            "pauta_code": pauta.pauta_code,
            "appraisal_value": str(proposal.requested_amount if proposal else "0"),
            "company_document": company_document,
            "registry_number": registry_number,
        },
    )
    return pauta


def _flash_documents_from_pauta(pauta: PreAnalysisPauta, asset_type: str) -> dict[str, str]:
    submitted = json.loads(pauta.documents_json or "{}").get("submitted", [])
    by_code = {str(d.get("code", "")): str(d.get("filename", d.get("code", ""))) for d in submitted}
    tapaf_ref = pauta.tapaf_payment_reference or pauta.id

    def doc_hash(code: str, fallback: str) -> str:
        raw = by_code.get(code, fallback)
        return hashlib.sha256(raw.encode()).hexdigest()

    if asset_type == "VEHICLE":
        return {
            "FIPE_MOLICAR": doc_hash("MATRICULA_OU_CRLV", "fipe"),
            "LAUDO_AVALIACAO": doc_hash("LAUDO_AVM", "laudo"),
            "SERASA": tapaf_ref,
            "BACEN": tapaf_ref,
            "CRLV": doc_hash("MATRICULA_OU_CRLV", "crlv"),
        }
    return {
        "MATRICULA_ENOTARIADO": doc_hash("MATRICULA_OU_CRLV", "matricula"),
        "LAUDO_AVALIACAO": doc_hash("LAUDO_AVM", "laudo"),
        "SERASA": tapaf_ref,
        "BACEN": tapaf_ref,
    }


def run_flash_capital_engine_phase3(
    db: Session,
    user: User,
    pauta: PreAnalysisPauta,
    proposal: Proposal,
    payload: dict,
) -> dict:
    """Flash Capital: pós-TAPAF emite Valid-Stamp com LTV 40% e lastro imobiliário/veicular."""
    if pauta.status != "TAPAF_PAID":
        raise HTTPException(status_code=409, detail="Pagamento TAPAF confirmado é obrigatório para emissão do Valid-Stamp")

    asset_value = money(Decimal(str(payload.get("valor_avaliacao_bem", "0"))))
    principal = money(Decimal(str(proposal.requested_amount)))
    if asset_value <= 0:
        raise HTTPException(status_code=422, detail="Informe valor_avaliacao_bem (AVM) para Flash Capital")

    ltv = money(principal / asset_value * HUNDRED)
    asset_type = str(payload.get("asset_type", "REAL_ESTATE")).upper()
    if asset_type not in {"REAL_ESTATE", "VEHICLE"}:
        raise HTTPException(status_code=422, detail="asset_type deve ser REAL_ESTATE ou VEHICLE")

    engine = MotorPreAnaliseFiduciariaV6()
    extratos = payload.get("extratos_6_meses_data") or {}
    renda_liquida, status_renda = engine.calcular_media_extratos_bancarios_limpos(extratos)
    parcela = money(Decimal(str(payload.get("parcela_simulada", proposal.requested_amount))))
    limite_margem = money(renda_liquida * engine.margem_maxima_renda) if status_renda == "CONSOLIDADO_SUCCESS" else Decimal("0")

    result: dict = {
        "status_core": "APROVADO_COMPLIANCE_NINA",
        "produto": "FLASH_CAPITAL",
        "ltv_percent": str(ltv),
        "max_ltv_percent": "40",
        "asset_type": asset_type,
        "tapaf_reference": pauta.tapaf_payment_reference,
    }

    if ltv > Decimal("40"):
        result["status_core"] = "REPROVADO_POR_LTV_EXCEDIDO"
        result["motivo_gatilho"] = f"LTV {ltv}% excede o teto Flash Capital de 40%."
        pauta.status = "REPROVED"
    elif status_renda == "CONSOLIDADO_SUCCESS" and parcela > limite_margem:
        result["status_core"] = "REPROVADO_POR_PARCELA_MAIOR_QUE_30_PERCENT_DA_RENDA"
        result["motivo_gatilho"] = "Parcela acima de 30% da renda apurada nos extratos."
        pauta.status = "REPROVED"
    else:
        stamp_hash = "sha256_" + hashlib.sha256(
            f"FLASH_{proposal.id}_{pauta.tapaf_payment_reference}_{datetime.now(UTC).isoformat()}".encode()
        ).hexdigest()
        pauta.valid_stamp_hash = stamp_hash
        pauta.status = "APPROVED_VALID_STAMP"
        stamp_payload = {
            "pauta_code": pauta.pauta_code,
            "proposal_id": proposal.id,
            "tapaf_evidence_reference": pauta.tapaf_payment_reference,
            "asset_type": asset_type,
            "ltv_percent": str(ltv),
            "documents": _flash_documents_from_pauta(pauta, asset_type),
        }
        if asset_type == "VEHICLE" and payload.get("vehicle"):
            stamp_payload["vehicle"] = payload["vehicle"]
        issue_stamp(
            db,
            user,
            entity_type="pre_analysis_pauta",
            entity_id=pauta.id,
            purpose="FLASH_CAPITAL_PARTIES",
            payload=stamp_payload,
        )
        result["Selo_LETTER_Valid_Stamp"] = {
            "status": "ISSUED_VALID_STAMP_SUCCESS",
            "hash_criptografico_rs256": stamp_hash,
        }

    pauta.engine_result_json = json.dumps(result, ensure_ascii=False)
    pauta.client_result_json = json.dumps(
        {k: v for k, v in result.items() if k != "resumo_fiduciario_interno_oculto_para_o_fundo"},
        ensure_ascii=False,
    )
    return json.loads(pauta.client_result_json or "{}")


def run_engine_phase3(
    db: Session, user: User, pauta: PreAnalysisPauta, proposal: Proposal, payload: dict,
) -> dict:
    if proposal.product == "FLASH_CREDIT":
        return run_flash_capital_engine_phase3(db, user, pauta, proposal, payload)

    if pauta.status != "TAPAF_PAID":
        raise HTTPException(status_code=409, detail="Pagamento TAPAF confirmado é obrigatório para Fase 3")

    engine = MotorPreAnaliseFiduciariaV6()
    codes = homologated_codes(db) or engine.administradoras_homologadas
    adm_nome = str(payload.get("adm_nome", "ANCORA"))
    admin_rules = rules_for_administrator_name(db, adm_nome)
    approval_rules = admin_rules.get("approval_rules") if isinstance(admin_rules.get("approval_rules"), dict) else {}
    result = engine.processar_esteira_score_e_roteamento(
        adm_nome=adm_nome,
        extratos_6_meses_data=payload.get("extratos_6_meses_data") or {},
        parcela_simulada=Decimal(str(payload.get("parcela_simulada", proposal.requested_amount))),
        valor_avaliacao_bem=Decimal(str(payload.get("valor_avaliacao_bem", "0"))),
        saldo_devedor_cotas=Decimal(str(payload.get("saldo_devedor_cotas", proposal.requested_amount))),
        ano_fabricacao_bem=int(payload.get("ano_fabricacao_bem", datetime.now(UTC).year)),
        restricoes_cadastrais_bool=bool(payload.get("restricoes_cadastrais_bool", False)),
        possui_gravame_bool=bool(payload.get("possui_gravame_bool", False)),
        valor_gravame_anterior=Decimal(str(payload.get("valor_gravame_anterior", "0"))),
        homologated_codes=codes,
        max_asset_age_years=int(admin_rules.get("max_asset_age_years", 10)),
        min_commitment_margin=Decimal(str(approval_rules.get("min_income_margin", admin_rules.get("min_commitment_margin", "0.30")))),
    )

    pauta.engine_result_json = json.dumps(result, ensure_ascii=False)
    client_result = {k: v for k, v in result.items() if k != "resumo_fiduciario_interno_oculto_para_o_fundo"}
    if "bifurcacao_opcoes_interface_cliente" in client_result:
        client_result.pop("resumo_fiduciario_interno_oculto_para_o_fundo", None)
    pauta.client_result_json = json.dumps(client_result, ensure_ascii=False)

    status_core = result.get("status_core", "UNKNOWN")
    if status_core == "APROVADO_COMPLIANCE_NINA":
        pauta.status = "APPROVED_VALID_STAMP"
        stamp_info = result.get("Selo_LETTER_Valid_Stamp", {})
        pauta.valid_stamp_hash = stamp_info.get("hash_criptografico_rs256")
        issue_stamp(
            db, user,
            entity_type="pre_analysis_pauta",
            entity_id=pauta.id,
            purpose="PRE_ANALYSIS_VALID_STAMP",
            payload={
                "pauta_code": pauta.pauta_code,
                "proposal_id": proposal.id,
                "tapaf_reference": pauta.tapaf_payment_reference,
                "engine_status": status_core,
                "stamp_hash": pauta.valid_stamp_hash,
            },
        )
        vault_key = f"company-vault/pre-analysis/{pauta.id}/resumo_fiduciario_oculto.json"
        get_storage().put(
            vault_key,
            json.dumps(result.get("resumo_fiduciario_interno_oculto_para_o_fundo", {}), ensure_ascii=False).encode(),
            "application/json",
        )
        pauta.vault_s3_uri = f"s3://letter-vault-private/{vault_key}"
    elif status_core.startswith("ROTEAMENTO"):
        pauta.status = "ROUTED_FLASH_CAPITAL"
    else:
        pauta.status = "REPROVED"

    return client_result


def pauta_view(item: PreAnalysisPauta) -> dict:
    return {
        "id": item.id,
        "proposal_id": item.proposal_id,
        "pauta_code": item.pauta_code,
        "status": item.status,
        "documents": json.loads(item.documents_json or "{}"),
        "tapaf_scroll_completed": item.tapaf_scroll_completed,
        "tapaf_checkbox_1": item.tapaf_checkbox_1,
        "tapaf_checkbox_2": item.tapaf_checkbox_2,
        "tapaf_payment_reference": item.tapaf_payment_reference,
        "tapaf_paid_at": item.tapaf_paid_at,
        "client_result": json.loads(item.client_result_json) if item.client_result_json else None,
        "valid_stamp_hash": item.valid_stamp_hash,
        "created_at": item.created_at,
    }
