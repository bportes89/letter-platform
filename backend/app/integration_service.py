import base64
import hashlib
import hmac
import ipaddress
import json
import time
from datetime import UTC, datetime, timedelta
from urllib.parse import urljoin, urlparse

import httpx
from cryptography.fernet import Fernet
from fastapi import HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.config import settings
from app.models import ProviderIncident, ProviderIntegration, ProviderRequestLog, User, WebhookDelivery, WebhookEndpoint


ALLOWED_CATEGORIES = {"BAAS", "KYC", "SIGNATURE", "COMMUNICATIONS", "TAX", "CUSTOM"}
ALLOWED_ENVIRONMENTS = {"SANDBOX", "PRODUCTION"}


def _fernet() -> Fernet:
    key = base64.urlsafe_b64encode(hashlib.sha256(settings.secret_key.encode()).digest())
    return Fernet(key)


def protect(value: str) -> str:
    return _fernet().encrypt(value.encode()).decode()


def reveal(value: str) -> str:
    return _fernet().decrypt(value.encode()).decode()


def validate_target_url(url: str, environment: str, allowed_hosts: list[str] | None = None) -> None:
    parsed = urlparse(url)
    if parsed.scheme not in ({"https"} if environment == "PRODUCTION" else {"http", "https", "mock"}):
        raise HTTPException(status_code=422, detail="URL incompatível com o ambiente")
    if environment == "PRODUCTION" and (not parsed.hostname or parsed.hostname in {"localhost", "127.0.0.1", "::1"}):
        raise HTTPException(status_code=422, detail="Destino local não permitido em produção")
    if parsed.hostname:
        try:
            if ipaddress.ip_address(parsed.hostname).is_private: raise HTTPException(status_code=422,detail="Endereço privado não permitido")
        except ValueError: pass
    if allowed_hosts is not None and parsed.hostname not in allowed_hosts:
        raise HTTPException(status_code=422,detail="Host fora da allowlist da integração")


def configure_integration(db: Session, user: User, provider: str, category: str, environment: str, base_url: str | None, credential: str | None, allowed_hosts: list[str], sla_latency_ms: int) -> ProviderIntegration:
    provider = provider.strip().upper(); category = category.upper(); environment = environment.upper()
    if category not in ALLOWED_CATEGORIES or environment not in ALLOWED_ENVIRONMENTS:
        raise HTTPException(status_code=422, detail="Categoria ou ambiente inválido")
    hosts=sorted({x.strip().lower() for x in allowed_hosts if x.strip()})
    if base_url:
        parsed=urlparse(base_url);base_host=(parsed.hostname or "").lower()
        if not hosts: hosts=[base_host]
        validate_target_url(base_url, environment,hosts)
    if environment=="PRODUCTION" and not hosts: raise HTTPException(status_code=422,detail="Allowlist obrigatória em produção")
    existing = db.scalar(select(ProviderIntegration).where(ProviderIntegration.organization_id == user.organization_id, ProviderIntegration.provider == provider, ProviderIntegration.environment == environment))
    if existing:
        existing.category = category; existing.base_url = base_url; existing.active = True;existing.allowed_hosts_json=json.dumps(hosts);existing.sla_latency_ms=sla_latency_ms
        if credential: rotate_credential(existing,credential)
        return existing
    item = ProviderIntegration(organization_id=user.organization_id, provider=provider, category=category, environment=environment, base_url=base_url, credential_ciphertext=protect(credential) if credential else None,allowed_hosts_json=json.dumps(hosts),credential_rotated_at=datetime.now(UTC) if credential else None,sla_latency_ms=sla_latency_ms)
    db.add(item); return item


def rotate_credential(item:ProviderIntegration,credential:str)->ProviderIntegration:
    item.credential_ciphertext=protect(credential);item.credential_version+=1;item.credential_rotated_at=datetime.now(UTC);return item


def open_incident(db:Session,item:ProviderIntegration,incident_type:str,severity:str,title:str,details:str)->ProviderIncident:
    existing=db.scalar(select(ProviderIncident).where(ProviderIncident.integration_id==item.id,ProviderIncident.incident_type==incident_type,ProviderIncident.status.in_(["OPEN","ACKNOWLEDGED"])))
    if existing:return existing
    incident=ProviderIncident(organization_id=item.organization_id,integration_id=item.id,incident_type=incident_type,severity=severity,title=title,details=details[:1000]);db.add(incident);return incident


def resolve_incidents(db:Session,item:ProviderIntegration,incident_types:set[str])->None:
    now=datetime.now(UTC)
    for incident in db.scalars(select(ProviderIncident).where(ProviderIncident.integration_id==item.id,ProviderIncident.incident_type.in_(incident_types),ProviderIncident.status.in_(["OPEN","ACKNOWLEDGED"]))):
        incident.status="RESOLVED";incident.resolved_at=now


def probe_integration(db:Session,item: ProviderIntegration, simulate_status: str = "UP", latency_ms: int = 40) -> ProviderIntegration:
    now = datetime.now(UTC); status = simulate_status.upper()
    item.last_health_at = now; item.latency_ms = max(0, latency_ms);item.total_checks+=1
    if status == "UP":
        item.successful_checks+=1
        if latency_ms>item.sla_latency_ms:
            item.health_status="DEGRADED";open_incident(db,item,"SLA_LATENCY","MEDIUM",f"Latência acima do SLA em {item.provider}",f"Latência {latency_ms}ms; limite {item.sla_latency_ms}ms")
        else:item.health_status = "UP";resolve_incidents(db,item,{"PROVIDER_DOWN","CIRCUIT_OPEN","SLA_LATENCY"})
        item.consecutive_failures = 0; item.circuit_status = "CLOSED"; item.circuit_opened_at = None
    else:
        item.health_status = "DEGRADED" if status == "DEGRADED" else "DOWN"
        register_failure(item, now)
        open_incident(db,item,"PROVIDER_DOWN","HIGH",f"Provedor {item.provider} indisponível",f"Health check retornou {item.health_status}")
        if item.circuit_status=="OPEN":open_incident(db,item,"CIRCUIT_OPEN","HIGH",f"Circuit breaker aberto para {item.provider}",f"Falhas consecutivas: {item.consecutive_failures}")
    return item


def execute_provider_request(db:Session,item:ProviderIntegration,method:str,path:str,payload:dict|None=None,client:httpx.Client|None=None)->ProviderRequestLog:
    ensure_circuit_available(item)
    if not item.base_url:raise HTTPException(status_code=422,detail="Base URL não configurada")
    if method.upper() not in {"GET","POST"}:raise HTTPException(status_code=422,detail="Método HTTP não permitido")
    if not path.startswith("/") or path.startswith("//"):raise HTTPException(status_code=422,detail="Caminho relativo inválido")
    url=urljoin(item.base_url.rstrip("/")+"/",path.lstrip("/"));hosts=json.loads(item.allowed_hosts_json)
    validate_target_url(url,item.environment,hosts)
    headers={"Accept":"application/json","User-Agent":"LETTER-Connector/1.0"}
    if item.credential_ciphertext:headers["Authorization"]=f"Bearer {reveal(item.credential_ciphertext)}"
    started=time.perf_counter();response_code=None;error=None;success=False
    owned=client is None;http=client or httpx.Client(timeout=settings.integration_http_timeout_seconds,follow_redirects=False)
    try:
        response=http.request(method.upper(),url,json=payload if method.upper()=="POST" else None,headers=headers)
        response_code=response.status_code;success=200<=response.status_code<400
        if not success:error=f"HTTP {response.status_code}: {response.text[:300]}"
    except httpx.HTTPError as exc:error=f"{type(exc).__name__}: {str(exc)[:400]}"
    finally:
        if owned:http.close()
    latency=max(0,int((time.perf_counter()-started)*1000));log=ProviderRequestLog(organization_id=item.organization_id,integration_id=item.id,method=method.upper(),path=path,response_code=response_code,latency_ms=latency,success=success,error=error);db.add(log)
    probe_integration(db,item,"UP" if success else "DOWN",latency)
    return log


def register_failure(item: ProviderIntegration, now: datetime | None = None) -> None:
    now = now or datetime.now(UTC); item.consecutive_failures += 1
    if item.consecutive_failures >= settings.integration_circuit_failure_threshold:
        item.circuit_status = "OPEN"; item.circuit_opened_at = now


def ensure_circuit_available(item: ProviderIntegration) -> None:
    if item.circuit_status != "OPEN": return
    opened = item.circuit_opened_at or datetime.now(UTC)
    if opened.tzinfo is None: opened = opened.replace(tzinfo=UTC)
    if datetime.now(UTC) - opened < timedelta(seconds=settings.integration_circuit_cooldown_seconds):
        raise HTTPException(status_code=503, detail="Circuit breaker aberto para o provedor")
    item.circuit_status = "HALF_OPEN"


def create_endpoint(db: Session, user: User, integration: ProviderIntegration, name: str, target_url: str, secret: str, subscribed_events: list[str], max_attempts: int) -> WebhookEndpoint:
    validate_target_url(target_url, integration.environment,json.loads(integration.allowed_hosts_json) if not target_url.startswith("mock://") else None)
    existing = db.scalar(select(WebhookEndpoint).where(WebhookEndpoint.organization_id == user.organization_id, WebhookEndpoint.name == name))
    if existing: raise HTTPException(status_code=409, detail="Endpoint com este nome já existe")
    item = WebhookEndpoint(organization_id=user.organization_id, integration_id=integration.id, name=name, target_url=target_url, secret_ciphertext=protect(secret), subscribed_events_json=json.dumps(sorted(set(subscribed_events))), max_attempts=max_attempts)
    db.add(item); return item


def canonical_payload(payload: dict) -> str:
    return json.dumps(payload, ensure_ascii=False, separators=(",", ":"), sort_keys=True)


def sign_webhook(secret: str, timestamp: int, payload_json: str) -> str:
    digest = hmac.new(secret.encode(), f"{timestamp}.{payload_json}".encode(), hashlib.sha256).hexdigest()
    return f"t={timestamp},v1={digest}"


def verify_webhook(secret: str, signature: str, payload: dict, tolerance_seconds: int = 300) -> bool:
    try:
        parts = dict(part.split("=", 1) for part in signature.split(",")); timestamp = int(parts["t"])
        if abs(int(datetime.now(UTC).timestamp()) - timestamp) > tolerance_seconds: return False
        expected = sign_webhook(secret, timestamp, canonical_payload(payload)).split("v1=", 1)[1]
        return hmac.compare_digest(expected, parts["v1"])
    except (KeyError, ValueError):
        return False


def dispatch_webhook(db: Session, user: User, endpoint: WebhookEndpoint, integration: ProviderIntegration, event_id: str, event_type: str, payload: dict, simulate_failure: bool = False) -> tuple[WebhookDelivery, bool]:
    existing = db.scalar(select(WebhookDelivery).where(WebhookDelivery.endpoint_id == endpoint.id, WebhookDelivery.event_id == event_id))
    if existing: return existing, False
    subscriptions = json.loads(endpoint.subscribed_events_json)
    if subscriptions and event_type not in subscriptions and "*" not in subscriptions:
        raise HTTPException(status_code=422, detail="Evento não assinado pelo endpoint")
    ensure_circuit_available(integration)
    body = canonical_payload(payload); timestamp = int(datetime.now(UTC).timestamp())
    item = WebhookDelivery(organization_id=user.organization_id, endpoint_id=endpoint.id, event_id=event_id, event_type=event_type, payload_json=body, signature=sign_webhook(reveal(endpoint.secret_ciphertext), timestamp, body), max_attempts=endpoint.max_attempts)
    db.add(item); db.flush(); attempt_delivery(item, integration, simulate_failure,db,endpoint); return item, True


def attempt_delivery(item: WebhookDelivery, integration: ProviderIntegration, simulate_failure: bool = False, db:Session|None=None, endpoint:WebhookEndpoint|None=None, client:httpx.Client|None=None) -> WebhookDelivery:
    ensure_circuit_available(integration); now = datetime.now(UTC); item.attempts += 1
    if integration.environment=="PRODUCTION" and endpoint and not simulate_failure:
        validate_target_url(endpoint.target_url,"PRODUCTION",json.loads(integration.allowed_hosts_json));owned=client is None;http=client or httpx.Client(timeout=settings.integration_http_timeout_seconds,follow_redirects=False)
        try:
            response=http.post(endpoint.target_url,content=item.payload_json.encode(),headers={"Content-Type":"application/json","X-LETTER-Signature":item.signature,"X-LETTER-Event-ID":item.event_id,"User-Agent":"LETTER-Webhooks/1.0"})
            if 200<=response.status_code<300:
                item.status="DELIVERED";item.response_code=response.status_code;item.response_body=response.text[:500];item.last_error=None;item.next_attempt_at=None;item.delivered_at=now
                integration.health_status="UP";integration.consecutive_failures=0;integration.circuit_status="CLOSED";integration.circuit_opened_at=None;integration.last_health_at=now
                if db:resolve_incidents(db,integration,{"PROVIDER_DOWN","CIRCUIT_OPEN"})
                return item
            item.response_code=response.status_code;item.response_body=response.text[:500];item.last_error=f"HTTP {response.status_code}"
        except httpx.HTTPError as exc:item.response_code=None;item.response_body=None;item.last_error=f"{type(exc).__name__}: {str(exc)[:400]}"
        finally:
            if owned:http.close()
        simulate_failure=True
    if simulate_failure:
        item.response_code = item.response_code or 503; item.response_body = item.response_body or "sandbox provider unavailable"; item.last_error = item.last_error or "Falha transitória do provedor"
        register_failure(integration, now)
        if db:open_incident(db,integration,"WEBHOOK_DELIVERY","HIGH",f"Falha de webhook em {integration.provider}",item.last_error)
        if item.attempts >= item.max_attempts:
            item.status = "DEAD_LETTER"; item.next_attempt_at = None
        else:
            item.status = "RETRY_SCHEDULED"; item.next_attempt_at = now + timedelta(seconds=min(900, 2 ** item.attempts))
        return item
    item.status = "DELIVERED"; item.response_code = 200; item.response_body = "sandbox accepted"; item.last_error = None; item.next_attempt_at = None; item.delivered_at = now
    integration.health_status = "UP"; integration.consecutive_failures = 0; integration.circuit_status = "CLOSED"; integration.circuit_opened_at = None; integration.last_health_at = now
    return item


def reprocess_dead_letters(db:Session,user:User,delivery_ids:list[str])->dict:
    if len(delivery_ids)>100:raise HTTPException(status_code=422,detail="Máximo de 100 entregas por lote")
    items=list(db.scalars(select(WebhookDelivery).where(WebhookDelivery.organization_id==user.organization_id,WebhookDelivery.id.in_(delivery_ids))))
    selected=0
    for item in items:
        if item.status!="DEAD_LETTER":continue
        item.status="RETRY_SCHEDULED";item.attempts=0;item.last_error=None;item.next_attempt_at=datetime.now(UTC);selected+=1
    return {"requested":len(delivery_ids),"requeued":selected,"skipped":len(delivery_ids)-selected}
