import hashlib
import io
import re
from datetime import UTC, datetime
from pathlib import Path
from uuid import uuid4

from fastapi import HTTPException, UploadFile
from reportlab.lib.colors import HexColor
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.units import mm
from reportlab.platypus import Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle

from app.core.config import settings
from app.models import CalculationMemory, Contract, Document, Proposal, User
from app.storage_service import get_storage

ALLOWED_TYPES = {
    "application/pdf": (b"%PDF",),
    "image/png": (b"\x89PNG",),
    "image/jpeg": (b"\xff\xd8\xff",),
    "application/xml": (b"<?xml", b"<"),
    "text/xml": (b"<?xml", b"<"),
    "application/vnd.openxmlformats-officedocument.wordprocessingml.document": (b"PK",),
}


def safe_name(filename: str) -> str:
    name = Path(filename).name
    name = re.sub(r"[^A-Za-z0-9._-]", "_", name)
    return name[:180] or "documento"


async def persist_upload(upload: UploadFile, user: User, entity_type: str, entity_id: str, kind: str) -> Document:
    content_type = (upload.content_type or "").lower()
    if content_type not in ALLOWED_TYPES:
        raise HTTPException(status_code=415, detail="Tipo de arquivo não permitido")
    data = await upload.read(settings.max_upload_mb * 1024 * 1024 + 1)
    if len(data) > settings.max_upload_mb * 1024 * 1024:
        raise HTTPException(status_code=413, detail=f"Arquivo excede {settings.max_upload_mb} MB")
    if not data or not any(data.startswith(prefix) for prefix in ALLOWED_TYPES[content_type]):
        raise HTTPException(status_code=422, detail="Conteúdo não corresponde ao tipo declarado")
    digest = hashlib.sha256(data).hexdigest()
    filename = safe_name(upload.filename or "documento")
    relative = Path(user.organization_id) / datetime.now(UTC).strftime("%Y/%m") / f"{uuid4().hex}-{filename}"
    get_storage().put(str(relative),data,content_type)
    return Document(
        organization_id=user.organization_id, entity_type=entity_type, entity_id=entity_id,
        kind=kind, filename=filename, storage_key=str(relative), sha256=digest,
        status="QUARANTINED", uploaded_by_id=user.id,
    )


def contract_pdf(contract: Contract, proposal: Proposal, calculation: CalculationMemory) -> bytes:
    buffer = io.BytesIO()
    doc = SimpleDocTemplate(buffer, pagesize=A4, rightMargin=18*mm, leftMargin=18*mm, topMargin=18*mm, bottomMargin=18*mm)
    styles = getSampleStyleSheet()
    styles.add(ParagraphStyle(name="LetterTitle", parent=styles["Title"], textColor=HexColor("#0B5D3B"), fontSize=20, spaceAfter=12))
    styles.add(ParagraphStyle(name="LetterBody", parent=styles["BodyText"], fontSize=9.5, leading=14, spaceAfter=8))
    output = __import__("json").loads(calculation.output_json)
    rows = [["Produto", proposal.product], ["Valor solicitado", f"R$ {proposal.requested_amount}"], ["Fórmula", calculation.formula_version]]
    field_labels = {
        "credit_total": "Crédito total", "premium_total": "Ágio", "platform_fee": "Fee da plataforma",
        "start_fee": "Taxa de Start", "total_due": "Total calculado", "principal": "Principal",
        "total_interest": "Juros totais", "investor_interest": "Remuneração dos investidores",
        "platform_spread": "Spread LETTER", "maturity_total": "Total no vencimento",
        "start_fee_total": "Taxa de Start", "start_fee_milestone_1": "Taxa de Start — Marco 1",
        "start_fee_milestone_2": "Taxa de Start — Marco 2", "intermediation_fee": "Fee de intermediação",
        "asset_value": "Valor do bem", "ltv_percent": "LTV (%)", "monthly_payment": "Parcela",
        "balloon_payment": "Parcela Balloon", "management_fee_total": "Taxa de gestão",
        "itbi_provision": "Provisão ITBI", "structuring_fee": "Fee de estruturação",
        "net_payout": "Payout líquido", "total_contract": "Total do contrato",
    }
    for field, label in field_labels.items():
        if field in output:
            prefix = "" if field == "ltv_percent" else "R$ "
            suffix = "%" if field == "ltv_percent" else ""
            rows.append([label, f"{prefix}{output[field]}{suffix}"])
    story = [
        Paragraph("LETTER — Instrumento de Operação", styles["LetterTitle"]),
        Paragraph(f"Contrato nº <b>{contract.contract_number}</b>", styles["LetterBody"]),
        Paragraph("Este documento é uma minuta técnica gerada pela plataforma e deve utilizar template jurídico homologado antes da produção.", styles["LetterBody"]),
        Spacer(1, 4*mm),
        Table(rows, colWidths=[52*mm, 100*mm], style=TableStyle([
            ("BACKGROUND",(0,0),(0,-1),HexColor("#E8F5EE")), ("TEXTCOLOR",(0,0),(0,-1),HexColor("#0B5D3B")),
            ("FONTNAME",(0,0),(0,-1),"Helvetica-Bold"), ("FONTNAME",(1,0),(1,-1),"Helvetica"),
            ("FONTSIZE",(0,0),(-1,-1),9), ("GRID",(0,0),(-1,-1),0.4,HexColor("#C9D8D0")),
            ("VALIGN",(0,0),(-1,-1),"MIDDLE"), ("TOPPADDING",(0,0),(-1,-1),7), ("BOTTOMPADDING",(0,0),(-1,-1),7),
        ])),
        Spacer(1, 7*mm),
        Paragraph("Condições essenciais", styles["Heading2"]),
        Paragraph("A liberação de valores depende do cumprimento das condições precedentes, validação documental, confirmação da transferência e aprovações previstas no workflow. Nenhum payout é realizado automaticamente por inteligência artificial.", styles["LetterBody"]),
        Paragraph("Integridade e evidência", styles["Heading2"]),
        Paragraph(f"Hash SHA-256 da versão: <font name='Courier'>{contract.content_hash}</font>", styles["LetterBody"]),
        Paragraph(f"Status: {contract.status} | Template: {contract.template_version}", styles["LetterBody"]),
    ]
    doc.build(story)
    return buffer.getvalue()
