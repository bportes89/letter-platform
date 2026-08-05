import hashlib
import json
from datetime import UTC, datetime

from fastapi import HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import (
    AdapterCertificationRun, HomologationEvidence, ProviderGoLiveApproval,
    ProviderGoLiveDecision, ProviderIncident, ProviderIntegration,
    ProviderOnboardingProfile, User,
)
from app.provider_adapters import ADAPTER_TYPES


APPROVAL_AREAS={"SECURITY","LEGAL","COMPLIANCE","OPERATIONS"}
APPROVAL_DECISIONS={"APPROVED","REJECTED"}


def _canonical_hash(payload:dict)->str:
    raw=json.dumps(payload,ensure_ascii=False,separators=(",",":"),sort_keys=True)
    return hashlib.sha256(raw.encode()).hexdigest()


def certify_adapter(db:Session,user:User,integration:ProviderIntegration)->AdapterCertificationRun:
    adapter_type=ADAPTER_TYPES.get(integration.category)
    profile=db.scalar(select(ProviderOnboardingProfile).where(ProviderOnboardingProfile.integration_id==integration.id))
    evidence_count=len(list(db.scalars(select(HomologationEvidence).where(HomologationEvidence.integration_id==integration.id,HomologationEvidence.result=="PASS"))))
    checks={
        "adapter_contract_registered":adapter_type is not None,
        "capabilities_declared":bool(adapter_type and adapter_type.capabilities),
        "credential_configured":integration.credential_version>0,
        "allowlist_configured":bool(json.loads(integration.allowed_hosts_json or "[]")),
        "health_check_passed":integration.health_status=="UP",
        "circuit_closed":integration.circuit_status=="CLOSED",
        "onboarding_profile_configured":profile is not None,
        "homologation_evidence_complete":evidence_count>=6,
    }
    report={"provider":integration.provider,"category":integration.category,"environment":integration.environment,"checks":checks,"executed_at":datetime.now(UTC).isoformat()}
    passed=sum(checks.values())
    item=AdapterCertificationRun(organization_id=user.organization_id,integration_id=integration.id,status="PASS" if passed==len(checks) else "FAIL",passed_checks=passed,total_checks=len(checks),report_json=json.dumps(report,ensure_ascii=False),report_hash=_canonical_hash(report),executed_by_id=user.id)
    db.add(item);return item


def decide_approval(db:Session,user:User,integration:ProviderIntegration,area:str,decision:str,notes:str)->ProviderGoLiveApproval:
    area=area.upper();decision=decision.upper()
    if area not in APPROVAL_AREAS:raise HTTPException(status_code=422,detail="Área de aprovação inválida")
    if decision not in APPROVAL_DECISIONS:raise HTTPException(status_code=422,detail="Decisão inválida")
    item=db.scalar(select(ProviderGoLiveApproval).where(ProviderGoLiveApproval.integration_id==integration.id,ProviderGoLiveApproval.area==area))
    if item:
        item.decision=decision;item.notes=notes;item.decided_by_id=user.id;item.decided_at=datetime.now(UTC)
    else:
        item=ProviderGoLiveApproval(organization_id=user.organization_id,integration_id=integration.id,area=area,decision=decision,notes=notes,decided_by_id=user.id);db.add(item)
    return item


def evaluate_go_live(db:Session,user:User,integration:ProviderIntegration)->ProviderGoLiveDecision:
    latest=db.scalar(select(AdapterCertificationRun).where(AdapterCertificationRun.integration_id==integration.id).order_by(AdapterCertificationRun.executed_at.desc()))
    approvals=list(db.scalars(select(ProviderGoLiveApproval).where(ProviderGoLiveApproval.integration_id==integration.id)))
    approved={x.area for x in approvals if x.decision=="APPROVED"}
    open_incidents=len(list(db.scalars(select(ProviderIncident).where(ProviderIncident.integration_id==integration.id,ProviderIncident.status.in_(["OPEN","ACKNOWLEDGED"])))))
    blockers=[]
    if integration.environment!="PRODUCTION":blockers.append("integration_not_production")
    # Official implementations are intentionally empty until vendor code is delivered.
    blockers.append("official_adapter_not_registered")
    if not latest or latest.status!="PASS":blockers.append("certification_not_passed")
    for area in sorted(APPROVAL_AREAS-approved):blockers.append(f"approval_missing:{area}")
    if open_incidents:blockers.append("open_provider_incidents")
    if integration.health_status!="UP" or integration.circuit_status!="CLOSED":blockers.append("provider_health_not_ready")
    snapshot={"integration_id":integration.id,"provider":integration.provider,"blockers":blockers,"evaluated_at":datetime.now(UTC).isoformat()}
    item=ProviderGoLiveDecision(organization_id=user.organization_id,integration_id=integration.id,status="APPROVED" if not blockers else "BLOCKED",blockers_json=json.dumps(blockers),snapshot_hash=_canonical_hash(snapshot),decided_by_id=user.id);db.add(item);return item
