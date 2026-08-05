import itertools
import json
from decimal import Decimal, ROUND_HALF_UP

from fastapi import HTTPException
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.models import (
    AuctionSettlement, DelinquencyCase, FundingOpportunity, Invoice, Lead,
    Proposal, Quota, UnderwritingAssessment, UnderwritingDecision,
    UnderwritingPolicy, User,
)


def money(value: Decimal) -> Decimal:
    return value.quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)


def create_policy(db: Session, user: User, product: str, **data) -> UnderwritingPolicy:
    current=db.scalar(select(func.max(UnderwritingPolicy.version)).where(UnderwritingPolicy.organization_id==user.organization_id,UnderwritingPolicy.product==product)) or 0
    for item in db.scalars(select(UnderwritingPolicy).where(UnderwritingPolicy.organization_id==user.organization_id,UnderwritingPolicy.product==product,UnderwritingPolicy.active.is_(True))): item.active=False
    policy=UnderwritingPolicy(organization_id=user.organization_id,product=product,version=current+1,rules_json=json.dumps(data.pop("rules",{}),ensure_ascii=False),**data)
    db.add(policy);return policy


def assess(db:Session,user:User,proposal:Proposal,policy:UnderwritingPolicy,inputs:dict)->UnderwritingAssessment:
    income=Decimal(str(inputs["monthly_income"]));commitment=Decimal(str(inputs["monthly_commitment"]));asset=Decimal(str(inputs["asset_value"]));requested=Decimal(str(proposal.requested_amount))
    external=int(inputs["external_score"]);completeness=Decimal(str(inputs["document_completeness_percent"]));kyc=inputs["kyc_status"]
    commitment_pct=(commitment/income*100) if income else Decimal("100")
    ltv=(requested/asset*100) if asset else Decimal("100")
    score=external
    factors=[]
    if kyc!="APPROVED": score-=180;factors.append({"factor":"KYC","impact":-180,"detail":"KYC não aprovado"})
    else: factors.append({"factor":"KYC","impact":20,"detail":"KYC aprovado"});score+=20
    if completeness<Decimal("100"): penalty=int((Decimal("100")-completeness)*Decimal("1.5"));score-=penalty;factors.append({"factor":"DOCUMENTS","impact":-penalty,"detail":f"Completude {completeness}%"})
    if commitment_pct>Decimal(str(policy.maximum_commitment_percent)):
        penalty=int((commitment_pct-Decimal(str(policy.maximum_commitment_percent)))*4);score-=penalty;factors.append({"factor":"COMMITMENT","impact":-penalty,"detail":f"Comprometimento {commitment_pct:.2f}%"})
    if ltv>Decimal(str(policy.maximum_ltv_percent)):
        penalty=int((ltv-Decimal(str(policy.maximum_ltv_percent)))*5);score-=penalty;factors.append({"factor":"LTV","impact":-penalty,"detail":f"LTV {ltv:.2f}%"})
    score=max(0,min(1000,score));band="LOW" if score>=800 else "MEDIUM" if score>=650 else "HIGH"
    recommendation="REJECT" if score<int(policy.minimum_score) or kyc!="APPROVED" else "MANUAL_REVIEW" if score<int(policy.manual_review_score) else "APPROVE"
    version=(db.scalar(select(func.max(UnderwritingAssessment.version)).where(UnderwritingAssessment.proposal_id==proposal.id)) or 0)+1
    output={"factors":factors,"ltv_percent":str(money(ltv)),"commitment_percent":str(money(commitment_pct)),"policy_version":policy.version,"summary":f"Score {score}, risco {band}, recomendação {recommendation}."}
    item=UnderwritingAssessment(organization_id=user.organization_id,proposal_id=proposal.id,policy_id=policy.id,version=version,score=score,risk_band=band,recommendation=recommendation,inputs_json=json.dumps(inputs),explanation_json=json.dumps(output,ensure_ascii=False),assessed_by_id=user.id)
    db.add(item);return item


def decide(db:Session,user:User,assessment:UnderwritingAssessment,decision:str,reason:str)->UnderwritingDecision:
    if assessment.status!="PENDING_DECISION": raise HTTPException(status_code=409,detail="Avaliação já decidida")
    item=UnderwritingDecision(organization_id=user.organization_id,assessment_id=assessment.id,decision=decision,reason=reason,decided_by_id=user.id)
    assessment.status="DECIDED";proposal=db.get(Proposal,assessment.proposal_id);proposal.status=f"UNDERWRITING_{decision}"
    db.add(item);return item


def rank_quota_combinations(db:Session,user:User,target:Decimal,category:str,limit:int=10)->list[dict]:
    quotas=list(db.scalars(select(Quota).where(Quota.organization_id==user.organization_id,Quota.status=="AVAILABLE",Quota.category==category)))
    candidates=[]
    for size in range(1,min(3,len(quotas))+1):
        for combo in itertools.combinations(quotas,size):
            if len({x.administrator_id for x in combo})>1: continue
            total=sum((Decimal(str(x.credit_value)) for x in combo),Decimal("0"));deviation=abs((total-target)/target*100)
            score=max(0,1000-int(deviation*20)-size*5)
            candidates.append({"quota_ids":[x.id for x in combo],"total_credit":str(money(total)),"deviation_percent":str(money(deviation)),"score":score,"administrator_id":combo[0].administrator_id,"explanation":f"Desvio de {money(deviation)}% com {size} cota(s)."})
    return sorted(candidates,key=lambda x:(-x["score"],x["deviation_percent"]))[:limit]


def bi_summary(db:Session,user:User)->dict:
    org=user.organization_id
    count=lambda model,*filters: db.scalar(select(func.count()).select_from(model).where(model.organization_id==org,*filters)) or 0
    total=lambda model,column,*filters: money(Decimal(str(db.scalar(select(func.coalesce(func.sum(column),0)).where(model.organization_id==org,*filters)) or 0)))
    invoice_total=total(Invoice,Invoice.total_amount);paid=total(Invoice,Invoice.paid_amount);overdue=total(DelinquencyCase,DelinquencyCase.penalty_amount)+total(DelinquencyCase,DelinquencyCase.late_interest_amount)
    return {"funnel":{"leads":count(Lead),"proposals":count(Proposal),"approved":count(Proposal,Proposal.status=="UNDERWRITING_APPROVE")},"portfolio":{"invoiced":str(invoice_total),"paid":str(paid),"open":str(money(invoice_total-paid)),"delinquency_charges":str(money(overdue))},"risk":{"assessments":count(UnderwritingAssessment),"high_risk":count(UnderwritingAssessment,UnderwritingAssessment.risk_band=="HIGH"),"pending_decisions":count(UnderwritingAssessment,UnderwritingAssessment.status=="PENDING_DECISION")},"funding":{"target":str(total(FundingOpportunity,FundingOpportunity.target_amount)),"funded":str(total(FundingOpportunity,FundingOpportunity.funded_amount))},"recovery":{"settled":str(total(AuctionSettlement,AuctionSettlement.gross_amount))}}
