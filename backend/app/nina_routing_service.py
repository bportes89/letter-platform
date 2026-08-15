import hashlib
import json
from datetime import UTC,datetime
from decimal import Decimal

from fastapi import HTTPException
from sqlalchemy import func,select
from sqlalchemy.orm import Session

from app.flash_valid_lss_service import issue_stamp
from app.models import NinaRoutingAssessment,NinaRoutingPolicy,Proposal,User

from app.vehicle_registry_service import query_vehicle_registry

RISK_FLAGS={"PF_NEGATIVE","PJ_NEGATIVE","PARTNER_NEGATIVE","ADMINISTRATOR_VETO","REGISTRY_RISK"}

def canonical_hash(payload:dict)->str:
    return hashlib.sha256(json.dumps(payload,ensure_ascii=False,sort_keys=True,separators=(",",":")).encode()).hexdigest()

def create_policy(db:Session,user:User,**values)->NinaRoutingPolicy:
    item=NinaRoutingPolicy(organization_id=user.organization_id,**values);db.add(item);db.flush();return item

def approve_policy(db:Session,user:User,item:NinaRoutingPolicy)->NinaRoutingPolicy:
    for other in db.scalars(select(NinaRoutingPolicy).where(NinaRoutingPolicy.organization_id==user.organization_id,NinaRoutingPolicy.status=="ACTIVE")):other.status="RETIRED"
    item.status="ACTIVE";item.approved_by_id=user.id;item.approved_at=datetime.now(UTC);return item

def assess(db:Session,user:User,proposal:Proposal,policy:NinaRoutingPolicy,*,asset_type:str,municipality_code:str,population:int,income_per_capita:Decimal,encumbrances:list[str],risk_flags:list[str],tapaf_evidence_reference:str|None,vehicle_plate:str|None=None,vehicle_renavam:str|None=None,vehicle_uf:str|None=None,vehicle_class:str|None=None)->NinaRoutingAssessment:
    asset=asset_type.upper();enc={x.upper() for x in encumbrances if x};risks={x.upper() for x in risk_flags if x}
    unknown=risks-RISK_FLAGS
    if unknown:raise HTTPException(422,f"Flags de risco desconhecidas: {sorted(unknown)}")
    rejected=set(json.loads(policy.rejected_encumbrances_json));blockers=[]
    judicial=sorted(enc&rejected)
    if judicial:blockers.append("JUDICIAL_ENCUMBRANCE")
    if risks and asset!="REAL_ESTATE" and proposal.product=="FLASH_CREDIT":blockers.append("RISK_RESCUE_REQUIRES_REAL_ESTATE")
    if proposal.product=="FLASH_CREDIT" and asset!="REAL_ESTATE":blockers.append("FLASH_CREDIT_REAL_ESTATE_ONLY")
    vehicle_registry_snapshot=None
    if asset=="VEHICLE" and tapaf_evidence_reference:
        if not all([vehicle_plate, vehicle_uf, vehicle_class]):
            blockers.append("VEHICLE_REGISTRY_DATA_REQUIRED")
        else:
            registry=query_vehicle_registry(plate=vehicle_plate,uf=vehicle_uf,vehicle_class=vehicle_class,renavam=vehicle_renavam)
            vehicle_registry_snapshot=registry
            if not registry["cleared"]:
                blockers.append("VEHICLE_REGISTRY_RESTRICTION")
    elif asset=="VEHICLE" and proposal.product=="SDC" and not tapaf_evidence_reference:
        pass  # aguarda TAPAF antes da consulta DETRAN
    product_route="BLOCKED" if blockers else ("FLASH_CREDIT" if (risks or proposal.product=="FLASH_CREDIT") else ("SDC" if proposal.product=="SDC" else "CONSORTIUM_MARKETPLACE"))
    capital_route=None
    if product_route=="FLASH_CREDIT":capital_route="FUNDS" if population>=policy.population_threshold and income_per_capita>=Decimal(str(policy.income_per_capita_threshold)) else "POOL"
    status="BLOCKED" if blockers else ("AWAITING_TAPAF_EVIDENCE" if not tapaf_evidence_reference else "PENDING_COMMITTEE_REVIEW")
    version=(db.scalar(select(func.max(NinaRoutingAssessment.version)).where(NinaRoutingAssessment.proposal_id==proposal.id)) or 0)+1
    evidence={"proposal_id":proposal.id,"policy_id":policy.id,"version":version,"asset_type":asset,"municipality_code":municipality_code,"population":population,"income_per_capita":str(income_per_capita),"encumbrances":sorted(enc),"risk_flags":sorted(risks),"tapaf_evidence_reference":tapaf_evidence_reference,"product_route":product_route,"capital_route":capital_route,"status":status,"blockers":blockers,"physical_appraisal_required":True,"vehicle_registry_snapshot":vehicle_registry_snapshot}
    item=NinaRoutingAssessment(organization_id=user.organization_id,proposal_id=proposal.id,policy_id=policy.id,version=version,asset_type=asset,municipality_code=municipality_code,population=population,income_per_capita=income_per_capita,encumbrances_json=json.dumps(sorted(enc)),risk_flags_json=json.dumps(sorted(risks)),tapaf_evidence_reference=tapaf_evidence_reference,product_route=product_route,capital_route=capital_route,status=status,blockers_json=json.dumps(blockers),evidence_hash=canonical_hash(evidence))
    db.add(item);db.flush();return item

def approve_assessment(db:Session,user:User,item:NinaRoutingAssessment)->tuple[NinaRoutingAssessment,object]:
    if item.status!="PENDING_COMMITTEE_REVIEW":raise HTTPException(409,"Avaliação não está apta à aprovação do comitê")
    item.status="COMMITTEE_APPROVED_EVIDENCE_STAMPED";item.approved_by_id=user.id;item.approved_at=datetime.now(UTC)
    stamp=issue_stamp(db,user,entity_type="nina_routing_assessment",entity_id=item.id,purpose="COMMITTEE_ROUTING_APPROVAL",payload={"assessment_id":item.id,"evidence_hash":item.evidence_hash,"product_route":item.product_route,"capital_route":item.capital_route,"physical_appraisal_required":True,"payout_authorized":False})
    return item,stamp

def assessment_view(item:NinaRoutingAssessment)->dict:
    return {"id":item.id,"proposal_id":item.proposal_id,"policy_id":item.policy_id,"version":item.version,"asset_type":item.asset_type,"municipality_code":item.municipality_code,"population":item.population,"income_per_capita":item.income_per_capita,"encumbrances":json.loads(item.encumbrances_json),"risk_flags":json.loads(item.risk_flags_json),"tapaf_evidence_reference":item.tapaf_evidence_reference,"physical_appraisal_required":item.physical_appraisal_required,"product_route":item.product_route,"capital_route":item.capital_route,"status":item.status,"blockers":json.loads(item.blockers_json),"evidence_hash":item.evidence_hash,"approved_at":item.approved_at,"created_at":item.created_at}

def source_policy()->dict:
    return {"allowed":["IBGE_AGGREGATED_API","BACEN_AGGREGATED_OPEN_DATA","AUTHORIZED_ONR_PROVIDER","AUTHORIZED_CREDIT_BUREAU","CUSTOMER_SUPPLIED_DOCUMENTS"],"conditional":["PUBLIC_WEB_LISTING_WITH_TERMS_AND_ROBOTS_REVIEW","COURT_DATA_WITH_DOCUMENTED_LEGAL_BASIS_AND_ACCESS_AUTHORIZATION"],"blocked":["MASS_PJE_SCRAPING","RESTRICTED_PERSONAL_DATA_ENRICHMENT","CONTACT_EXTRACTION_WITHOUT_LAWFUL_BASIS"],"requires_dpia":True,"execution":"POLICY_ONLY_NO_SCRAPING"}
