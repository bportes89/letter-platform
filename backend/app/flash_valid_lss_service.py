import hashlib
import hmac
import json
from datetime import UTC, datetime, timedelta
from decimal import Decimal, ROUND_HALF_UP
from uuid import uuid4

from fastapi import HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.config import settings
from app.models import (
    FlashCreditParty, FlashCreditPolicy, PreAnalysisPauta, Proposal, SaaSAcceptance,
    SaaSPlan, SaaSSubscription, SaaSTermsTemplate, User, ValidStamp,
)
from app.valid_stamp_requirements import (
    FLASH_CAPITAL_STAMP_PURPOSES,
    SDC_VEHICLE_STAMP_PURPOSES,
    validate_flash_capital_stamp_payload,
    validate_sdc_vehicle_stamp_payload,
)


def canonical(payload: dict) -> str:
    return json.dumps(payload,ensure_ascii=False,sort_keys=True,separators=(",", ":"))


def digest(payload: dict | str) -> str:
    raw=payload if isinstance(payload,str) else canonical(payload)
    return hashlib.sha256(raw.encode()).hexdigest()


def clean_doc(value: str) -> str:
    return ''.join(x for x in value if x.isdigit())


def mask_doc(value: str) -> str:
    value=clean_doc(value);return f"***{value[-4:]}" if len(value)>=4 else "****"


def create_flash_policy(db:Session,user:User,**values)->FlashCreditPolicy:
    item=FlashCreditPolicy(organization_id=user.organization_id,**values);db.add(item);db.flush();return item


def approve_flash_policy(db:Session,user:User,item:FlashCreditPolicy)->FlashCreditPolicy:
    for other in db.scalars(select(FlashCreditPolicy).where(FlashCreditPolicy.organization_id==user.organization_id,FlashCreditPolicy.status=="ACTIVE")):other.status="RETIRED"
    item.status="ACTIVE";item.approved_by_id=user.id;item.approved_at=datetime.now(UTC);return item


def configure_flash_parties(db:Session,user:User,proposal:Proposal,*,borrower_cnpj:str,property_owner_type:str,
        property_owner_document:str,legal_representative_document:str|None,liveness_reference:str|None,
        qsa_representative_match:bool|None,consent_confirmation:bool)->dict:
    if proposal.product != "FLASH_CREDIT":
        raise HTTPException(422, "Proposta deve ser Flash Capital")
    borrower = clean_doc(borrower_cnpj)
    if len(borrower) != 14:
        raise HTTPException(422, "Tomador do Flash Capital deve possuir CNPJ válido; CPF só pode participar como garantidor/interveniente")
    if property_owner_type not in {"PF","PJ_BORROWER","PJ_THIRD_PARTY"}:raise HTTPException(422,"Tipo de proprietário inválido")
    owner=clean_doc(property_owner_document)
    if property_owner_type=="PF" and len(owner)!=11:raise HTTPException(422,"Proprietário PF exige CPF")
    if property_owner_type.startswith("PJ") and len(owner)!=14:raise HTTPException(422,"Proprietário PJ exige CNPJ")
    if property_owner_type!="PJ_BORROWER" and (not liveness_reference or not consent_confirmation):raise HTTPException(422,"Terceiro proprietário exige liveness e consentimento expresso")
    if property_owner_type=="PJ_THIRD_PARTY" and qsa_representative_match is not True:raise HTTPException(409,"Administrador signatário deve coincidir com QSA/poderes de alienação")
    for role in ("BORROWER","PROPERTY_OWNER"):
        current=db.scalar(select(FlashCreditParty).where(FlashCreditParty.proposal_id==proposal.id,FlashCreditParty.party_role==role))
        if current:db.delete(current);db.flush()
    db.add(FlashCreditParty(organization_id=user.organization_id,proposal_id=proposal.id,party_role="BORROWER",person_type="PJ",document_masked=mask_doc(borrower),qsa_match_status="VALIDATED",consent_status="ACCEPTED",status="VALIDATED"))
    consent={"proposal_id":proposal.id,"owner_type":property_owner_type,"owner":mask_doc(owner),"representative":mask_doc(legal_representative_document or owner),"liveness_reference":liveness_reference,"confirmed":consent_confirmation}
    db.add(FlashCreditParty(organization_id=user.organization_id,proposal_id=proposal.id,party_role="PROPERTY_OWNER",person_type="PF" if property_owner_type=="PF" else "PJ",document_masked=mask_doc(owner),legal_representative_document_masked=mask_doc(legal_representative_document or owner),qsa_match_status="VALIDATED" if property_owner_type!="PF" else "NOT_APPLICABLE",liveness_reference=liveness_reference,consent_status="ACCEPTED",consent_hash=digest(consent),status="VALIDATED"))
    route="DIRECT_CLEAN" if property_owner_type=="PJ_BORROWER" else ("THIRD_PARTY_PF_GUARANTOR" if property_owner_type=="PF" else "THIRD_PARTY_PJ_QSA")
    terms=json.loads(proposal.terms_json or "{}");terms["flash_credit_route"]={"borrower_pj":True,"property_owner_type":property_owner_type,"route":route,"dynamic_clause_blocks":["IQ" if terms.get("has_lien_debt") else None,"THIRD_PARTY_CONSENT" if property_owner_type!="PJ_BORROWER" else None,"UNREGISTERED_CONSTRUCTION" if terms.get("unregistered_construction") else None]}
    terms["flash_credit_route"]["dynamic_clause_blocks"]=[x for x in terms["flash_credit_route"]["dynamic_clause_blocks"] if x];proposal.terms_json=json.dumps(terms,ensure_ascii=False)
    return terms["flash_credit_route"]


def issue_stamp(db:Session,user:User,*,entity_type:str,entity_id:str,purpose:str,payload:dict)->ValidStamp:
    if purpose in FLASH_CAPITAL_STAMP_PURPOSES:
        if not str(payload.get("tapaf_evidence_reference", "")).strip() and entity_type == "proposal":
            pauta = db.scalar(
                select(PreAnalysisPauta).where(
                    PreAnalysisPauta.proposal_id == entity_id,
                    PreAnalysisPauta.organization_id == user.organization_id,
                    PreAnalysisPauta.status.in_(("TAPAF_PAID", "APPROVED_VALID_STAMP")),
                )
            )
            if not pauta or not pauta.tapaf_payment_reference:
                raise HTTPException(
                    status_code=422,
                    detail="Valid-Stamp Flash Capital exige TAPAF liquidada (R$ 1.500) na esteira de pré-análise",
                )
            payload = {**payload, "tapaf_evidence_reference": pauta.tapaf_payment_reference}
        if not str(payload.get("tapaf_evidence_reference", "")).strip():
            raise HTTPException(
                status_code=422,
                detail="Valid-Stamp Flash Capital exige pagamento TAPAF (tapaf_evidence_reference)",
            )
        validate_flash_capital_stamp_payload(payload)
    elif purpose in SDC_VEHICLE_STAMP_PURPOSES:
        validate_sdc_vehicle_stamp_payload(payload)
    existing=db.scalar(select(ValidStamp).where(ValidStamp.organization_id==user.organization_id,ValidStamp.entity_type==entity_type,ValidStamp.entity_id==entity_id,ValidStamp.purpose==purpose))
    if existing:return existing
    previous=db.scalar(select(ValidStamp).where(ValidStamp.organization_id==user.organization_id).order_by(ValidStamp.issued_at.desc()))
    payload_hash=digest(payload);previous_hash=previous.chain_hash if previous else None
    body={"organization_id":user.organization_id,"entity_type":entity_type,"entity_id":entity_id,"purpose":purpose,"payload_hash":payload_hash,"previous_hash":previous_hash}
    chain_hash=digest(body);signature=hmac.new(settings.secret_key.encode(),chain_hash.encode(),hashlib.sha256).hexdigest()
    item=ValidStamp(organization_id=user.organization_id,stamp_code=f"LVS-{uuid4().hex[:16].upper()}",entity_type=entity_type,entity_id=entity_id,purpose=purpose,payload_hash=payload_hash,previous_hash=previous_hash,chain_hash=chain_hash,signature=signature,issued_by_id=user.id)
    db.add(item);db.flush();return item


def verify_stamp(item:ValidStamp)->dict:
    expected=hmac.new(settings.secret_key.encode(),item.chain_hash.encode(),hashlib.sha256).hexdigest()
    return {"stamp_code":item.stamp_code,"status":item.status,"integrity_valid":hmac.compare_digest(expected,item.signature) and item.status=="VALID","algorithm":item.algorithm,"payload_hash":item.payload_hash,"chain_hash":item.chain_hash,"legal_effect":"EVIDENCE_RECORD_NOT_DIGITAL_CERTIFICATE"}


def create_terms(db:Session,user:User,*,code:str,version:int,title:str,body:str)->SaaSTermsTemplate:
    item=SaaSTermsTemplate(organization_id=user.organization_id,code=code,version=version,title=title,body=body,body_hash=digest(body));db.add(item);db.flush();return item


def approve_terms(db:Session,user:User,item:SaaSTermsTemplate)->SaaSTermsTemplate:
    for other in db.scalars(select(SaaSTermsTemplate).where(SaaSTermsTemplate.organization_id==user.organization_id,SaaSTermsTemplate.code==item.code,SaaSTermsTemplate.active.is_(True))):other.active=False
    item.active=True;item.legal_review_status="APPROVED";item.approved_by_id=user.id;item.approved_at=datetime.now(UTC);return item


def create_plan(db:Session,user:User,*,code:str,name:str,monthly_price:Decimal,central_share_percent:Decimal,network_pool_percent:Decimal)->SaaSPlan:
    if (central_share_percent+network_pool_percent).quantize(Decimal(".01"))!=Decimal("100.00"):raise HTTPException(422,"Rateio deve totalizar 100%")
    item=SaaSPlan(organization_id=user.organization_id,code=code,name=name,monthly_price=monthly_price,central_share_percent=central_share_percent,network_pool_percent=network_pool_percent);db.add(item);db.flush();return item


def subscribe(db:Session,user:User,plan:SaaSPlan,terms:SaaSTermsTemplate,*,company_name:str,company_cnpj:str,
        representative_name:str,representative_document:str,scroll_completed:bool,terms_accepted:bool,
        recurring_authorized:bool,verification_reference:str,payment_method_reference:str|None,ip_address:str|None,user_agent:str|None,
        subscriber_email:str|None=None,subscriber_phone:str|None=None,billing_type:str|None=None)->SaaSSubscription:
    if len(clean_doc(company_cnpj))!=14:raise HTTPException(422,"LSS é contratado por Pessoa Jurídica e exige CNPJ")
    if not all([scroll_completed,terms_accepted,recurring_authorized,verification_reference]):raise HTTPException(422,"Rolagem, aceite, autorização recorrente e verificação são obrigatórios")
    if not terms.active or terms.legal_review_status!="APPROVED":raise HTTPException(409,"Termos LSS não possuem versão jurídica ativa")
    now=datetime.now(UTC);evidence={"plan":plan.code,"price":str(plan.monthly_price),"terms_id":terms.id,"terms_version":terms.version,"terms_hash":terms.body_hash,"company":mask_doc(company_cnpj),"representative":mask_doc(representative_document),"scroll_completed":True,"terms_accepted":True,"recurring_authorized":True,"verification_reference":verification_reference,"ip":ip_address,"user_agent":user_agent,"accepted_at":now.isoformat()};evidence_hash=digest(evidence)
    from app.lss_billing_service import lss_billing_live, provision_asaas_subscription

    initial_status = "PENDING_PAYMENT" if lss_billing_live() else "ACTIVE_SANDBOX"
    item=SaaSSubscription(organization_id=user.organization_id,plan_id=plan.id,terms_template_id=terms.id,subscriber_company_name=company_name,subscriber_document_masked=mask_doc(company_cnpj),legal_representative_name=representative_name,legal_representative_document_masked=mask_doc(representative_document),status=initial_status,current_period_start=now,current_period_end=now+timedelta(days=30),payment_method_reference=payment_method_reference,recurring_authorized=True,acceptance_hash=evidence_hash,subscriber_email=(subscriber_email or user.email).strip())
    db.add(item);db.flush();db.add(SaaSAcceptance(organization_id=user.organization_id,subscription_id=item.id,user_id=user.id,terms_template_id=terms.id,ip_address=ip_address,user_agent=user_agent,verification_reference=verification_reference,evidence_json=json.dumps(evidence,ensure_ascii=False,sort_keys=True),evidence_hash=evidence_hash))
    issue_stamp(db,user,entity_type="saas_subscription",entity_id=item.id,purpose="LSS_CLICKWRAP_ACCEPTANCE",payload=evidence)
    if lss_billing_live():
        provision_asaas_subscription(db,item,plan,company_cnpj=company_cnpj,subscriber_email=item.subscriber_email or user.email,subscriber_phone=subscriber_phone,billing_type=billing_type)
    return item


def cancel_subscription(item:SaaSSubscription)->SaaSSubscription:
    cancellable={"ACTIVE_SANDBOX","PAST_DUE","ACTIVE","PENDING_PAYMENT","SUSPENDED","SUSPENDED_PAST_DUE_SANDBOX"}
    if item.status not in cancellable:raise HTTPException(409,"Assinatura não está cancelável")
    from app.lss_billing_service import cancel_asaas_subscription

    item.cancel_at_period_end=True;item.cancelled_at=datetime.now(UTC);item.status="CANCELLATION_SCHEDULED"
    cancel_asaas_subscription(item)
    return item


def evaluate_subscription(item:SaaSSubscription,as_of:datetime|None=None)->SaaSSubscription:
    from app.lss_billing_service import evaluate_subscription_billing

    return evaluate_subscription_billing(item, as_of)


def subscription_allocation(plan:SaaSPlan)->dict:
    price=Decimal(str(plan.monthly_price));central=(price*Decimal(str(plan.central_share_percent))/Decimal(100)).quantize(Decimal(".01"),rounding=ROUND_HALF_UP);network=price-central
    from app.lss_billing_service import lss_billing_live

    execution = "ASAAS_RECURRING" if lss_billing_live() else "PREVIEW_ONLY"
    return {"monthly_price":str(price.quantize(Decimal('.01'))),"central_share":str(central),"network_pool":str(network),"execution":execution}
