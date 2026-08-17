import json
from datetime import UTC, datetime
from decimal import Decimal, ROUND_HALF_UP

from fastapi import HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.config import settings
from app.models import Contract, Document, Invoice, Lead, PaymentEvent, PaymentReceipt, Proposal, User
from app.receipt_service import (
    build_storage_paths,
    compute_authenticity_hash,
    receipt_filename,
    receipt_pdf,
    resolve_receipt_context,
)
from app.receipt_notification_service import dispatch_receipt_notifications
from app.storage_service import get_storage


HUNDRED = Decimal("100")


def money(value: Decimal) -> Decimal:
    return value.quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)


class MotorFaturamentoEFiscalLETTERV3:
    """LETTER_FINOPS_INVOICE_AUTOMATION_ENGINE_2026_V3 — sandbox/production."""

    imposto_lucro_presumido_fruicao = Decimal("0.1133")
    taxa_pool_mensal_price = Decimal("0.025")

    def calcular_e_disparar_recibo_automatico(
        self,
        *,
        id_contrato: str,
        id_parceiro: str,
        volume_total_pago: Decimal,
        mes_referencia: int,
        base_fruicao_juros: Decimal,
        base_amortizacao_recompra: Decimal,
    ) -> dict:
        v_pago = money(volume_total_pago)
        v_fruicao = money(base_fruicao_juros)
        v_amortizacao = money(base_amortizacao_recompra)
        mes = int(mes_referencia)
        hash_recibo = compute_authenticity_hash(id_contrato, mes, v_fruicao, v_amortizacao)
        nome_arquivo_pdf = receipt_filename(mes)
        _, _, customer_route, vault_uri = build_storage_paths(id_parceiro, id_contrato, nome_arquivo_pdf)
        return {
            "timestamp_emissao_automatica": datetime.now(UTC).isoformat(),
            "id_contrato_vinculado": id_contrato,
            "id_parceiro_vinculado": id_parceiro,
            "mes_competencia": mes,
            "hash_autenticidade_documental": hash_recibo,
            "demonstrativo_contabil_legal": {
                "valor_total_liquidado_baas": str(v_pago),
                "fração_taxa_de_fruição_tributavel": str(v_fruicao),
                "fração_amortização_da_recompra_isenta": str(v_amortizacao),
                "imposto_retido_spe_lucro_presumido": str(money(v_fruicao * self.imposto_lucro_presumido_fruicao)),
                "indexacao_ipca_anual": mes in {13, 25},
            },
            "mapeamento_armazenamento_nuvem": {
                "rota_area_logada_cliente_db": customer_route,
                "rota_interna_bucket_s3_admin": vault_uri,
            },
            "disparo_transacional_workflow": {
                "trigger_email_automatico": "SENT_D+0",
                "trigger_push_notificacao": "ACTIVE",
            },
        }


def resolve_partner_id(db: Session, proposal: Proposal) -> str:
    lead = db.get(Lead, proposal.lead_id) if proposal.lead_id else None
    if lead and lead.owner_id:
        return f"PARTNER_{lead.owner_id[:8].upper()}"
    return f"PARTNER_ORG_{proposal.organization_id[:8].upper()}"


def process_invoice_settlement(
    db: Session,
    user: User,
    invoice: Invoice,
    payment_event: PaymentEvent | None = None,
) -> PaymentReceipt:
    if invoice.status != "PAID":
        raise HTTPException(status_code=409, detail="Recibo exige fatura com status PAID")

    if payment_event:
        existing = db.scalar(
            select(PaymentReceipt).where(
                PaymentReceipt.invoice_id == invoice.id,
                PaymentReceipt.payment_event_id == payment_event.id,
            )
        )
        if existing:
            return existing

    contract = db.get(Contract, invoice.contract_id)
    proposal = db.get(Proposal, invoice.proposal_id)
    if not contract or not proposal:
        raise HTTPException(status_code=404, detail="Contrato ou proposta não encontrados")

    fruicao = money(Decimal(str(invoice.interest_amount)))
    amortizacao = money(Decimal(str(invoice.principal_amount)))
    fee = money(Decimal(str(invoice.fee_amount)))
    if fruicao == Decimal("0") and fee > Decimal("0"):
        fruicao = fee
    total_paid = money(Decimal(str(invoice.total_amount)))
    reference_month = max(1, int(invoice.installment_number or 1))
    partner_id = resolve_partner_id(db, proposal)
    ctx = resolve_receipt_context(db, proposal, reference_month)

    engine = MotorFaturamentoEFiscalLETTERV3()
    payload = engine.calcular_e_disparar_recibo_automatico(
        id_contrato=contract.id,
        id_parceiro=partner_id,
        volume_total_pago=total_paid,
        mes_referencia=reference_month,
        base_fruicao_juros=fruicao,
        base_amortizacao_recompra=amortizacao,
    )
    tax_withheld = money(fruicao * engine.imposto_lucro_presumido_fruicao)
    filename = receipt_filename(reference_month)
    customer_key, vault_key, customer_route, vault_uri = build_storage_paths(
        partner_id, contract.id, filename,
    )

    pdf_bytes = receipt_pdf(
        contract=contract,
        proposal=proposal,
        invoice=invoice,
        fruicao=fruicao,
        amortizacao=amortizacao,
        total_paid=total_paid,
        tax_withheld=tax_withheld,
        authenticity_hash=payload["hash_autenticidade_documental"],
        reference_month=reference_month,
        client_name=ctx["client_name"],
        client_cnpj=ctx["client_cnpj"],
        property_registry=ctx["property_registry"],
        registry_office=ctx["registry_office"],
        ipca_adjusted=ctx["ipca_adjusted"],
    )
    storage = get_storage()
    storage.put(customer_key, pdf_bytes, "application/pdf")
    storage.put(vault_key, pdf_bytes, "application/pdf")

    doc = Document(
        organization_id=user.organization_id,
        entity_type="contract",
        entity_id=contract.id,
        kind="PAYMENT_RECEIPT",
        filename=filename,
        storage_key=customer_key,
        sha256=payload["hash_autenticidade_documental"].replace("sha256_", ""),
        status="APPROVED",
        uploaded_by_id=user.id,
    )
    db.add(doc)
    db.flush()

    receipt = PaymentReceipt(
        organization_id=user.organization_id,
        invoice_id=invoice.id,
        contract_id=contract.id,
        payment_event_id=payment_event.id if payment_event else None,
        partner_id=partner_id,
        reference_month=reference_month,
        filename=filename,
        total_paid=total_paid,
        fruicao_amount=fruicao,
        amortizacao_amount=amortizacao,
        tax_withheld=tax_withheld,
        authenticity_hash=payload["hash_autenticidade_documental"],
        customer_route=customer_route,
        vault_s3_uri=vault_uri,
        document_id=doc.id,
        payload_json=json.dumps(payload, ensure_ascii=False),
        email_status="SENT_D+0",
        push_status="ACTIVE",
        issued_at=datetime.now(UTC),
    )
    db.add(receipt)
    db.flush()
    lead = db.get(Lead, proposal.lead_id) if proposal.lead_id else None
    dispatch = dispatch_receipt_notifications(db, user, receipt, lead)
    payload["disparo_transacional_workflow"] = {
        "trigger_email_automatico": dispatch["trigger_email_automatico"],
        "trigger_push_notificacao": dispatch["trigger_push_notificacao"],
    }
    receipt.payload_json = json.dumps(payload, ensure_ascii=False)
    db.flush()
    return receipt


def receipt_processor_response(receipt: PaymentReceipt, transacao_id: str | None = None) -> dict:
    data = json.loads(receipt.payload_json)
    return {
        "endpoint": "/api/v1/finops/billing/invoice-processor",
        "status": "SUCCESS",
        "transacao_id": transacao_id or f"TX_BILL_{receipt.id[:8].upper()}",
        "data": data,
    }


def receipt_view(receipt: PaymentReceipt) -> dict:
    return {
        "id": receipt.id,
        "contract_id": receipt.contract_id,
        "invoice_id": receipt.invoice_id,
        "partner_id": receipt.partner_id,
        "reference_month": receipt.reference_month,
        "filename": receipt.filename,
        "total_paid": str(receipt.total_paid),
        "fruicao_amount": str(receipt.fruicao_amount),
        "amortizacao_amount": str(receipt.amortizacao_amount),
        "tax_withheld": str(receipt.tax_withheld),
        "authenticity_hash": receipt.authenticity_hash,
        "customer_route": receipt.customer_route,
        "vault_s3_uri": receipt.vault_s3_uri,
        "email_status": receipt.email_status,
        "push_status": receipt.push_status,
        "issued_at": receipt.issued_at,
    }
