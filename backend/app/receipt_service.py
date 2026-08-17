import hashlib
import io
from datetime import UTC, datetime
from decimal import Decimal

from reportlab.lib.colors import HexColor
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import mm
from reportlab.platypus import Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle

from app.core.config import settings
from app.models import Contract, Invoice, Proposal


def receipt_filename(reference_month: int) -> str:
    return f"recibo_fruicao_mes_{reference_month:02d}.pdf"


def build_storage_paths(partner_id: str, contract_id: str, filename: str) -> tuple[str, str, str, str]:
    admin_key = f"partners/{partner_id}/contracts/{contract_id}/receipts/{filename}"
    customer_key = f"customer-vault/contracts/{contract_id}/receipts/{filename}"
    bucket = settings.vault_bucket or settings.s3_bucket or "letter-vault-private"
    vault_uri = f"s3://{bucket}/{admin_key}"
    customer_route = f"/api/v1/customer/dashboard/contracts/{contract_id}/receipts/{filename}"
    return customer_key, admin_key, customer_route, vault_uri


def resolve_receipt_context(db, proposal: Proposal, reference_month: int) -> dict:
    import json as json_lib
    from sqlalchemy import select
    from app.models import Lead, PreAnalysisPauta

    lead = db.get(Lead, proposal.lead_id) if proposal.lead_id else None
    terms = json_lib.loads(proposal.terms_json or "{}")
    pauta = db.scalar(select(PreAnalysisPauta).where(PreAnalysisPauta.proposal_id == proposal.id))
    engine = json_lib.loads(pauta.engine_result_json) if pauta and pauta.engine_result_json else {}
    client_name = terms.get("company_name") or (lead.name if lead else "Cliente")
    client_cnpj = terms.get("company_cnpj") or (lead.document if lead else "—")
    property_registry = (
        terms.get("property_registry")
        or engine.get("matricula_imovel")
        or engine.get("numero_matricula")
        or "Matrícula vinculada ao contrato"
    )
    registry_office = terms.get("registry_office") or engine.get("cartorio") or "Ofício de Registro de Imóveis competente"
    return {
        "client_name": client_name,
        "client_cnpj": client_cnpj,
        "property_registry": property_registry,
        "registry_office": registry_office,
        "ipca_adjusted": reference_month in {13, 25},
    }


def receipt_pdf(
    *,
    contract: Contract,
    proposal: Proposal,
    invoice: Invoice,
    fruicao: Decimal,
    amortizacao: Decimal,
    total_paid: Decimal,
    tax_withheld: Decimal,
    authenticity_hash: str,
    reference_month: int,
    client_name: str = "Cliente",
    client_cnpj: str = "—",
    property_registry: str = "Matrícula vinculada ao contrato",
    registry_office: str = "Ofício de Registro de Imóveis competente",
    ipca_adjusted: bool = False,
) -> bytes:
    buffer = io.BytesIO()
    doc = SimpleDocTemplate(
        buffer, pagesize=A4, rightMargin=18 * mm, leftMargin=18 * mm,
        topMargin=18 * mm, bottomMargin=18 * mm,
    )
    styles = getSampleStyleSheet()
    styles.add(ParagraphStyle(
        name="ReceiptTitle", parent=styles["Title"],
        textColor=HexColor("#0B5D3B"), fontSize=16, spaceAfter=10,
    ))
    styles.add(ParagraphStyle(
        name="ReceiptBody", parent=styles["BodyText"],
        fontSize=9.5, leading=14, spaceAfter=8,
    ))
    brl = lambda v: f"R$ {Decimal(v):,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")
    rows = [
        ["I. Taxa de fruição patrimonial (juros)", brl(fruicao)],
        ["II. Amortização da recompra (capital principal)", brl(amortizacao)],
        ["III. Valor total liquidado na data", brl(total_paid)],
        ["Imposto SPE (Lucro Presumido 11,33% s/ fruição)", brl(tax_withheld)],
    ]
    story = [
        Paragraph("LETTER ATIVOS IMOBILIÁRIOS SPE LTDA", styles["ReceiptTitle"]),
        Paragraph(
            f"CNPJ/ME nº {settings.spe_cnpj} — Inscrição Municipal nº {settings.spe_municipal_registration}",
            styles["ReceiptBody"],
        ),
        Paragraph("Módulo Central FinOps — Recibo de Quitação Mensal de Fruição e Amortização", styles["ReceiptBody"]),
        Paragraph(
            f"Contrato <b>{contract.contract_number}</b> · Fatura <b>{invoice.invoice_number}</b> · "
            f"Competência mês <b>{reference_month}</b>"
            + (" · <b>Parcela com reajuste IPCA anual</b>" if ipca_adjusted else ""),
            styles["ReceiptBody"],
        ),
        Spacer(1, 4 * mm),
        Paragraph("<b>DEMONSTRATIVO CONTÁBIL DETALHADO DO PERÍODO</b>", styles["ReceiptBody"]),
        Table(rows, colWidths=[95 * mm, 55 * mm], style=TableStyle([
            ("BACKGROUND", (0, 0), (0, -1), HexColor("#E8F5EE")),
            ("TEXTCOLOR", (0, 0), (0, -1), HexColor("#0B5D3B")),
            ("FONTNAME", (0, 0), (0, -1), "Helvetica-Bold"),
            ("GRID", (0, 0), (-1, -1), 0.4, HexColor("#C9D8D0")),
            ("FONTSIZE", (0, 0), (-1, -1), 9),
            ("TOPPADDING", (0, 0), (-1, -1), 7),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 7),
        ])),
        Spacer(1, 6 * mm),
        Paragraph(
            "Declaramos para os devidos fins de direito, regularidade contábil e quitação de parcelas que recebemos "
            f"da pessoa jurídica <b>{client_name}</b>, inscrita no CNPJ/ME sob o nº <b>{client_cnpj}</b>, "
            f"o valor total de <b>{brl(total_paid)}</b>, correspondente à liquidação da parcela "
            f"<b>{invoice.invoice_number}</b> do Contrato de Compra e Venda com Pacto Expresso de Retrovenda "
            f"do imóvel colateralizado sob a matrícula nº <b>{property_registry}</b> do "
            f"<b>{registry_office}</b>.",
            styles["ReceiptBody"],
        ),
        Paragraph(
            "O valor discriminado no Item I (Taxa de Fruição) foi auferido pela emitente sob a rubrica estrita de "
            "receita de fruição patrimonial precária de imóvel próprio (CNAE 68.10-2-02), constituindo a base de "
            "incidência dos tributos federais sob o regime do Lucro Presumido. O montante discriminado no Item II "
            "(Amortização da Recompra) foi lançado de forma direta na escrituração como redução do ativo imobiliário "
            "circulante, abatendo de pleno direito o saldo devedor residual para fins de exercício futuro do direito "
            "de retrovenda e resgate do bem.",
            styles["ReceiptBody"],
        ),
        Paragraph(
            "A presente transação financeira é ISENTA DE ISS (Imposto Sobre Serviços de Qualquer Natureza) por força "
            "da Súmula Vinculante nº 31 do Supremo Tribunal Federal (STF) e amparada pelos Arts. 505 e 506 do "
            "Código Civil Brasileiro, conferindo validade fiscal e contábil plena para dedução de despesas "
            "operacionais líquidas da tomadora perante a Secretaria da Receita Federal do Brasil.",
            styles["ReceiptBody"],
        ),
        Paragraph(
            f"Hash de autenticidade: <font name='Courier'>{authenticity_hash}</font>",
            styles["ReceiptBody"],
        ),
        Paragraph(
            f"{settings.spe_city}, {datetime.now(UTC).strftime('%d/%m/%Y')}.",
            styles["ReceiptBody"],
        ),
        Paragraph("LETTER ATIVOS IMOBILIÁRIOS SPE LTDA — SISTEMA AUTOMATIZADO FINOPS", styles["ReceiptBody"]),
    ]
    doc.build(story)
    return buffer.getvalue()


def compute_authenticity_hash(contract_id: str, month: int, fruicao: Decimal, amortizacao: Decimal) -> str:
    raw = f"{contract_id}_{month}_{fruicao}_{amortizacao}_{datetime.now(UTC).strftime('%Y%m%d')}"
    return "sha256_" + hashlib.sha256(raw.encode()).hexdigest()
