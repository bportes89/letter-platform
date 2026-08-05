import csv
import hashlib
import io
import json
from calendar import monthrange
from datetime import UTC, date, datetime, timedelta
from decimal import Decimal, ROUND_HALF_UP

from fastapi import HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import (
    CalculationMemory, CollectionAction, Contract, DelinquencyCase, Invoice,
    PaymentEvent, Proposal, ReconciliationBatch, ReconciliationItem, User,
)


def money(value: Decimal) -> Decimal:
    return value.quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)


def add_months(value: date, months: int) -> date:
    month = value.month - 1 + months
    year = value.year + month // 12
    month = month % 12 + 1
    return date(year, month, min(value.day, monthrange(year, month)[1]))


def invoice_number(contract: Contract, installment: int, kind: str) -> str:
    return f"{contract.contract_number}-{installment:03d}-{kind}"


def add_invoice(db: Session, contract: Contract, installment: int, kind: str, due: date, principal: Decimal, interest: Decimal, fee: Decimal) -> Invoice:
    item = Invoice(
        organization_id=contract.organization_id, contract_id=contract.id,
        proposal_id=contract.proposal_id, invoice_number=invoice_number(contract,installment,kind),
        installment_number=installment, kind=kind, due_date=due,
        principal_amount=money(principal), interest_amount=money(interest), fee_amount=money(fee),
        total_amount=money(principal+interest+fee),
    )
    db.add(item); return item


def generate_billing_schedule(db: Session, contract: Contract, proposal: Proposal, calculation: CalculationMemory, start_date: date) -> list[Invoice]:
    existing = list(db.scalars(select(Invoice).where(Invoice.contract_id == contract.id)))
    if existing:
        raise HTTPException(status_code=409, detail="Cronograma financeiro já foi gerado")
    output = json.loads(calculation.output_json)
    rows: list[Invoice] = []
    if calculation.formula_version == "marketplace-v1":
        rows.append(add_invoice(db,contract,1,"MARKETPLACE",start_date+timedelta(days=2),Decimal("0"),Decimal("0"),Decimal(output["total_due"])))
    elif calculation.formula_version == "sdc-bullet-v1":
        milestone_one=Decimal(output["start_fee_milestone_1"]);milestone_two=Decimal(output["start_fee_milestone_2"])
        if milestone_one>0: rows.append(add_invoice(db,contract,0,"START_1",start_date,Decimal("0"),Decimal("0"),milestone_one))
        if milestone_two>0: rows.append(add_invoice(db,contract,0,"START_2",start_date+timedelta(days=30),Decimal("0"),Decimal("0"),milestone_two))
        rows.append(add_invoice(db,contract,int(output["duration_months"]),"BULLET",add_months(start_date,int(output["duration_months"])),Decimal(output["principal"]),Decimal(output["total_interest"]),Decimal("0")))
    elif calculation.formula_version == "flash-credit-v1":
        term=int(output["term_months"]);payment=Decimal(output["monthly_payment"]);source=output["capital_source"]
        months=36 if source=="RETAIL" and term==60 else term
        balance=Decimal(output["principal"])
        total_interest=Decimal(output.get("total_interest","0"));linear_interest=money(total_interest/term) if term else Decimal("0")
        for number in range(1,months+1):
            if source=="RETAIL":
                interest=money(balance*Decimal("0.025"));principal=max(Decimal("0"),money(payment-interest));balance=max(Decimal("0"),money(balance-principal))
            else:
                interest=linear_interest;principal=money(payment-interest)
            rows.append(add_invoice(db,contract,number,"INSTALLMENT",add_months(start_date,number),principal,interest,Decimal("0")))
        balloon=Decimal(output.get("balloon_payment","0"))
        if balloon>0: rows.append(add_invoice(db,contract,36,"BALLOON",add_months(start_date,36),balloon,Decimal("0"),Decimal("0")))
    else:
        raise HTTPException(status_code=422, detail="Fórmula sem gerador de cobrança homologado")
    db.flush(); return rows


def apply_payment(db: Session, user: User, invoice: Invoice, event_id: str, amount: Decimal, metadata: dict) -> tuple[PaymentEvent,bool]:
    existing=db.scalar(select(PaymentEvent).where(PaymentEvent.provider_event_id==event_id))
    if existing: return existing,False
    value=money(amount);outstanding=money(Decimal(str(invoice.total_amount))-Decimal(str(invoice.paid_amount)))
    new_paid=money(Decimal(str(invoice.paid_amount))+value)
    invoice.paid_amount=new_paid
    if value==outstanding:
        status="MATCHED";invoice.status="PAID";invoice.paid_at=datetime.now(UTC)
    elif value<outstanding:
        status="DIVERGENT";invoice.status="PARTIALLY_PAID"
    else:
        status="DIVERGENT";invoice.status="OVERPAID";invoice.paid_at=datetime.now(UTC)
    event=PaymentEvent(organization_id=user.organization_id,invoice_id=invoice.id,provider_event_id=event_id,amount=value,status=status,payload_json=json.dumps(metadata))
    db.add(event);db.flush()
    if status=="DIVERGENT": create_webhook_divergence(db,user,invoice,event,outstanding,value)
    return event,True


def create_webhook_divergence(db:Session,user:User,invoice:Invoice,event:PaymentEvent,expected:Decimal,received:Decimal):
    digest=hashlib.sha256(event.provider_event_id.encode()).hexdigest()
    batch=ReconciliationBatch(organization_id=user.organization_id,source="WEBHOOK",file_hash=digest,status="DIVERGENT",total_records=1,divergent_records=1,created_by_id=user.id)
    db.add(batch);db.flush();db.add(ReconciliationItem(organization_id=user.organization_id,batch_id=batch.id,invoice_id=invoice.id,external_reference=invoice.invoice_number,external_event_id=event.provider_event_id,expected_amount=expected,received_amount=received,payment_date=date.today(),status="DIVERGENT",reason="AMOUNT_MISMATCH"))


def import_reconciliation_csv(db:Session,user:User,data:bytes)->ReconciliationBatch:
    digest=hashlib.sha256(data).hexdigest()
    if db.scalar(select(ReconciliationBatch).where(ReconciliationBatch.file_hash==digest)): raise HTTPException(status_code=409,detail="Arquivo de conciliação já importado")
    try: records=list(csv.DictReader(io.StringIO(data.decode("utf-8-sig"))))
    except UnicodeDecodeError: raise HTTPException(status_code=422,detail="CSV deve estar em UTF-8")
    required={"invoice_number","amount","payment_date","external_id"}
    if not records or not required.issubset(records[0]): raise HTTPException(status_code=422,detail="CSV deve conter invoice_number, amount, payment_date e external_id")
    batch=ReconciliationBatch(organization_id=user.organization_id,source="CSV",file_hash=digest,total_records=len(records),created_by_id=user.id)
    db.add(batch);db.flush();matched=divergent=0
    for row in records:
        invoice=db.scalar(select(Invoice).where(Invoice.organization_id==user.organization_id,Invoice.invoice_number==row["invoice_number"]))
        received=money(Decimal(row["amount"]));expected=money(Decimal(str(invoice.total_amount))-Decimal(str(invoice.paid_amount))) if invoice else Decimal("0")
        if not invoice: status="DIVERGENT";reason="INVOICE_NOT_FOUND";divergent+=1
        elif received!=expected: status="DIVERGENT";reason="AMOUNT_MISMATCH";divergent+=1
        else:
            event,processed=apply_payment(db,user,invoice,row["external_id"],received,{"source":"CSV"});status="MATCHED";reason=None;matched+=1
        db.add(ReconciliationItem(organization_id=user.organization_id,batch_id=batch.id,invoice_id=invoice.id if invoice else None,external_reference=row["invoice_number"],external_event_id=row["external_id"],expected_amount=expected,received_amount=received,payment_date=date.fromisoformat(row["payment_date"]),status=status,reason=reason))
    batch.matched_records=matched;batch.divergent_records=divergent;batch.status="RECONCILED" if divergent==0 else "DIVERGENT";return batch


def refresh_delinquency(db:Session,user:User,as_of:date)->list[DelinquencyCase]:
    invoices=list(db.scalars(select(Invoice).where(Invoice.organization_id==user.organization_id,Invoice.status.in_(["OPEN","PARTIALLY_PAID","OVERDUE"]),Invoice.due_date<as_of)))
    result=[]
    for invoice in invoices:
        days=(as_of-invoice.due_date).days;outstanding=money(Decimal(str(invoice.total_amount))-Decimal(str(invoice.paid_amount)))
        case=db.scalar(select(DelinquencyCase).where(DelinquencyCase.invoice_id==invoice.id))
        if not case: case=DelinquencyCase(organization_id=user.organization_id,invoice_id=invoice.id,days_overdue=days);db.add(case)
        case.days_overdue=days;case.penalty_amount=money(outstanding*Decimal("0.02"));case.late_interest_amount=money(outstanding*Decimal("0.01")*Decimal(days)/Decimal("30"));invoice.status="OVERDUE"
        proposal=db.get(Proposal,invoice.proposal_id);case.caducity_eligible=bool(proposal and proposal.product=="FLASH_CREDIT" and days>60)
        threshold=60 if days>=60 else 30 if days>=30 else 15 if days>=15 else 5 if days>=5 else 1;action_type=f"OVERDUE_D{threshold}"
        if not db.scalar(select(CollectionAction).where(CollectionAction.invoice_id==invoice.id,CollectionAction.action_type==action_type)):
            db.add(CollectionAction(organization_id=user.organization_id,invoice_id=invoice.id,action_type=action_type,channel="IN_APP",scheduled_at=datetime.now(UTC),payload_json=json.dumps({"days_overdue":days})))
        result.append(case)
    db.flush();return result


def resolve_reconciliation(db:Session,user:User,item:ReconciliationItem,decision:str,note:str)->ReconciliationItem:
    if item.status not in {"DIVERGENT","PENDING"}: raise HTTPException(status_code=409,detail="Divergência já resolvida")
    if decision=="ACCEPT_PAYMENT":
        if not item.invoice_id: raise HTTPException(status_code=422,detail="Vincule uma fatura antes de aceitar")
        invoice=db.get(Invoice,item.invoice_id);outstanding=money(Decimal(str(invoice.total_amount))-Decimal(str(invoice.paid_amount)));invoice.paid_amount=money(Decimal(str(invoice.paid_amount))+Decimal(str(item.received_amount)))
        invoice.status="PAID" if Decimal(str(invoice.paid_amount))==Decimal(str(invoice.total_amount)) else "PARTIALLY_PAID"
        if invoice.status=="PAID": invoice.paid_at=datetime.now(UTC)
    elif decision!="IGNORE": raise HTTPException(status_code=422,detail="Decisão deve ser ACCEPT_PAYMENT ou IGNORE")
    item.status="RESOLVED";item.resolved_by_id=user.id;item.resolved_at=datetime.now(UTC);item.resolution_note=note;return item
