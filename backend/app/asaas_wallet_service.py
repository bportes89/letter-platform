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
    "COMMISSION_CREDITED": "Comissão creditada",
    "TRANSFER": "Transferência",
    "TRANSFER_SENT": "Saque/transferência realizada",
  "BILL_PAYMENT": "Pagamento de conta",
  "BOLETO_ISSUED": "Boleto emitido",
  "PAYMENT_FEE": "Taxa de cobrança",
    "DEBIT": "Débito",
    "CREDIT": "Crédito",
    "INTERNAL_TRANSFER_DEBIT": "Transferência interna (saída)",
    "INTERNAL_TRANSFER_CREDIT": "Transferência interna (entrada)",
    "ESCROW_MONTHLY_FEE": "Tarifa mensal Escrow",
    "BILLING_RETENTION": "Retenção por inadimplência",
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


def wallet_onboarding_complete(account: EscrowAccount | None) -> bool:
    if account is None:
        return False
    if _is_mock_account(account):
        return True
    status = (account.asaas_kyc_status or "").upper()
    return status in {"APPROVED", "ACTIVE"}


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
            "onboarding_complete": False,
            "kyc_case": kyc_case,
            "message": "Conta LETTER ainda não aberta. Conclua a verificação para ativar sua carteira.",
        }

    if _is_mock_account(account):
        ensure_mock_banking(account)
        db.flush()

    complete = wallet_onboarding_complete(account)
    return {
        "has_subaccount": True,
        "onboarding_complete": complete,
        "kyc_case": kyc_case,
        "account": _account_payload(account),
        "banking": _banking_payload(account),
        "capabilities": _capabilities(account, db),
        "message": _wallet_message(account, db),
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


def _capabilities(account: EscrowAccount, db: Session | None = None) -> dict:
    approved = (account.asaas_kyc_status or "").upper() in {"APPROVED", "ACTIVE"} or _is_mock_account(account)
    billing_blocked = False
    if db is not None and account.escrow_enabled:
        from app.wallet_billing_service import get_billing_cycle

        cycle = get_billing_cycle(db, account)
        billing_blocked = bool(cycle and cycle.billing_blocked and Decimal(str(cycle.outstanding_amount or 0)) > 0)
    withdrawals = approved and not account.escrow_enabled and not billing_blocked
    return {
        "deposits_enabled": True,
        "withdrawals_enabled": withdrawals,
        "bill_payments_enabled": approved and not billing_blocked,
        "boleto_issuance_enabled": approved and not billing_blocked,
        "pix_key_enabled": approved,
        "escrow_locked": account.escrow_enabled,
        "billing_blocked": billing_blocked,
    }


def _wallet_message(account: EscrowAccount, db: Session | None = None) -> str:
    if db is not None:
        from app.wallet_billing_service import get_billing_cycle

        cycle = get_billing_cycle(db, account)
        if cycle and cycle.billing_blocked and Decimal(str(cycle.outstanding_amount or 0)) > 0:
            return (
                "Conta inadimplente — entradas retidas até quitar "
                f"R$ {money(Decimal(str(cycle.outstanding_amount)))} de mensalidade Escrow."
            )
    if account.escrow_enabled:
        return "Conta com Escrow — saques dependem da liberação operacional."
    status = (account.asaas_kyc_status or "PENDING").upper()
    if status in {"APPROVED", "ACTIVE"}:
        return "Carteira ativa — depósitos, saques e pagamentos disponíveis conforme saldo."
    if account.asaas_onboarding_url:
        return "Envie seus documentos pelo link de verificação LETTER para liberar saques e transferências."
    return "Documentação pendente — envie os documentos de verificação para liberar saques e transferências."


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
                    "type": "IDENTIFICATION",
                    "status": "APPROVED",
                    "onboarding_url": None,
                    "accepts_api_upload": False,
                },
                {
                    "id": "social-contract",
                    "title": "Contrato social",
                    "type": "SOCIAL_CONTRACT",
                    "status": "NOT_SENT",
                    "onboarding_url": None,
                    "accepts_api_upload": True,
                },
            ],
        }

    with subaccount_client(account) as client:
        payload = client.list_documents()
    data = payload.get("data") if isinstance(payload.get("data"), list) else payload if isinstance(payload, list) else []
    items = []
    for row in data:
        onboarding_url = row.get("onboardingUrl") or row.get("onboarding_url")
        if isinstance(onboarding_url, str):
            onboarding_url = onboarding_url.strip() or None
        else:
            onboarding_url = None
        doc_type = str(row.get("type") or row.get("documentType") or "CUSTOM").upper()
        title = str(row.get("title") or row.get("description") or doc_type or "Documento")
        if doc_type == "SOCIAL_CONTRACT" and "contrato" not in title.lower():
            title = "Contrato social"
        items.append(
            {
                "id": str(row.get("id") or row.get("type") or uuid4()),
                "title": title,
                "type": doc_type,
                "status": str(row.get("status") or "PENDING"),
                "onboarding_url": onboarding_url,
                # Com onboardingUrl o Asaas rejeita upload via API — só o link cadastro.io.
                "accepts_api_upload": not bool(onboarding_url),
            }
        )
        if onboarding_url and not account.asaas_onboarding_url:
            account.asaas_onboarding_url = str(onboarding_url)
    db.flush()
    return {"source": "ASAAS", "items": items}


async def upload_kyc_document(db: Session, account: EscrowAccount, document_id: str, file: UploadFile) -> dict:
    content = await file.read()
    if not content:
        raise HTTPException(status_code=422, detail="Arquivo vazio. Selecione o PDF novamente.")
    raw_name = (file.filename or "documento.pdf").strip() or "documento.pdf"
    # Asaas/multipart falha com nome de arquivo problemático em alguns browsers.
    safe_stem = "".join(ch if ch.isalnum() or ch in "-_." else "_" for ch in raw_name.rsplit(".", 1)[0])[:80] or "documento"
    ext = raw_name.rsplit(".", 1)[-1].lower() if "." in raw_name else "pdf"
    if ext not in {"pdf", "png", "jpg", "jpeg"}:
        ext = "pdf"
    filename = f"{safe_stem}.{ext}"
    content_type = (file.content_type or "").strip() or ("application/pdf" if ext == "pdf" else f"image/{ext}")
    lower_name = filename.lower()
    if not (lower_name.endswith((".pdf", ".png", ".jpg", ".jpeg")) or content_type.startswith(("application/pdf", "image/"))):
        raise HTTPException(status_code=422, detail="Envie PDF, PNG ou JPG do documento.")
    # Limite prático (~10 MB) para evitar timeout no Asaas
    if len(content) > 10 * 1024 * 1024:
        raise HTTPException(status_code=422, detail="Arquivo muito grande. Envie um PDF de até 10 MB.")

    if _is_mock_account(account):
        account.asaas_kyc_status = "UNDER_REVIEW"
        db.flush()
        return {"status": "UNDER_REVIEW", "message": f"Documento '{filename}' recebido em homologação (mock)."}

    with subaccount_client(account) as client:
        docs = list_kyc_documents(db, account)
        target = next((item for item in docs["items"] if item["id"] == document_id), None)
        if not target:
            raise HTTPException(status_code=404, detail="Grupo documental não encontrado")
        if target.get("onboarding_url"):
            raise HTTPException(
                status_code=422,
                detail="Este documento deve ser enviado pelo link oficial de verificação Asaas.",
            )
        document_type = str(target.get("type") or "CUSTOM").upper()
        # Contrato social e atas usam type do grupo; fallback sensato por título
        title_l = str(target.get("title") or "").lower()
        if document_type in {"", "CUSTOM"} and "contrato" in title_l:
            document_type = "SOCIAL_CONTRACT"
        result = client.upload_document(
            document_id,
            file_bytes=content,
            filename=filename,
            content_type=content_type,
            document_type=document_type,
        )
    account.asaas_kyc_status = "UNDER_REVIEW"
    db.flush()
    return {
        "status": str(result.get("status") or "UNDER_REVIEW"),
        "message": f"Documento '{raw_name}' enviado ao Asaas para análise.",
        "provider": result,
    }


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
    from app.wallet_billing_service import assert_withdrawals_allowed
    from app.wallet_pricing_service import customer_fee_for

    if account.escrow_enabled:
        raise HTTPException(status_code=422, detail="Subconta com Escrow — saque via fluxo operacional.")
    assert_withdrawals_allowed(db, account)
    if (account.asaas_kyc_status or "").upper() not in {"APPROVED", "ACTIVE"} and not _is_mock_account(account):
        raise HTTPException(status_code=422, detail="KYC Asaas pendente — saques bloqueados até aprovação.")
    value = money(amount)
    transfer_fee = customer_fee_for("TRANSFER", value)
    total_debit = money(value + transfer_fee)
    if Decimal(str(account.available_balance)) < total_debit:
        raise HTTPException(status_code=422, detail="Saldo insuficiente (valor + taxa de saque).")

    if _is_mock_account(account):
        account.available_balance = money(Decimal(str(account.available_balance)) - total_debit)
        event_id = f"mock_transfer_{uuid4().hex[:12]}"
        db.add(
            EscrowEvent(
                organization_id=account.organization_id,
                escrow_account_id=account.id,
                provider_event_id=event_id,
                event_type="TRANSFER_SENT",
                amount=float(value),
                payload_json=json.dumps({"pix_key": pix_key, "description": description, "fee": str(transfer_fee)}, ensure_ascii=False),
            )
        )
        if transfer_fee > 0:
            db.add(
                EscrowEvent(
                    organization_id=account.organization_id,
                    escrow_account_id=account.id,
                    provider_event_id=f"tx_fee_{event_id}",
                    event_type="PAYMENT_FEE",
                    amount=float(transfer_fee),
                    payload_json=json.dumps({"source_event": event_id}, ensure_ascii=False),
                )
            )
        db.flush()
        return {"provider": "MOCK", "transfer_id": event_id, "status": "DONE", "amount": str(value), "fee": str(transfer_fee)}

    with subaccount_client(account) as client:
        result = client.create_transfer(
            {
                "value": float(value),
                "pixAddressKey": pix_key,
                "description": description or "Saque LETTER",
            }
        )
    account.available_balance = money(Decimal(str(account.available_balance)) - total_debit)
    db.flush()
    return {
        "provider": "ASAAS",
        "transfer_id": str(result.get("id") or ""),
        "status": str(result.get("status") or "PENDING"),
        "amount": str(value),
        "fee": str(transfer_fee),
    }


def request_bill_payment(db: Session, account: EscrowAccount, *, barcode: str, amount: Decimal, description: str | None) -> dict:
    from app.wallet_billing_service import assert_withdrawals_allowed

    assert_withdrawals_allowed(db, account)
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


def _assert_boleto_issuance_allowed(db: Session, account: EscrowAccount) -> None:
    caps = _capabilities(account, db)
    if not caps.get("boleto_issuance_enabled"):
        if caps.get("billing_blocked"):
            raise HTTPException(status_code=422, detail="Emissão de boletos bloqueada por inadimplência da mensalidade Escrow.")
        raise HTTPException(status_code=422, detail="KYC Asaas pendente — emissão de boletos bloqueada.")


def _parse_due_date(raw: str) -> str:
    value = (raw or "").strip()
    try:
        return datetime.strptime(value[:10], "%Y-%m-%d").date().isoformat()
    except ValueError as exc:
        raise HTTPException(status_code=422, detail="Data de vencimento inválida. Use AAAA-MM-DD.") from exc


def _boleto_view_from_payment(
    payment: dict,
    *,
    provider: str,
    customer_name: str | None = None,
    customer_document: str | None = None,
    description: str | None = None,
) -> dict:
    return {
        "provider": provider,
        "payment_id": str(payment.get("id") or ""),
        "status": str(payment.get("status") or "PENDING"),
        "amount": str(payment.get("value") or payment.get("amount") or "0"),
        "due_date": str(payment.get("dueDate") or "") or None,
        "description": description or (str(payment.get("description") or "") or None),
        "customer_name": customer_name,
        "customer_document": customer_document,
        "invoice_url": str(payment.get("invoiceUrl") or "") or None,
        "bank_slip_url": str(payment.get("bankSlipUrl") or payment.get("invoiceUrl") or "") or None,
        "identification_field": str(payment.get("identificationField") or "") or None,
        "barcode": str(payment.get("barCode") or payment.get("nossoNumero") or "") or None,
    }


def issue_wallet_boleto(
    db: Session,
    account: EscrowAccount,
    *,
    customer_name: str,
    customer_document: str,
    amount: Decimal,
    due_date: str,
    description: str | None = None,
    customer_email: str | None = None,
    customer_phone: str | None = None,
) -> dict:
    _assert_boleto_issuance_allowed(db, account)
    value = money(amount)
    due = _parse_due_date(due_date)
    document = _digits(customer_document)
    if len(document) not in {11, 14}:
        raise HTTPException(status_code=422, detail="Informe CPF (11 dígitos) ou CNPJ (14 dígitos) do pagador.")
    name = customer_name.strip()
    if len(name) < 3:
        raise HTTPException(status_code=422, detail="Informe o nome do pagador.")
    desc = (description or "Cobrança LETTER BANK").strip()[:200]

    if _is_mock_account(account):
        payment_id = f"mock_boleto_{uuid4().hex[:12]}"
        digitable = f"23793{uuid4().hex[:10].upper()}{document[-8:]}{int(value * 100):011d}"
        payment = {
            "id": payment_id,
            "status": "PENDING",
            "value": float(value),
            "dueDate": due,
            "description": desc,
            "invoiceUrl": f"https://sandbox.asaas.com/i/{payment_id}",
            "bankSlipUrl": f"https://sandbox.asaas.com/b/pdf/{payment_id}",
            "identificationField": digitable,
            "barCode": digitable,
        }
        db.add(
            EscrowEvent(
                organization_id=account.organization_id,
                escrow_account_id=account.id,
                provider_event_id=payment_id,
                event_type="BOLETO_ISSUED",
                amount=float(value),
                payload_json=json.dumps(
                    {
                        "customer_name": name,
                        "customer_document": document,
                        "due_date": due,
                        "description": desc,
                        "invoice_url": payment["invoiceUrl"],
                    },
                    ensure_ascii=False,
                ),
            )
        )
        db.flush()
        return _boleto_view_from_payment(
            payment,
            provider="MOCK",
            customer_name=name,
            customer_document=document,
            description=desc,
        )

    with subaccount_client(account) as client:
        customer_payload: dict = {
            "name": name,
            "cpfCnpj": document,
            "notificationDisabled": True,
            "externalReference": f"boleto:{account.id}:{uuid4().hex[:8]}",
        }
        if customer_email and customer_email.strip():
            customer_payload["email"] = customer_email.strip()
        phone = _digits(customer_phone)
        if phone:
            customer_payload["mobilePhone"] = phone
        customer = client.create_customer(customer_payload)
        customer_id = str(customer.get("id") or "").strip()
        if not customer_id:
            raise HTTPException(status_code=502, detail="Asaas não retornou o cliente do boleto.")

        payment = client.create_payment(
            {
                "customer": customer_id,
                "billingType": "BOLETO",
                "value": float(value),
                "dueDate": due,
                "description": desc,
                "externalReference": f"wallet-boleto:{account.id}:{uuid4().hex[:10]}",
            }
        )

    db.add(
        EscrowEvent(
            organization_id=account.organization_id,
            escrow_account_id=account.id,
            provider_event_id=str(payment.get("id") or f"boleto_{uuid4().hex[:12]}"),
            event_type="BOLETO_ISSUED",
            amount=float(value),
            payload_json=json.dumps(
                {
                    "customer_name": name,
                    "customer_document": document,
                    "due_date": due,
                    "description": desc,
                    "invoice_url": payment.get("invoiceUrl"),
                    "bank_slip_url": payment.get("bankSlipUrl"),
                },
                ensure_ascii=False,
            ),
        )
    )
    db.flush()
    return _boleto_view_from_payment(
        payment,
        provider="ASAAS",
        customer_name=name,
        customer_document=document,
        description=desc,
    )


def list_wallet_boletos(db: Session, account: EscrowAccount, *, limit: int = 20) -> dict:
    if _is_mock_account(account):
        events = list(
            db.scalars(
                select(EscrowEvent)
                .where(
                    EscrowEvent.escrow_account_id == account.id,
                    EscrowEvent.event_type == "BOLETO_ISSUED",
                )
                .order_by(EscrowEvent.processed_at.desc())
                .limit(limit)
            )
        )
        items = []
        for event in events:
            try:
                meta = json.loads(event.payload_json or "{}")
            except Exception:
                meta = {}
            items.append(
                {
                    "provider": "MOCK",
                    "payment_id": event.provider_event_id,
                    "status": "PENDING",
                    "amount": str(event.amount),
                    "due_date": meta.get("due_date"),
                    "description": meta.get("description"),
                    "customer_name": meta.get("customer_name"),
                    "customer_document": meta.get("customer_document"),
                    "invoice_url": meta.get("invoice_url"),
                    "bank_slip_url": meta.get("invoice_url"),
                    "identification_field": None,
                    "barcode": None,
                }
            )
        return {"items": items}

    with subaccount_client(account) as client:
        payload = client.list_payments(limit=limit, billing_type="BOLETO")
    data = payload.get("data") if isinstance(payload, dict) else None
    rows = data if isinstance(data, list) else []
    items = [_boleto_view_from_payment(row, provider="ASAAS") for row in rows if isinstance(row, dict)]
    return {"items": items}


def _resolve_webhook_account_id(payload: dict, payment: dict, transfer: dict) -> str | None:
    account = payload.get("account")
    if isinstance(account, dict):
        account_id = str(account.get("id") or "").strip()
        if account_id:
            return account_id
    for candidate in (
        payment.get("accountId"),
        transfer.get("accountId"),
        payload.get("accountId"),
        payload.get("account") if isinstance(payload.get("account"), str) else None,
    ):
        if candidate:
            return str(candidate).strip()
    return None


def _account_status_webhook(event: str) -> bool:
    return event in {
        "ACCOUNT_STATUS_UPDATED",
        "ACCOUNT_DOCUMENTATION_APPROVED",
        "ACCOUNT_DOCUMENTATION_REJECTED",
    } or event.startswith("ACCOUNT_STATUS_")


def handle_asaas_webhook(db: Session, payload: dict) -> dict:
    event = str(payload.get("event") or payload.get("type") or "UNKNOWN")
    payment = payload.get("payment") if isinstance(payload.get("payment"), dict) else {}
    transfer = payload.get("transfer") if isinstance(payload.get("transfer"), dict) else {}
    account_ref = _resolve_webhook_account_id(payload, payment, transfer)

    account = None
    if account_ref:
        account = db.scalar(
            select(EscrowAccount).where(
                (EscrowAccount.asaas_account_id == account_ref)
                | (EscrowAccount.external_account_id == account_ref)
            )
        )

    event_id = str(payload.get("id") or payload.get("event") or uuid4())
    processed = False
    lss_subscription_id = None
    split_result = None

    from app.lss_billing_service import handle_lss_payment_webhook
    from app.asaas_split_service import PAYMENT_SPLIT_DONE, handle_payment_split_done

    if event == PAYMENT_SPLIT_DONE:
        split_result = handle_payment_split_done(db, payload)
        processed = bool(split_result.get("processed"))

    lss_item = handle_lss_payment_webhook(db, event, payment)
    if lss_item:
        processed = True
        lss_subscription_id = lss_item.id

    if account and event in {"PAYMENT_RECEIVED", "PAYMENT_CONFIRMED"}:
        amount = Decimal(str(payment.get("value") or payment.get("netValue") or 0))
        if amount > 0:
            org_user = db.scalar(select(User).where(User.id == account.user_id)) if account.user_id else None
            actor = org_user or db.scalar(select(User).where(User.organization_id == account.organization_id).limit(1))
            if actor:
                from app.wallet_billing_service import credit_escrow_incoming

                payment_event_id = str(payment.get("id") or payload.get("id") or event_id)
                _, processed = credit_escrow_incoming(
                    db,
                    actor,
                    account,
                    payment_event_id,
                    "PAYMENT_RECEIVED",
                    amount,
                    payload,
                )
                ensure_chart(db, actor)

    if account and _account_status_webhook(event):
        account_status = payload.get("accountStatus") if isinstance(payload.get("accountStatus"), dict) else {}
        if account_status:
            general = str(account_status.get("general") or "").upper()
            documentation = str(account_status.get("documentation") or "").upper()
            if general == "APPROVED" or documentation == "APPROVED":
                account.asaas_kyc_status = "APPROVED"
            elif general == "REJECTED" or documentation == "REJECTED":
                account.asaas_kyc_status = "REJECTED"
            elif general in {"AWAITING_APPROVAL", "PENDING"}:
                account.asaas_kyc_status = general
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

    return {
        "event": event,
        "processed": processed,
        "account_id": account.id if account else None,
        "lss_subscription_id": lss_subscription_id,
        "split": split_result,
    }
