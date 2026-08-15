import csv
import hashlib
import io
import json
import os
from datetime import UTC, datetime
from decimal import Decimal

from fastapi import HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.integration_service import protect, reveal
from app.models import (
    EscrowEvent, HomologationEvidence, IntegrationMTLSConfig, PaymentEvent,
    ProviderIntegration, ProviderOnboardingProfile, ProviderReconciliationItem,
    ProviderReconciliationRun, SecretReference, User,
)


def create_secret(db:Session,user:User,name:str,backend:str,value:str|None,external_reference:str|None)->SecretReference:
    backend=backend.upper()
    if backend not in {"LOCAL_ENCRYPTED","ENV_REFERENCE"}:raise HTTPException(status_code=422,detail="Backend de segredo inválido")
    if backend=="LOCAL_ENCRYPTED" and not value:raise HTTPException(status_code=422,detail="Valor obrigatório")
    if backend=="ENV_REFERENCE" and not external_reference:raise HTTPException(status_code=422,detail="Referência de ambiente obrigatória")
    item=db.scalar(select(SecretReference).where(SecretReference.organization_id==user.organization_id,SecretReference.name==name))
    if item:
        item.backend=backend;item.encrypted_value=protect(value) if value else None;item.external_reference=external_reference;item.version+=1;item.last_rotated_at=datetime.now(UTC);item.active=True;return item
    item=SecretReference(organization_id=user.organization_id,name=name,backend=backend,encrypted_value=protect(value) if value else None,external_reference=external_reference);db.add(item);return item


def resolve_secret(item:SecretReference)->str:
    if not item.active:raise RuntimeError("Segredo inativo")
    if item.backend=="LOCAL_ENCRYPTED":return reveal(item.encrypted_value or "")
    value=os.getenv(item.external_reference or "")
    if not value:raise RuntimeError("Segredo externo indisponível")
    return value


def configure_mtls(db:Session,user:User,integration:ProviderIntegration,certificate:SecretReference,private_key:SecretReference,ca:SecretReference|None,verify_peer:bool,enabled:bool)->IntegrationMTLSConfig:
    refs=[certificate,private_key]+([ca] if ca else [])
    if any(x.organization_id!=user.organization_id for x in refs):raise HTTPException(status_code=404,detail="Referência de segredo inválida")
    item=db.scalar(select(IntegrationMTLSConfig).where(IntegrationMTLSConfig.integration_id==integration.id))
    values={"certificate_secret_id":certificate.id,"private_key_secret_id":private_key.id,"ca_secret_id":ca.id if ca else None,"verify_peer":verify_peer,"enabled":enabled}
    if item:
        for key,value in values.items():setattr(item,key,value)
        return item
    item=IntegrationMTLSConfig(organization_id=user.organization_id,integration_id=integration.id,**values);db.add(item);return item


def configure_profile(db:Session,user:User,integration:ProviderIntegration,api_version:str,authentication_type:str,health_path:str,reconciliation_mode:str,checklist:dict)->ProviderOnboardingProfile:
    if authentication_type not in {"BEARER","API_KEY","MTLS","OAUTH2"}:raise HTTPException(status_code=422,detail="Autenticação inválida")
    if reconciliation_mode not in {"CSV","WEBHOOK","CSV_AND_WEBHOOK"}:raise HTTPException(status_code=422,detail="Modo de conciliação inválido")
    if not health_path.startswith("/"):raise HTTPException(status_code=422,detail="Health path inválido")
    item=db.scalar(select(ProviderOnboardingProfile).where(ProviderOnboardingProfile.integration_id==integration.id));values={"api_version":api_version,"authentication_type":authentication_type,"health_path":health_path,"reconciliation_mode":reconciliation_mode,"checklist_json":json.dumps(checklist,ensure_ascii=False),"status":"DRAFT"}
    if item:
        for key,value in values.items():setattr(item,key,value)
        return item
    item=ProviderOnboardingProfile(organization_id=user.organization_id,integration_id=integration.id,**values);db.add(item);return item


def import_reconciliation_csv(db:Session,user:User,integration:ProviderIntegration,filename:str,content:bytes)->tuple[ProviderReconciliationRun,bool]:
    digest=hashlib.sha256(content).hexdigest();existing=db.scalar(select(ProviderReconciliationRun).where(ProviderReconciliationRun.content_hash==digest))
    if existing:
        if existing.organization_id!=user.organization_id:raise HTTPException(status_code=409,detail="Arquivo já utilizado")
        return existing,False
    try:rows=list(csv.DictReader(io.StringIO(content.decode("utf-8-sig"))))
    except UnicodeDecodeError:raise HTTPException(status_code=422,detail="CSV deve estar em UTF-8")
    required={"external_id","event_type","amount","status"}
    if not rows or not required.issubset(rows[0]):raise HTTPException(status_code=422,detail=f"CSV exige colunas: {', '.join(sorted(required))}")
    run=ProviderReconciliationRun(organization_id=user.organization_id,integration_id=integration.id,source_type="CSV",source_reference=filename,content_hash=digest,total_items=len(rows));db.add(run);db.flush();matched=0
    for row in rows:
        try:amount=Decimal(row["amount"])
        except Exception:raise HTTPException(status_code=422,detail=f"Valor inválido para {row.get('external_id')}")
        escrow=db.scalar(select(EscrowEvent).where(EscrowEvent.organization_id==user.organization_id,EscrowEvent.provider_event_id==row["external_id"]));payment=db.scalar(select(PaymentEvent).where(PaymentEvent.organization_id==user.organization_id,PaymentEvent.provider_event_id==row["external_id"]));internal=escrow or payment
        same_amount=bool(internal and Decimal(str(internal.amount))==amount);match_status="MATCHED" if same_amount else "DIVERGENT";reason=None if same_amount else ("NOT_FOUND" if not internal else "AMOUNT_MISMATCH")
        if same_amount:matched+=1
        db.add(ProviderReconciliationItem(organization_id=user.organization_id,run_id=run.id,external_id=row["external_id"],event_type=row["event_type"],amount=amount,provider_status=row["status"],match_status=match_status,reason=reason))
    run.matched_items=matched;run.divergent_items=len(rows)-matched;run.status="COMPLETED" if matched==len(rows) else "COMPLETED_WITH_DIVERGENCES";run.processed_at=datetime.now(UTC);return run,True


def generate_evidence(db:Session,user:User,integration:ProviderIntegration)->list[HomologationEvidence]:
    profile=db.scalar(select(ProviderOnboardingProfile).where(ProviderOnboardingProfile.integration_id==integration.id));mtls=db.scalar(select(IntegrationMTLSConfig).where(IntegrationMTLSConfig.integration_id==integration.id));run=db.scalar(select(ProviderReconciliationRun).where(ProviderReconciliationRun.integration_id==integration.id).order_by(ProviderReconciliationRun.created_at.desc()))
    controls={
        "ALLOWLIST":{"passed":bool(json.loads(integration.allowed_hosts_json)),"detail":"Hosts mínimos configurados"},
        "CREDENTIAL":{"passed":bool(integration.credential_ciphertext),"detail":f"Versão {integration.credential_version}"},
        "HEALTH":{"passed":integration.health_status=="UP","detail":integration.health_status},
        "CIRCUIT":{"passed":integration.circuit_status=="CLOSED","detail":integration.circuit_status},
        "MTLS":{"passed":bool(profile and profile.authentication_type!="MTLS") or bool(mtls and mtls.enabled),"detail":"Configurado quando exigido"},
        "RECONCILIATION":{"passed":bool(run and run.status=="COMPLETED"),"detail":run.status if run else "NOT_EXECUTED"},
    }
    now=datetime.now(UTC);items=[]
    for key,data in controls.items():
        body=json.dumps({"provider":integration.provider,"control":key,**data,"executed_at":now.isoformat()},sort_keys=True,ensure_ascii=False);item=HomologationEvidence(organization_id=user.organization_id,integration_id=integration.id,control_key=key,result="PASS" if data["passed"] else "FAIL",evidence_json=body,evidence_hash=hashlib.sha256(body.encode()).hexdigest(),executed_by_id=user.id,executed_at=now);db.add(item);items.append(item)
    if profile:profile.status="READY_FOR_HOMOLOGATION" if all(x.result=="PASS" for x in items) else "BLOCKED"
    return items
