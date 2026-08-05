import json
from collections import defaultdict, deque
from datetime import UTC, datetime, timedelta
from threading import Lock

from fastapi import HTTPException
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.models import OperationalJob, SecurityEvent, TenantQuota, User


class SlidingWindowLimiter:
    def __init__(self): self.events=defaultdict(deque);self.lock=Lock()
    def allow(self,key:str,limit:int,window_seconds:int=60)->tuple[bool,int]:
        now=datetime.now(UTC).timestamp();cutoff=now-window_seconds
        with self.lock:
            bucket=self.events[key]
            while bucket and bucket[0]<=cutoff: bucket.popleft()
            if len(bucket)>=limit: return False,max(1,int(bucket[0]+window_seconds-now))
            bucket.append(now);return True,0
    def clear(self):
        with self.lock:self.events.clear()


rate_limiter=SlidingWindowLimiter()


def record_security_event(db:Session,event_type:str,severity:str,ip:str|None,subject:str|None,organization_id:str|None=None,metadata:dict|None=None):
    db.add(SecurityEvent(organization_id=organization_id,event_type=event_type,severity=severity,ip_address=ip,subject=subject,metadata_json=json.dumps(metadata or {},ensure_ascii=False)))


def get_or_create_quota(db:Session,user:User)->TenantQuota:
    item=db.scalar(select(TenantQuota).where(TenantQuota.organization_id==user.organization_id))
    if not item:item=TenantQuota(organization_id=user.organization_id);db.add(item);db.flush()
    return item


def check_job_quota(db:Session,user:User):
    quota=get_or_create_quota(db,user);start=datetime.now(UTC)-timedelta(days=1)
    used=db.scalar(select(func.count()).select_from(OperationalJob).where(OperationalJob.organization_id==user.organization_id,OperationalJob.created_at>=start)) or 0
    if used>=quota.jobs_per_day: raise HTTPException(status_code=429,detail="Quota diária de jobs atingida")
    return {"used":used,"limit":quota.jobs_per_day}
