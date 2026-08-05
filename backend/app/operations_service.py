import json
from datetime import UTC, datetime, timedelta

from fastapi import HTTPException
from sqlalchemy import func, select, text
from sqlalchemy.orm import Session

from app.models import OperationalJob, ProviderIncident, ProviderIntegration, User, WebhookDelivery
from app.core.config import settings


ALLOWED_JOBS={"RECONCILIATION_REFRESH","COLLECTION_REFRESH","COMMUNICATION_DELIVERY","EXECUTIVE_REPORT","PROVIDER_HEALTH_MONITOR","DEAD_LETTER_REPROCESS"}


def enqueue_job(db:Session,user:User,job_type:str,idempotency_key:str,payload:dict,max_attempts:int)->tuple[OperationalJob,bool]:
    if job_type not in ALLOWED_JOBS: raise HTTPException(status_code=422,detail="Tipo de job não permitido")
    existing=db.scalar(select(OperationalJob).where(OperationalJob.idempotency_key==idempotency_key))
    if existing:
        if existing.organization_id!=user.organization_id: raise HTTPException(status_code=409,detail="Chave idempotente já utilizada")
        return existing,False
    item=OperationalJob(organization_id=user.organization_id,job_type=job_type,idempotency_key=idempotency_key,payload_json=json.dumps(payload,ensure_ascii=False),max_attempts=max_attempts)
    db.add(item);return item,True


def process_job(item:OperationalJob,simulate_failure:bool=False)->OperationalJob:
    if item.status=="COMPLETED": return item
    if item.status=="DEAD_LETTER": raise HTTPException(status_code=409,detail="Job esgotou as tentativas")
    now=datetime.now(UTC);item.status="RUNNING";item.locked_at=now;item.attempts+=1
    if simulate_failure:
        item.last_error="Falha transitória simulada"
        if item.attempts>=item.max_attempts: item.status="DEAD_LETTER"
        else:
            item.status="RETRY_SCHEDULED";item.scheduled_at=now+timedelta(seconds=min(300,2**item.attempts))
        return item
    item.status="COMPLETED";item.completed_at=now;item.last_error=None;item.result_json=json.dumps({"processed":True,"job_type":item.job_type});return item


def system_readiness(db:Session)->dict:
    try: db.execute(text("SELECT 1"));database="UP"
    except Exception: database="DOWN"
    return {"status":"ready" if database=="UP" else "not_ready","database":database,"worker_mode":"DATABASE_QUEUE","financial_transactions":"LOCKED"}


def operational_metrics(db:Session,user:User)->dict:
    base=OperationalJob.organization_id==user.organization_id
    count=lambda status: db.scalar(select(func.count()).select_from(OperationalJob).where(base,OperationalJob.status==status)) or 0
    total=db.scalar(select(func.count()).select_from(OperationalJob).where(base)) or 0
    attempts=db.scalar(select(func.coalesce(func.sum(OperationalJob.attempts),0)).where(base)) or 0
    webhook_total=db.scalar(select(func.count()).select_from(WebhookDelivery).where(WebhookDelivery.organization_id==user.organization_id)) or 0
    webhook_delivered=db.scalar(select(func.count()).select_from(WebhookDelivery).where(WebhookDelivery.organization_id==user.organization_id,WebhookDelivery.status=="DELIVERED")) or 0
    incidents_open=db.scalar(select(func.count()).select_from(ProviderIncident).where(ProviderIncident.organization_id==user.organization_id,ProviderIncident.status.in_(["OPEN","ACKNOWLEDGED"]))) or 0
    circuits_open=db.scalar(select(func.count()).select_from(ProviderIntegration).where(ProviderIntegration.organization_id==user.organization_id,ProviderIntegration.circuit_status=="OPEN")) or 0
    return {"jobs_total":total,"pending":count("PENDING"),"retry_scheduled":count("RETRY_SCHEDULED"),"completed":count("COMPLETED"),"dead_letter":count("DEAD_LETTER"),"attempts_total":attempts,"webhooks_total":webhook_total,"webhooks_delivered":webhook_delivered,"provider_incidents_open":incidents_open,"circuits_open":circuits_open}


def process_due_jobs(db:Session,batch_size:int=20)->dict:
    now=datetime.now(UTC)
    query=select(OperationalJob).where(OperationalJob.status.in_(["PENDING","RETRY_SCHEDULED"]),OperationalJob.scheduled_at<=now).order_by(OperationalJob.scheduled_at).limit(batch_size)
    if db.bind and db.bind.dialect.name=="postgresql": query=query.with_for_update(skip_locked=True)
    items=list(db.scalars(query));completed=0
    for item in items:
        process_job(item);completed+=1
    db.commit();return {"selected":len(items),"completed":completed}


def homologation_status(db:Session,organization_id:str|None=None)->dict:
    readiness=system_readiness(db);issues=settings.production_issues()
    checks={"database":readiness["database"],"environment":settings.env,"storage_backend":settings.storage_backend,"secret_key":"OK" if len(settings.secret_key)>=32 and settings.secret_key!="development-only-secret-key-change-me" else "DEVELOPMENT_ONLY","cors_origins":settings.cors_origins,"financial_guard":"LOCKED" if not settings.financial_transactions_enabled else "ENABLED"}
    providers={"baas":"NOT_CONFIGURED","kyc":"MOCK","signature":"MOCK","communications":"MOCK","tax":"MOCK"}
    if organization_id:
        items=list(db.scalars(select(ProviderIntegration).where(ProviderIntegration.organization_id==organization_id,ProviderIntegration.active.is_(True))))
        for item in items:
            uptime=round(item.successful_checks/item.total_checks*100,2) if item.total_checks else 0
            providers[item.category.lower()]=f"{item.environment}:{item.health_status}:{item.circuit_status}:SLA {uptime}%"
    return {"status":"BLOCKED" if issues else ("DEVELOPMENT" if settings.env=="development" else "READY_FOR_STAGING"),"checks":checks,"blocking_issues":issues,"external_providers":providers}
