"""Carteira Asaas — dados bancários, KYC, extrato, Pix, webhooks."""

from __future__ import annotations

import json
import re
from datetime import UTC, datetime
from decimal import Decimal
from uuid import uuid4

from fastapi import HTTPException, UploadFile
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.asaas_client import AsaasClient
from app.asaas_common import asaas_configured
from app.core.config import settings
from app.financial_service import ensure_chart, process_escrow_event
from app.models import EscrowAccount, EscrowEvent, User
from app.services import money
from app.subaccount_auto_service import find_user_plain_subaccount


TRANSACTION_LABELS = {
    "PAYMENT_RECEIVED": "Cobrança recebida",
    "TRANSFER": "Transferência",
    "TRANSFER_SENT": "Saque/transferência realizada",
    "BILL_PAYMENT": "Pagamento de conta",
    "PAYMENT_FEE": "Taxa de cobrança",
    "DEBIT": "Débito",
    "CREDIT": "Crédito",
    "INTERNAL_TRANSFER_DEBIT": "Transferência interna (saída)",
    "INTERNAL_TRANSFER_CREDIT": "Transferência interna (entrada)",
}


def _digits(value: str | None) -> str:
    return re.sub(r"\D", "", value or "")


def _is_mock_account(account: EscrowAccount) -> bool:
    return account.provider in {"MOCK", "MOCK_SUBACCOUNT"} or not asaas_configured()


def subaccount_client(account: EscrowAccount) -> AsaasClient:
    key = (account.asaas_subaccount_api_key or "").strip()
    if key:
        return AsaasClient(api_key=key)
    return AsaasClient()


def apply_banking_fields(account: EscrowAccount, *, api_key: str | None = None, payload: dict | None = None) -> None:
    if api_key:
        account.asaas_subaccount_api_key = api_key
    payload = payload or {}
    account_number = payload.get("accountNumber") or payload.get("account")
    if isinstance(account_number, dict):
        account.bank_account_number = str(account_number.get("account") or account_number.get("accountNumber") or account.bank_account_number or "")
        account.bank_agency = str(account_number.get("agency") or account.bank_agency or settings.asaas_default_agency)
    elif account_number:
        account.bank_account_number = str(account_number)
    account.bank_code = str(payload.get("bank") or payload.get("bankCode") or account.bank_code or settings.asaas_bank_code)
    account.bank_agency = str(payload.get("agency") or account.bank_agency or settings.asaas_default_agency)


def ensure_mock_banking(account: EscrowAccount) -> None:
    if not account.bank_account_number:
        account.bank_code = settings.asaas_bank_code
        account.bank_agency = settings.asaas_default_agency
        account.bank_account_number = f"{account.external_account_id[-8:]}-{uuid4().hex[:2]}"
    if not account.pix_key:
        account.pix_key = f"mock-pix-{account.external_account_id[-12:]}"
    if not account.asaas_kyc_status:
        account.asaas_kyc_status = "APPROVED"
    if not account.asaas_commercial_status:
        account.asaas_commercial_status = "APPROVED"


def sync_account_from_asaas(db: Session, account: EscrowAccount) -> EscrowAccount:
    if _is_mock_account(account):
        ensure_mock_banking(account)
        db.flush()
        return account

    with subaccount_client(account) as client:
        balance_payload = client.get_balance()
        commercial = client.get_commercial_info()
        try:
            account_number_payload = client.get_account_number()
        except HTTPException:
            account_number_payload = {}

        account.available_balance = money(Decimal(str(balance_payload.get("balance", account.available_balance or 0))))
        account.asaas_commercial_status = str(commercial.get("status") or commercial.get("commercialInfoStatus") or account.asaas_commercial_status or "PENDING")
        account.asaas_kyc_status = str(commercial.get("documentationStatus") or account.asaas_kyc_status or "PENDING")
        apply_banking_fields(account, payload=account_number_payload)

        docs = client.list_documents()
        data = docs.get("data") if isinstance(docs.get("data"), list) else docs if isinstance(docs, list) else []
        for item in data:
            url = item.get("onboardingUrl")
            if url:
                account.asaas_onboarding_url = str(url)
                break

        if not account.pix_key:
            keys = client.list_pix_keys()
            key_rows = keys.get("data") if isinstance(keys.get("data"), list) else []
            active = next((row for row in key_rows if row.get("status") == "ACTIVE"), None)
            if active:
                account.pix_key = str(active.get("key") or "")

    db.flush()
    return account


def wallet_view(db: Session, user: User) -> dict:
    account = find_user_plain_subaccount(db, user)
    kyc_case = None
    from app.subaccount_auto_service import find_user_kyc_case

    case = find_user_kyc_case(db, user)
    if case:
        kyc_case = {
            "id": case.id,
            "status": case.status,
            "risk_level": case.risk_level,
            "provider": case.provider,
        }

    if not account:
        return {
            "has_subaccount": False,
            "kyc_case": kyc_case,
            "message": "Subconta ainda não provisionada. Conclua o KYC para abrir sua carteira.",
        }

    if _is_mock_account(account):
        ensure_mock_banking(account)
        db.flush()

    return {
        "has_subaccount": True,
        "kyc_case": kyc_case,
        "account": _account_payload(account),
        "banking": _banking_payload(account),
        "capabilities": _capabilities(account),
        "message": _wallet_message(account),
    }


def _account_payload(account: EscrowAccount) -> dict:
    return {
        "id": account.id,
        "provider": account.provider,
        "subaccount_name": account.subaccount_name,
        "escrow_enabled": account.escrow_enabled,
        "status": account.status,
        "available_balance": str(account.available_balance),
        "locked_balance": str(account.locked_balance),
        "asaas_kyc_status": account.asaas_kyc_status,
        "asaas_commercial_status": account.asaas_commercial_status,
        "asaas_onboarding_url": account.asaas_onboarding_url,
    }


def _banking_payload(account: EscrowAccount) -> dict:
    return {
        "bank_code": account.bank_code or settings.asaas_bank_code,
        "bank_name": settings.asaas_bank_name,
        "agency": account.bank_agency or settings.asaas_default_agency,
        "account_number": account.bank_account_number,
        "pix_key": account.pix_key,
        "display_bank": f"{account.bank_code or settings.asaas_bank_code} - {settings.asaas_bank_name}",
    }


def _capabilities(account: EscrowAccount) -> dict:
    approved = (account.asaas_kyc_status or "").upper() in {"APPROVED", "ACTIVE"} or _is_mock_account(account)
    return {
        "deposits_enabled": True,
        "withdrawals_enabled": approved and not account.escrow_enabled,
        "bill_payments_enabled": approved,
        "pix_key_enabled": approved,
        "escrow_locked": account.escrow_enabled,
    }


def _wallet_message(account: EscrowAccount) -> str:
    if account.escrow_enabled:
        return "Conta com Escrow — saques dependem da liberação operacional."
    status = (account.asaas_kyc_status or "PENDING").upper()
    if status in {"APPROVED", "ACTIVE"}:
        return "Carteira ativa — depósitos, saques e pagamentos disponíveis conforme saldo."
    if account.asaas_onboarding_url:
        return "Envie seus documentos pelo link de onboarding Asaas para liberar saques e transferências."
    return "Documentação pendente — envie os documentos KYC para liberar saques e transferências."


def list_wallet_transactions(db: Session, account: EscrowAccount, *, offset: int = 0, limit: int = 50) -> dict:
    if _is_mock_account(account):
        events = list(
            db.scalars(
                select(EscrowEvent)
                .where(EscrowEvent.escrow_account_id == account.id)
                .order_by(EscrowEvent.processed_at.desc())
                .offset(offset)
                .limit(limit)
            )
        )
        rows = [
            {
                "id": event.provider_event_id,
                "type": event.event_type,
                "label": TRANSACTION_LABELS.get(event.event_type, event.event_type),
                "amount": str(event.amount),
                "direction": "CREDIT" if event.event_type in {"FUNDS_CONFIRMED", "PAYMENT_RECEIVED", "CREDIT"} else "DEBIT",
                "date": event.processed_at.isoformat(),
            }
            for event in events
        ]
        return {"total": len(rows), "items": rows, "source": "MOCK"}

    with subaccount_client(account) as client:
        payload = client.list_financial_transactions(offset=offset, limit=limit)
    rows = []
    for item in payload.get("data", []):
        event_type = str(item.get("type") or item.get("event") or "MOVEMENT")
        value = item.get("value") or item.get("amount") or 0
        rows.append(
            {
                "id": str(item.get("id") or uuid4()),
                "type": event_type,
                "label": TRANSACTION_LABELS.get(event_type, event_type.replace("_", " ").title()),
                "amount": str(abs(Decimal(str(value)))),
                "direction": "CREDIT" if Decimal(str(value)) >= 0 else "DEBIT",
                "date": str(item.get("date") or item.get("effectiveDate") or datetime.now(UTC).isoformat()),
            }
        )
    return {"total": payload.get("totalCount", len(rows)), "items": rows, "source": "ASAAS"}


def list_kyc_documents(db: Session, account: EscrowAccount) -> dict:
    if _is_mock_account(account):
        ensure_mock_banking(account)
        return {
            "source": "MOCK",
            "items": [
                {
                    "id": "identification",
                    "title": "Documento de identificação + selfie",
                    "status": "APPROVED",
                    "onboarding_url": None,
                    "accepts_api_upload": False,
                }
            ],
        }

    with subaccount_client(account) as client:
        payload = client.list_documents()
    data = payload.get("data") if isinstance(payload.get("data"), list) else payload if isinstance(payload, list) else []
    items = []
    for row in data:
        onboarding_url = row.get("onboardingUrl")
        items.append(
            {
                "id": str(row.get("id") or row.get("type") or uuid4()),
                "title": str(row.get("title") or row.get("description") or row.get("type") or "Documento"),
                "status": str(row.get("status") or "PENDING"),
                "onboarding_url": onboarding_url,
                "accepts_api_upload": not bool(onboarding_url),
            }
        )
        if onboarding_url and not account.asaas_onboarding_url:
            account.asaas_onboarding_url = str(onboarding_url)
    db.flush()
    return {"source": "ASAAS", "items": items}


async def upload_kyc_document(db: Session, account: EscrowAccount, document_id: str, file: UploadFile) -> dict:
    content = await file.read()
    if _is_mock_account(account):
        account.asaas_kyc_status = "UNDER_REVIEW"
        db.flush()
        return {"status": "UNDER_REVIEW", "message": "Documento recebido em homologação (mock)."}

    with subaccount_client(account) as client:
        docs = list_kyc_documents(db, account)
        target = next((item for item in docs["items"] if item["id"] == document_id), None)
        if not target:
            raise HTTPException(status_code=404, detail="Grupo documental não encontrado")
        if target.get("onboarding_url"):
            raise HTTPException(status_code=422, detail="Este documento deve ser enviado pelo link de onboarding Asaas.")
        result = client.upload_document(
            document_id,
            file_bytes=content,
            filename=file.filename or "documento.pdf",
            content_type=file.content_type or "application/pdf",
        )
    account.asaas_kyc_status = "UNDER_REVIEW"
    db.flush()
    return {"status": "UNDER_REVIEW", "message": "Documento enviado ao Asaas para análise.", "provider": result}


def create_wallet_pix_key(db: Session, account: EscrowAccount) -> dict:
    if account.pix_key:
        return {"pix_key": account.pix_key, "created": False, "message": "Chave Pix já existente."}
    if _is_mock_account(account):
        ensure_mock_banking(account)
        db.flush()
        return {"pix_key": account.pix_key, "created": True, "message": "Chave Pix mock gerada."}

    with subaccount_client(account) as client:
        created = client.create_pix_key(key_type="EVP")
        account.pix_key = str(created.get("key") or "")
        qr = client.get_pix_qrcode(account.pix_key) if account.pix_key else {}
    db.flush()
    return {
        "pix_key": account.pix_key,
        "created": True,
        "qr_code_payload": qr.get("payload"),
        "qr_code_image_base64": qr.get("encodedImage"),
        "message": "Chave Pix aleatória (EVP) criada.",
    }


def get_wallet_pix_qrcode(account: EscrowAccount) -> dict:
    if not account.pix_key:
        raise HTTPException(status_code=404, detail="Chave Pix não configurada.")
    if _is_mock_account(account):
        return {
            "pix_key": account.pix_key,
            "payload": f"00020126MOCKPIX{account.pix_key}",
            "encoded_image": None,
        }
    with subaccount_client(account) as client:
        qr = client.get_pix_qrcode(account.pix_key)
    return {"pix_key": account.pix_key, "payload": qr.get("payload"), "encoded_image": qr.get("encodedImage")}


def request_wallet_transfer(db: Session, user: User, account: EscrowAccount, *, pix_key: str, amount: Decimal, description: str | None) -> dict:
    if account.escrow_enabled:
        raise HTTPException(status_code=422, detail="Subconta com Escrow — saque via fluxo operacional.")
    if (account.asaas_kyc_status or "").upper() not in {"APPROVED", "ACTIVE"} and not _is_mock_account(account):
        raise HTTPException(status_code=422, detail="KYC Asaas pendente — saques bloqueados até aprovação.")
    value = money(amount)
    if Decimal(str(account.available_balance)) < value:
        raise HTTPException(status_code=422, detail="Saldo insuficiente.")

    if _is_mock_account(account):
        account.available_balance = money(Decimal(str(account.available_balance)) - value)
        event_id = f"mock_transfer_{uuid4().hex[:12]}"
        db.add(
            EscrowEvent(
                organization_id=account.organization_id,
                escrow_account_id=account.id,
                provider_event_id=event_id,
                event_type="TRANSFER_SENT",
                amount=float(value),
                payload_json=json.dumps({"pix_key": pix_key, "description": description}, ensure_ascii=False),
            )
        )
        db.flush()
        return {"provider": "MOCK", "transfer_id": event_id, "status": "DONE", "amount": str(value)}

    with subaccount_client(account) as client:
        result = client.create_transfer(
            {
                "value": float(value),
                "pixAddressKey": pix_key,
                "description": description or "Saque LETTER",
            }
        )
    account.available_balance = money(Decimal(str(account.available_balance)) - value)
    db.flush()
    return {
        "provider": "ASAAS",
        "transfer_id": str(result.get("id") or ""),
        "status": str(result.get("status") or "PENDING"),
        "amount": str(value),
    }


def request_bill_payment(db: Session, account: EscrowAccount, *, barcode: str, amount: Decimal, description: str | None) -> dict:
    if (account.asaas_kyc_status or "").upper() not in {"APPROVED", "ACTIVE"} and not _is_mock_account(account):
        raise HTTPException(status_code=422, detail="KYC Asaas pendente — pagamento de contas bloqueado.")
    value = money(amount)
    if Decimal(str(account.available_balance)) < value:
        raise HTTPException(status_code=422, detail="Saldo insuficiente.")

    if _is_mock_account(account):
        account.available_balance = money(Decimal(str(account.available_balance)) - value)
        event_id = f"mock_bill_{uuid4().hex[:12]}"
        db.add(
            EscrowEvent(
                organization_id=account.organization_id,
                escrow_account_id=account.id,
                provider_event_id=event_id,
                event_type="BILL_PAYMENT",
                amount=float(value),
                payload_json=json.dumps({"barcode": _digits(barcode), "description": description}, ensure_ascii=False),
            )
        )
        db.flush()
        return {"provider": "MOCK", "payment_id": event_id, "status": "DONE", "amount": str(value)}

    with subaccount_client(account) as client:
        result = client.create_bill_payment(
            {
                "identificationField": barcode,
                "scheduleDate": datetime.now(UTC).date().isoformat(),
                "description": description or "Pagamento de conta LETTER",
            }
        )
    account.available_balance = money(Decimal(str(account.available_balance)) - value)
    db.flush()
    return {
        "provider": "ASAAS",
        "payment_id": str(result.get("id") or ""),
        "status": str(result.get("status") or "PENDING"),
        "amount": str(value),
    }


def handle_asaas_webhook(db: Session, payload: dict) -> dict:
    event = str(payload.get("event") or payload.get("type") or "UNKNOWN")
    payment = payload.get("payment") if isinstance(payload.get("payment"), dict) else {}
    transfer = payload.get("transfer") if isinstance(payload.get("transfer"), dict) else {}
    account_ref = (
        payload.get("account")
        or payment.get("accountId")
        or transfer.get("accountId")
        or payload.get("accountId")
    )

    account = None
    if account_ref:
        account = db.scalar(
            select(EscrowAccount).where(
                (EscrowAccount.asaas_account_id == str(account_ref))
                | (EscrowAccount.external_account_id == str(account_ref))
            )
        )

    event_id = str(payload.get("id") or payload.get("event") or uuid4())
    processed = False

    if account and event in {"PAYMENT_RECEIVED", "PAYMENT_CONFIRMED"}:
        amount = Decimal(str(payment.get("value") or payment.get("netValue") or 0))
        if amount > 0:
            org_user = db.scalar(select(User).where(User.id == account.user_id)) if account.user_id else None
            actor = org_user or db.scalar(select(User).where(User.organization_id == account.organization_id).limit(1))
            if actor:
                _, processed = process_escrow_event(
                    db,
                    actor,
                    account,
                    event_id,
                    "PAYMENT_RECEIVED",
                    amount,
                    payload,
                )
                ensure_chart(db, actor)

    if account and event in {"ACCOUNT_STATUS_UPDATED", "ACCOUNT_DOCUMENTATION_APPROVED", "ACCOUNT_DOCUMENTATION_REJECTED"}:
        sync_account_from_asaas(db, account)
        processed = True

    if account and event.startswith("TRANSFER"):
        sync_account_from_asaas(db, account)
        processed = True

    if not processed and account:
        db.add(
            EscrowEvent(
                organization_id=account.organization_id,
                escrow_account_id=account.id,
                provider_event_id=f"asaas_wh_{event_id}",
                event_type=event,
                amount=0,
                payload_json=json.dumps(payload, ensure_ascii=False, default=str),
            )
        )

    return {"event": event, "processed": processed, "account_id": account.id if account else None}
