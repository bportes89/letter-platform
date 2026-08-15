"""Motor de pré-análise fiduciária V6 e esteira TAPAF."""

import hashlib
import json
from datetime import UTC, datetime
from decimal import Decimal, ROUND_HALF_UP
from uuid import uuid4

from fastapi import HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.flash_valid_lss_service import issue_stamp
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


HUNDRED = Decimal("100")


def money(value: Decimal) -> Decimal:
    return value.quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)


class MotorPreAnaliseFiduciariaV6:
    margem_maxima_renda = Decimal("0.30")
    fee_plataforma_percent = Decimal("0.10")
    taxa_tapaf_nominal = Decimal("1500.00")
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
    ) -> dict:
        parcela = money(parcela_simulada)
        val_bem = money(valor_avaliacao_bem)
        saldo_cotas = money(saldo_devedor_cotas)
        val_gravame = money(valor_gravame_anterior)
        ano_atual = datetime.now(UTC).year

        if adm_nome not in self.administradoras_homologadas:
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
        if idade_bem > 10:
            return {
                "status_core": "ROTEAMENTO_OBRIGATORIO_FLASH_CAPITAL",
                "motivo_gatilho": (
                    f"O ano de fabricação do bem ({ano_fabricacao_bem}) ultrapassa a idade máxima "
                    f"permitida pelas regras da administradora {adm_nome}."
                ),
            }

        limite_margem = money(renda_liquida * self.margem_maxima_renda)
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
                            money(parcela / self.margem_maxima_renda - renda_liquida)
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
    return pauta


def run_engine_phase3(
    db: Session, user: User, pauta: PreAnalysisPauta, proposal: Proposal, payload: dict,
) -> dict:
    if pauta.status != "TAPAF_PAID":
        raise HTTPException(status_code=409, detail="Pagamento TAPAF confirmado é obrigatório para Fase 3")

    engine = MotorPreAnaliseFiduciariaV6()
    result = engine.processar_esteira_score_e_roteamento(
        adm_nome=str(payload.get("adm_nome", "ANCORA")),
        extratos_6_meses_data=payload.get("extratos_6_meses_data") or {},
        parcela_simulada=Decimal(str(payload.get("parcela_simulada", proposal.requested_amount))),
        valor_avaliacao_bem=Decimal(str(payload.get("valor_avaliacao_bem", "0"))),
        saldo_devedor_cotas=Decimal(str(payload.get("saldo_devedor_cotas", proposal.requested_amount))),
        ano_fabricacao_bem=int(payload.get("ano_fabricacao_bem", datetime.now(UTC).year)),
        restricoes_cadastrais_bool=bool(payload.get("restricoes_cadastrais_bool", False)),
        possui_gravame_bool=bool(payload.get("possui_gravame_bool", False)),
        valor_gravame_anterior=Decimal(str(payload.get("valor_gravame_anterior", "0"))),
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
