import hashlib
import html
import io
import json
from datetime import UTC, date, datetime, timedelta
from decimal import Decimal, ROUND_HALF_UP

from fastapi import HTTPException
from sqlalchemy import func, select
from sqlalchemy.orm import Session
from reportlab.lib.colors import HexColor
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import mm
from reportlab.platypus import Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle

from app.models import (
    DelinquencyCase, Invoice, NinaCriticalApproval, NinaDistressCase,
    NinaDistressEvent, NinaLegalDocument, Operation, Proposal, Quota, User, Contract,
)


CRITICAL_GATES={"CASH_HOLD","CARTORIO_NOTICE","CADUCITY","AUCTION_PUBLICATION"}
DOCUMENT_TYPES={"EXTRAJUDICIAL_NOTICE","VACATE_NOTICE","AUCTION_EDICT","AUCTION_RECORD"}


def money(value:Decimal)->Decimal:
    return value.quantize(Decimal("0.01"),rounding=ROUND_HALF_UP)


def canonical_hash(payload:dict)->str:
    raw=json.dumps(payload,ensure_ascii=False,separators=(",",":"),sort_keys=True)
    return hashlib.sha256(raw.encode()).hexdigest()


def add_event(db:Session,user:User|None,case:NinaDistressCase,event_key:str,event_type:str,status:str,payload:dict)->NinaDistressEvent:
    existing=db.scalar(select(NinaDistressEvent).where(NinaDistressEvent.case_id==case.id,NinaDistressEvent.event_key==event_key))
    if existing:return existing
    body={"case_id":case.id,"event_key":event_key,"event_type":event_type,"status":status,"payload":payload}
    item=NinaDistressEvent(organization_id=case.organization_id,case_id=case.id,event_key=event_key,event_type=event_type,status=status,payload_json=json.dumps(payload,ensure_ascii=False),evidence_hash=canonical_hash(body),actor_id=user.id if user else None)
    db.add(item);return item


def create_distress_case(db:Session,user:User,delinquency:DelinquencyCase,appraisal_value:Decimal|None,photo_reference:str|None,matched_quota_id:str|None,daily_reduction:Decimal)->NinaDistressCase:
    existing=db.scalar(select(NinaDistressCase).where(NinaDistressCase.delinquency_case_id==delinquency.id))
    if existing:return existing
    invoice=db.get(Invoice,delinquency.invoice_id);proposal=db.get(Proposal,invoice.proposal_id) if invoice else None
    if not invoice or not proposal or proposal.product not in {"FLASH_CREDIT","SDC"}:
        raise HTTPException(status_code=422,detail="NINA Asset exige inadimplência vinculada a SDC ou Flash Capital")
    contract=db.scalar(select(Contract).where(Contract.proposal_id==proposal.id))
    if not photo_reference and contract:
        from app.collateral_native_inspection_service import resolve_auction_photo_reference
        photo_reference=resolve_auction_photo_reference(db,proposal.id,contract.id)
    operation=db.scalar(select(Operation).where(Operation.proposal_id==proposal.id))
    if matched_quota_id and not db.scalar(select(Quota).where(Quota.id==matched_quota_id,Quota.organization_id==user.organization_id)):raise HTTPException(status_code=404,detail="Cota casada não encontrada")
    case=NinaDistressCase(organization_id=user.organization_id,delinquency_case_id=delinquency.id,operation_id=operation.id if operation else None,days_overdue=delinquency.days_overdue,appraisal_value_avm=money(appraisal_value) if appraisal_value else None,photo_storage_reference=photo_reference,matched_quota_id=matched_quota_id,daily_reduction_amount=money(daily_reduction),legal_hold=True)
    db.add(case);db.flush();add_event(db,user,case,"CASE_CREATED","CASE_CREATED","RECORDED",{"source":"DELINQUENCY","legal_hold":True});evaluate_timeline(db,user,case);return case


def evaluate_timeline(db:Session,user:User,case:NinaDistressCase,as_of:date|None=None)->NinaDistressCase:
    delinquency=db.get(DelinquencyCase,case.delinquency_case_id);invoice=db.get(Invoice,delinquency.invoice_id) if delinquency else None
    if not delinquency or not invoice:raise HTTPException(status_code=404,detail="Origem da inadimplência não encontrada")
    reference=as_of or date.today();days=max(0,(reference-invoice.due_date).days);case.days_overdue=days;delinquency.days_overdue=days
    if invoice.status=="PAID":
        case.stage="CURED";case.next_action_at=None;add_event(db,user,case,"CASE_CURED","CASE_CURED","COMPLETED",{"paid_at":invoice.paid_at.isoformat() if invoice.paid_at else None});return case
    milestones=[
        (1,"FRIENDLY_COLLECTION","FRIENDLY_ALERT_WINDOW","SIMULATED",{"channels":["EMAIL","WHATSAPP"],"window":"H+1_H+5"}),
        (6,"CASH_HOLD_PENDING","CASH_HOLD_REQUESTED","AWAITING_APPROVAL",{"execution":"BLOCKED_BY_GATE"}),
        (16,"NOTICE_PENDING","CARTORIO_NOTICE_REQUESTED","AWAITING_APPROVAL",{"provider":"NOT_CONFIGURED"}),
        (30,"CADUCITY_WARNING","CADUCITY_TIMER_STARTED","DISPLAY_ONLY",{"deadline_day":61}),
        (61,"EXECUTION_REVIEW","CADUCITY_REVIEW_REQUESTED","AWAITING_DUAL_APPROVAL",{"automatic_execution":False}),
    ]
    for threshold,stage,event_type,status,payload in milestones:
        if days>=threshold:add_event(db,user,case,f"TIMELINE_D{threshold}",event_type,status,{"days_overdue":days,**payload});case.stage=stage
    if days>=6 and case.cash_hold_status=="NOT_REQUESTED":case.cash_hold_status="PENDING_APPROVAL"
    if days>=16 and case.legal_notice_status=="NOT_REQUESTED":case.legal_notice_status="PENDING_APPROVAL"
    if days>=61:
        case.caducity_status="PENDING_LEGAL_REVIEW";case.auction_status="BLOCKED";delinquency.caducity_eligible=True
    next_threshold=next((x for x in (1,6,16,30,61) if x>days),None)
    case.next_action_at=datetime.combine(invoice.due_date+timedelta(days=next_threshold),datetime.min.time(),tzinfo=UTC) if next_threshold else None
    return case


def record_approval(db:Session,user:User,case:NinaDistressCase,gate:str,decision:str,notes:str)->NinaCriticalApproval:
    gate=gate.upper();decision=decision.upper()
    if gate not in CRITICAL_GATES:raise HTTPException(status_code=422,detail="Gate crítico inválido")
    if decision not in {"APPROVED","REJECTED"}:raise HTTPException(status_code=422,detail="Decisão inválida")
    existing=db.scalar(select(NinaCriticalApproval).where(NinaCriticalApproval.case_id==case.id,NinaCriticalApproval.gate==gate,NinaCriticalApproval.approver_id==user.id))
    if existing:
        existing.decision=decision;existing.notes=notes;existing.decided_at=datetime.now(UTC);item=existing
    else:
        item=NinaCriticalApproval(organization_id=user.organization_id,case_id=case.id,gate=gate,decision=decision,notes=notes,approver_id=user.id);db.add(item)
    add_event(db,user,case,f"APPROVAL_{gate}_{user.id}","CRITICAL_APPROVAL",decision,{"gate":gate,"notes":notes});return item


def apply_gate(db:Session,user:User,case:NinaDistressCase,gate:str)->NinaDistressCase:
    gate=gate.upper()
    if gate not in CRITICAL_GATES:raise HTTPException(status_code=422,detail="Gate crítico inválido")
    approvals=list(db.scalars(select(NinaCriticalApproval).where(NinaCriticalApproval.case_id==case.id,NinaCriticalApproval.gate==gate)))
    if any(x.decision=="REJECTED" for x in approvals):raise HTTPException(status_code=409,detail="Gate possui rejeição registrada")
    approved={x.approver_id for x in approvals if x.decision=="APPROVED"};required=2 if gate in {"CADUCITY","AUCTION_PUBLICATION"} else 1
    if len(approved)<required:raise HTTPException(status_code=409,detail=f"Gate exige {required} aprovação(ões) distinta(s)")
    if gate=="CASH_HOLD":
        if case.days_overdue<6:raise HTTPException(status_code=409,detail="Marco H+6 ainda não atingido")
        case.cash_hold_status="SIMULATED_HOLD";case.stage="CASH_HOLD_SIMULATED"
    elif gate=="CARTORIO_NOTICE":
        if case.days_overdue<16:raise HTTPException(status_code=409,detail="Marco H+16 ainda não atingido")
        case.legal_notice_status="READY_FOR_PROVIDER";case.stage="MORA_DOCUMENTATION_READY"
    elif gate=="CADUCITY":
        if case.days_overdue<61:raise HTTPException(status_code=409,detail="Marco H+61 ainda não atingido")
        case.caducity_status="APPROVED_FOR_SANDBOX";case.stage="CADUCITY_APPROVED_SANDBOX"
    elif gate=="AUCTION_PUBLICATION":
        if case.caducity_status!="APPROVED_FOR_SANDBOX":raise HTTPException(status_code=409,detail="Caducidade ainda não aprovada")
        if not case.appraisal_value_avm or not case.photo_storage_reference:raise HTTPException(status_code=409,detail="AVM e referência de fotos são obrigatórios")
        opening=money(Decimal(str(case.appraisal_value_avm))*Decimal(str(case.opening_price_percent))/Decimal("100"));case.current_auction_price=opening;case.auction_status="SANDBOX_READY";case.stage="AUCTION_SANDBOX_READY";case.voluntary_vacate_deadline=datetime.now(UTC)+timedelta(days=15)
    add_event(db,user,case,f"GATE_APPLIED_{gate}","GATE_APPLIED","SANDBOX_ONLY",{"gate":gate,"approvals":len(approved),"production_effect":False});return case


def generate_legal_document(db:Session,user:User,case:NinaDistressCase,document_type:str,variables:dict)->NinaLegalDocument:
    document_type=document_type.upper()
    if document_type not in DOCUMENT_TYPES:raise HTTPException(status_code=422,detail="Tipo documental inválido")
    version=(db.scalar(select(func.max(NinaLegalDocument.version)).where(NinaLegalDocument.case_id==case.id,NinaLegalDocument.document_type==document_type)) or 0)+1
    content={"template":"NINA_ASSET_2026_DRAFT","document_type":document_type,"case_id":case.id,"stage":case.stage,"variables":variables,"disclaimer":"MINUTA SEM EFEITO JURÍDICO OU REGISTRAL. EXIGE REVISÃO JURÍDICA E PROVEDOR OFICIAL."}
    item=NinaLegalDocument(organization_id=user.organization_id,case_id=case.id,document_type=document_type,version=version,status="DRAFT_LEGAL_REVIEW",content_json=json.dumps(content,ensure_ascii=False),content_hash=canonical_hash(content),created_by_id=user.id);db.add(item);db.flush();add_event(db,user,case,f"DOCUMENT_{document_type}_V{version}","DOCUMENT_GENERATED","DRAFT_LEGAL_REVIEW",{"document_id":item.id,"hash":item.content_hash});return item


def reduce_sandbox_prices(db:Session,user:User)->list[NinaDistressCase]:
    cases=list(db.scalars(select(NinaDistressCase).where(NinaDistressCase.organization_id==user.organization_id,NinaDistressCase.auction_status=="SANDBOX_READY")))
    changed=[]
    for case in cases:
        floor=money(Decimal(str(case.appraisal_value_avm))*Decimal(str(case.floor_price_percent))/Decimal("100"));current=Decimal(str(case.current_auction_price));updated=max(floor,current-Decimal(str(case.daily_reduction_amount)))
        if updated<current:
            case.current_auction_price=money(updated);add_event(db,user,case,f"PRICE_REDUCTION_{datetime.now(UTC).date().isoformat()}","SANDBOX_PRICE_REDUCED","COMPLETED",{"previous":str(current),"current":str(money(updated)),"floor":str(floor)});changed.append(case)
    return changed


def legal_document_pdf(document:NinaLegalDocument)->bytes:
    content=json.loads(document.content_json);variables=content.get("variables",{})
    titles={"EXTRAJUDICIAL_NOTICE":"Minuta de Notificação Extrajudicial","VACATE_NOTICE":"Minuta de Notificação de Desocupação","AUCTION_EDICT":"Minuta de Edital de Leilão Extrajudicial","AUCTION_RECORD":"Minuta de Ata de Arrematação"}
    buffer=io.BytesIO();doc=SimpleDocTemplate(buffer,pagesize=A4,rightMargin=18*mm,leftMargin=18*mm,topMargin=18*mm,bottomMargin=18*mm)
    styles=getSampleStyleSheet();styles.add(ParagraphStyle(name="NinaTitle",parent=styles["Title"],textColor=HexColor("#0B5D3B"),fontSize=18,spaceAfter=12));styles.add(ParagraphStyle(name="NinaBody",parent=styles["BodyText"],fontSize=9.5,leading=14,spaceAfter=8))
    rows=[["Campo","Valor"]]+[[html.escape(str(k)),html.escape(str(v))] for k,v in sorted(variables.items())]
    story=[Paragraph("NINA ASSET · DOCUMENTO CONTROLADO",styles["NinaTitle"]),Paragraph(titles.get(document.document_type,document.document_type),styles["Heading2"]),Paragraph(f"Caso: <font name='Courier'>{document.case_id}</font> · Versão {document.version}",styles["NinaBody"]),Paragraph("<b>MINUTA SEM EFEITO JURÍDICO, REGISTRAL OU FINANCEIRO.</b> Exige revisão jurídica, aprovações do workflow e provedor oficial homologado.",styles["NinaBody"]),Spacer(1,4*mm)]
    if len(rows)>1:story.append(Table(rows,colWidths=[55*mm,100*mm],repeatRows=1,style=TableStyle([("BACKGROUND",(0,0),(-1,0),HexColor("#0B5D3B")),("TEXTCOLOR",(0,0),(-1,0),HexColor("#FFFFFF")),("GRID",(0,0),(-1,-1),0.4,HexColor("#C9D8D0")),("FONTSIZE",(0,0),(-1,-1),9),("VALIGN",(0,0),(-1,-1),"MIDDLE"),("TOPPADDING",(0,0),(-1,-1),7),("BOTTOMPADDING",(0,0),(-1,-1),7)])))
    story.extend([Spacer(1,7*mm),Paragraph("Controles obrigatórios",styles["Heading2"]),Paragraph("Este arquivo é uma prévia técnica. Publicação, constituição em mora, consolidação patrimonial, desocupação, transferência de propriedade e liquidação dependem de análise humana e documentação oficial.",styles["NinaBody"]),Paragraph(f"Hash de integridade: <font name='Courier'>{document.content_hash}</font>",styles["NinaBody"])])
    doc.build(story);return buffer.getvalue()
