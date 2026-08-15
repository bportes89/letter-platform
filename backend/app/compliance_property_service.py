import hashlib
import io
import json
import re
from datetime import UTC, datetime, timedelta
from decimal import Decimal, ROUND_HALF_UP
from uuid import uuid4

from fastapi import HTTPException
from reportlab.lib.colors import HexColor
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import mm
from reportlab.platypus import Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import (Contract, Document, OperationalJob, SellerEvidenceAudit,
                        StructuredPropertyCase, StructuredPropertyEvent, User)


def money(value: Decimal) -> Decimal:
    return value.quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)


def digest(payload: dict) -> str:
    return hashlib.sha256(json.dumps(payload,ensure_ascii=False,sort_keys=True,separators=(",", ":")).encode()).hexdigest()


def clean_document(value: str) -> str:
    return re.sub(r"\D", "", value)


def mask_document(value: str) -> str:
    clean=clean_document(value)
    return f"***{clean[-4:]}" if len(clean)>=4 else "****"


def require_documents(db: Session, user: User, ids: list[str]) -> list[Document]:
    rows=list(db.scalars(select(Document).where(Document.organization_id==user.organization_id,Document.id.in_(ids))))
    if len(rows)!=len(set(ids)): raise HTTPException(404,"Um ou mais lastros documentais não foram encontrados")
    if any(x.status not in {"QUARANTINED","APPROVED"} for x in rows): raise HTTPException(409,"Lastro documental em estado inválido")
    return rows


def cross_validate_seller_evidence(db: Session, user: User, contract: Contract, *, buyer_document: str,
        seller_document: str, statement_document_id: str, protocol_document_id: str, assignment_document_id: str,
        statement_ocr_text: str, protocol_ocr_text: str, assignment_ocr_text: str) -> SellerEvidenceAudit:
    existing=db.scalar(select(SellerEvidenceAudit).where(SellerEvidenceAudit.contract_id==contract.id))
    if existing:return existing
    docs=require_documents(db,user,[statement_document_id,protocol_document_id,assignment_document_id])
    buyer=clean_document(buyer_document);seller=clean_document(seller_document)
    statement_ok="CONTEMPLADA" in statement_ocr_text.upper()
    protocol_match=re.search(r"(?:PROTOCOLO|N[º°ÚU]MERO)\s*[:#-]?\s*([A-Z0-9-]{5,30})",protocol_ocr_text.upper())
    protocol=protocol_match.group(1) if protocol_match else None
    assignment_digits=clean_document(assignment_ocr_text)
    parties=bool(buyer and seller and buyer in assignment_digits and seller in assignment_digits)
    signature=any(x in assignment_ocr_text.upper() for x in ("FIRMA","AUTENTICIDADE","RECONHEÇO","TABELIÃO","TABELIAO","CARTÓRIO","CARTORIO","ICP-BRASIL"))
    failures=[]
    if not statement_ok:failures.append("extrato sem status CONTEMPLADA")
    if not protocol:failures.append("protocolo da administradora não detectado")
    if not parties:failures.append("CPF/CNPJ das partes divergente no termo")
    if not signature:failures.append("evidência de assinatura/reconhecimento não detectada")
    evidence={"contract_id":contract.id,"documents":sorted([x.sha256 for x in docs]),"statement_contemplated":statement_ok,
              "protocol":protocol,"parties_matched":parties,"signature_evidence_detected":signature}
    item=SellerEvidenceAudit(organization_id=user.organization_id,contract_id=contract.id,
        buyer_document_masked=mask_document(buyer),seller_document_masked=mask_document(seller),
        statement_document_id=statement_document_id,protocol_document_id=protocol_document_id,assignment_document_id=assignment_document_id,
        statement_contemplated=statement_ok,administrator_protocol=protocol,parties_matched=parties,
        signature_evidence_detected=signature,status="OCR_PASSED_PENDING_REVIEW" if not failures else "REJECTED_DIVERGENT",
        rejection_reason="; ".join(failures) or None,evidence_hash=digest(evidence))
    db.add(item);db.flush();return item


def review_seller_audit(user: User, item: SellerEvidenceAudit, decision: str, notes: str) -> SellerEvidenceAudit:
    if item.status not in {"OCR_PASSED_PENDING_REVIEW","REJECTED_DIVERGENT"}: raise HTTPException(409,"Auditoria já revisada")
    decision=decision.upper()
    if decision not in {"APPROVE","REJECT"}:raise HTTPException(422,"Decisão inválida")
    if decision=="APPROVE" and not all([item.statement_contemplated,item.administrator_protocol,item.parties_matched,item.signature_evidence_detected]):
        raise HTTPException(409,"Divergências de OCR impedem aprovação")
    item.status="APPROVED" if decision=="APPROVE" else "REJECTED_MANUAL"
    item.manual_review_status="APPROVED" if decision=="APPROVE" else "REJECTED"
    item.reviewed_by_id=user.id;item.reviewed_at=datetime.now(UTC)
    if decision=="REJECT":item.rejection_reason=notes
    return item


def add_property_event(db: Session, user: User | None, case: StructuredPropertyCase, key: str, kind: str, status: str, payload: dict):
    existing=db.scalar(select(StructuredPropertyEvent).where(StructuredPropertyEvent.case_id==case.id,StructuredPropertyEvent.event_key==key))
    if existing:return existing
    body={"case_id":case.id,"key":key,"type":kind,"status":status,"payload":payload}
    item=StructuredPropertyEvent(organization_id=case.organization_id,case_id=case.id,event_key=key,event_type=kind,status=status,
        payload_json=json.dumps(payload,ensure_ascii=False,sort_keys=True),evidence_hash=digest(body),actor_id=user.id if user else None)
    db.add(item);return item


def create_property_case(db: Session, user: User, *, operation_id: str | None, buyer_document: str, seller_document: str,
        has_lien_debt: bool, unregistered_construction: bool, land_appraisal_value: Decimal,
        future_appraisal_value: Decimal, estimated_debt: Decimal) -> StructuredPropertyCase:
    land=money(land_appraisal_value);future=money(future_appraisal_value);debt=money(estimated_debt)
    if land<=0 or future<=0:raise HTTPException(422,"Avaliações devem ser positivas")
    if future<land:raise HTTPException(422,"AVM futuro não pode ser inferior ao valor do lote")
    gross=money(future*Decimal("0.40"))
    if has_lien_debt and debt>=gross:raise HTTPException(422,"Dívida estimada consome ou supera o LTV máximo de 40%")
    phase1=money(land*Decimal("0.40")) if unregistered_construction else gross
    phase2=money(gross-phase1)
    route="UNREGISTERED_CONSTRUCTION" if unregistered_construction else ("INTERVENING_PAYOFF" if has_lien_debt else "CLEAN_GUARANTEE")
    payload={"route":route,"ltv_percent":"40.00","land":str(land),"future":str(future),"gross":str(gross),"debt":str(debt),"phase1":str(phase1),"phase2":str(phase2)}
    case=StructuredPropertyCase(organization_id=user.organization_id,operation_id=operation_id,case_reference=f"NPROP-{uuid4().hex[:12].upper()}",
        buyer_document_masked=mask_document(buyer_document),seller_document_masked=mask_document(seller_document),has_lien_debt=has_lien_debt,
        unregistered_construction=unregistered_construction,route=route,land_appraisal_value=land,future_appraisal_value=future,
        gross_payout=gross,estimated_debt=debt,phase1_amount=phase1,phase2_amount=phase2,
        iq_status="AWAITING_PAYOFF_DOCUMENT" if has_lien_debt else "NOT_APPLICABLE",phase_status="AWAITING_REGISTRY" if unregistered_construction else "AWAITING_PHASE1_APPROVAL",
        evidence_hash=digest(payload),legal_hold=True)
    db.add(case);db.flush();add_property_event(db,user,case,"CASE_CREATED","PROPERTY_CASE_CREATED","RECORDED",payload);return case


def attach_iq_document(db: Session, user: User, case: StructuredPropertyCase, document_id: str):
    require_documents(db,user,[document_id]);case.iq_document_id=document_id;case.iq_status="DOCUMENT_PENDING_REVIEW"
    return add_property_event(db,user,case,"IQ_DOCUMENT_ATTACHED","IQ_DOCUMENT_ATTACHED","PENDING_REVIEW",{"document_id":document_id})


def approve_iq(db: Session, user: User, case: StructuredPropertyCase):
    if not case.has_lien_debt or case.iq_status!="DOCUMENT_PENDING_REVIEW":raise HTTPException(409,"Interveniente quitante não está pronto para revisão")
    case.iq_status="SANDBOX_SETTLEMENT_APPROVED";return add_property_event(db,user,case,"IQ_APPROVED","IQ_APPROVED","SANDBOX_ONLY",{"automatic_pix":False})


def release_phase1(db: Session, user: User, case: StructuredPropertyCase):
    if case.has_lien_debt and case.iq_status!="SANDBOX_SETTLEMENT_APPROVED":raise HTTPException(409,"Interveniente quitante pendente")
    if case.phase_status not in {"AWAITING_REGISTRY","AWAITING_PHASE1_APPROVAL"}:raise HTTPException(409,"Fase 1 indisponível")
    now=datetime.now(UTC);case.phase_status="PHASE1_SANDBOX_RELEASED";case.registration_deadline_at=now+timedelta(days=90);case.legal_hold=True
    add_property_event(db,user,case,"PHASE1_RELEASED","PHASE1_RELEASED","SANDBOX_ONLY",{"amount":str(case.phase1_amount),"real_transfer":False,"deadline":case.registration_deadline_at.isoformat()})
    for suffix,at,kind in [("start",now,"PROPERTY_REGISTRATION_90D_STARTED"),("30d",case.registration_deadline_at-timedelta(days=30),"PROPERTY_REGISTRATION_REMINDER_30D"),("7d",case.registration_deadline_at-timedelta(days=7),"PROPERTY_REGISTRATION_REMINDER_7D"),("1d",case.registration_deadline_at-timedelta(days=1),"PROPERTY_REGISTRATION_REMINDER_1D")]:
        db.add(OperationalJob(organization_id=user.organization_id,job_type=kind,idempotency_key=f"property:{case.id}:{suffix}",scheduled_at=at,
            payload_json=json.dumps({"case_id":case.id,"deadline":case.registration_deadline_at.isoformat(),"channels":["PUSH","EMAIL"]})))
    return case


def submit_registration(db: Session, user: User, case: StructuredPropertyCase, document_id: str):
    if case.phase_status!="PHASE1_SANDBOX_RELEASED":raise HTTPException(409,"Caso não está aguardando matrícula averbada")
    require_documents(db,user,[document_id]);case.registered_property_document_id=document_id;case.phase_status="REGISTRATION_PENDING_REVIEW"
    add_property_event(db,user,case,"REGISTRATION_SUBMITTED","REGISTRATION_SUBMITTED","PENDING_HUMAN_REVIEW",{"document_id":document_id});return case


def approve_registration(db: Session, user: User, case: StructuredPropertyCase):
    if case.phase_status!="REGISTRATION_PENDING_REVIEW":raise HTTPException(409,"Matrícula não está pronta para revisão")
    case.phase_status="PHASE2_SANDBOX_READY";case.legal_hold=True
    add_property_event(db,user,case,"REGISTRATION_APPROVED","REGISTRATION_APPROVED","SANDBOX_READY",{"phase2_amount":str(case.phase2_amount),"automatic_payout":False});return case


def evaluate_expiry(db: Session, user: User, case: StructuredPropertyCase, at: datetime | None=None):
    now=at or datetime.now(UTC);deadline=case.registration_deadline_at
    if case.phase_status=="PHASE1_SANDBOX_RELEASED" and deadline and now>(deadline if deadline.tzinfo else deadline.replace(tzinfo=UTC)):
        case.phase_status="EXPIRED_MANUAL_REVIEW";case.legal_hold=True
        add_property_event(db,user,case,"REGISTRATION_EXPIRED","REGISTRATION_EXPIRED","AWAITING_LEGAL_REVIEW",{"automatic_forfeiture":False,"phase2_locked":True})
    return case


def property_requirement_pdf(case: StructuredPropertyCase) -> bytes:
    buffer=io.BytesIO();styles=getSampleStyleSheet();styles.add(ParagraphStyle(name="Letter",parent=styles["BodyText"],fontSize=9.5,leading=14,spaceAfter=7))
    doc=SimpleDocTemplate(buffer,pagesize=A4,rightMargin=18*mm,leftMargin=18*mm,topMargin=18*mm,bottomMargin=18*mm)
    rows=[["Caso",case.case_reference],["Rota",case.route],["Prazo",case.registration_deadline_at.isoformat() if case.registration_deadline_at else "A definir"],["Status",case.phase_status]]
    story=[Paragraph("LETTER — Minuta de Requerimento para Averbação",styles["Title"]),Paragraph("Documento técnico sujeito à assinatura ICP-Brasil e conferência jurídica antes do protocolo no Registro de Imóveis.",styles["Letter"]),
      Table(rows,colWidths=[45*mm,105*mm],style=TableStyle([("GRID",(0,0),(-1,-1),.4,HexColor("#CBD8D1")),("BACKGROUND",(0,0),(0,-1),HexColor("#E8F5EE")),("FONTSIZE",(0,0),(-1,-1),9),("PADDING",(0,0),(-1,-1),7)])),Spacer(1,6*mm),
      Paragraph("Ao Ilustríssimo Senhor Oficial do Registro de Imóveis competente",styles["Heading2"]),Paragraph("A proprietária resolúvel, após validação dos poderes de representação e dos documentos registrais, requer a análise da averbação da construção/benfeitoria na matrícula indicada no dossiê da operação.",styles["Letter"]),
      Paragraph("Anexos esperados: Habite-se ou Certidão de Conclusão de Obra, CND/SERO aplicável, matrícula atualizada e guias de emolumentos. Esta minuta não comprova propriedade, representação, autenticidade ou protocolo cartorial.",styles["Letter"]),Paragraph(f"Hash do caso: <font name='Courier'>{case.evidence_hash}</font>",styles["Letter"])]
    doc.build(story);return buffer.getvalue()
