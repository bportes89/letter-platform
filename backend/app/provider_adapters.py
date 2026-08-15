import hashlib
import json
from abc import ABC, abstractmethod
from dataclasses import dataclass
from datetime import UTC, datetime

from fastapi import HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import AdapterExecution, ProviderIntegration, User


@dataclass(frozen=True)
class AdapterResult:
    external_id:str
    status:str
    data:dict


class ProviderAdapter(ABC):
    category:str
    name:str
    version="sandbox-v1"
    capabilities:tuple[str,...]

    @abstractmethod
    def execute(self,operation:str,payload:dict,idempotency_key:str)->AdapterResult: ...

    def _ensure(self,operation:str)->None:
        if operation not in self.capabilities:raise HTTPException(status_code=422,detail=f"Operação {operation} não suportada por {self.category}")

    def _id(self,prefix:str,key:str)->str:
        return f"{prefix}_{hashlib.sha256(key.encode()).hexdigest()[:20]}"


class BaasSandboxAdapter(ProviderAdapter):
    category="BAAS";name="LETTER BaaS Sandbox";capabilities=("create_account","create_charge","get_transaction")
    def execute(self,operation,payload,key):
        self._ensure(operation);external=self._id("baas",key)
        if operation=="create_account" and not payload.get("document"):raise HTTPException(status_code=422,detail="document obrigatório")
        if operation=="create_charge" and float(payload.get("amount",0))<=0:raise HTTPException(status_code=422,detail="amount deve ser positivo")
        return AdapterResult(external,"CREATED" if operation!="get_transaction" else "SETTLED",{"operation":operation,"account_id":payload.get("account_id"),"amount":payload.get("amount")})


class KycSandboxAdapter(ProviderAdapter):
    category="KYC";name="LETTER KYC Sandbox";capabilities=("start_verification","get_result")
    def execute(self,operation,payload,key):
        self._ensure(operation)
        if not payload.get("subject_id"):raise HTTPException(status_code=422,detail="subject_id obrigatório")
        return AdapterResult(self._id("kyc",key),"PENDING" if operation=="start_verification" else "APPROVED",{"risk_level":"LOW","subject_id":payload["subject_id"]})


class SignatureSandboxAdapter(ProviderAdapter):
    category="SIGNATURE";name="LETTER Signature Sandbox";capabilities=("create_envelope","get_status")
    def execute(self,operation,payload,key):
        self._ensure(operation)
        if not payload.get("signer_email"):raise HTTPException(status_code=422,detail="signer_email obrigatório")
        return AdapterResult(self._id("sign",key),"SENT" if operation=="create_envelope" else "SIGNED",{"signer_email":payload["signer_email"]})


class CommunicationsSandboxAdapter(ProviderAdapter):
    category="COMMUNICATIONS";name="LETTER Communications Sandbox";capabilities=("send_template","get_delivery")
    def execute(self,operation,payload,key):
        self._ensure(operation)
        if operation=="send_template" and (not payload.get("destination") or not payload.get("template")):raise HTTPException(status_code=422,detail="destination e template obrigatórios")
        masked="***"+str(payload.get("destination", ""))[-4:]
        return AdapterResult(self._id("msg",key),"QUEUED" if operation=="send_template" else "DELIVERED",{"destination_masked":masked,"channel":payload.get("channel","WHATSAPP")})


class TaxSandboxAdapter(ProviderAdapter):
    category="TAX";name="LETTER NFS-e Sandbox";capabilities=("issue_document","get_status")
    def execute(self,operation,payload,key):
        self._ensure(operation)
        if operation=="issue_document" and (not payload.get("document") or float(payload.get("amount",0))<=0):raise HTTPException(status_code=422,detail="document e amount obrigatórios")
        return AdapterResult(self._id("nfse",key),"AUTHORIZED" if operation=="issue_document" else "AVAILABLE",{"document_number":self._id("doc",key),"amount":payload.get("amount")})


ADAPTER_TYPES={x.category:x for x in (BaasSandboxAdapter,KycSandboxAdapter,SignatureSandboxAdapter,CommunicationsSandboxAdapter,TaxSandboxAdapter)}


def get_adapter(integration:ProviderIntegration)->ProviderAdapter:
    adapter_type=ADAPTER_TYPES.get(integration.category)
    if not adapter_type:raise HTTPException(status_code=422,detail="Categoria sem adaptador registrado")
    if integration.environment!="SANDBOX":raise HTTPException(status_code=409,detail="Adaptador oficial ainda não registrado para produção")
    return adapter_type()


def adapter_catalog()->list[dict]:
    return [{"category":category,"adapter":cls.name,"version":cls.version,"capabilities":list(cls.capabilities),"mode":"SANDBOX"} for category,cls in ADAPTER_TYPES.items()]


def execute_adapter(db:Session,user:User,integration:ProviderIntegration,operation:str,payload:dict,idempotency_key:str)->tuple[AdapterExecution,bool]:
    canonical=json.dumps(payload,ensure_ascii=False,separators=(",",":"),sort_keys=True)
    input_hash=hashlib.sha256(canonical.encode()).hexdigest()
    existing=db.scalar(select(AdapterExecution).where(AdapterExecution.integration_id==integration.id,AdapterExecution.idempotency_key==idempotency_key))
    if existing:
        if existing.operation!=operation or existing.input_hash!=input_hash:
            raise HTTPException(status_code=409,detail="Chave de idempotência já utilizada com outra operação ou payload")
        return existing,False
    adapter=get_adapter(integration);result=adapter.execute(operation,payload,idempotency_key)
    output={**result.data,"external_id":result.external_id,"status":result.status,"processed_at":datetime.now(UTC).isoformat()}
    item=AdapterExecution(organization_id=user.organization_id,integration_id=integration.id,category=integration.category,operation=operation,idempotency_key=idempotency_key,input_hash=input_hash,output_json=json.dumps(output,ensure_ascii=False),external_id=result.external_id,status=result.status,adapter_name=adapter.name,adapter_version=adapter.version);db.add(item);return item,True
