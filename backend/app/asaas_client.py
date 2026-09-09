"""Cliente HTTP mínimo para a API Asaas v3."""

from __future__ import annotations

import httpx
from fastapi import HTTPException

from app.core.config import settings


class AsaasClient:
    def __init__(
        self,
        *,
        api_key: str | None = None,
        base_url: str | None = None,
        timeout: float | None = None,
    ) -> None:
        key = (api_key or settings.asaas_api_key or "").strip()
        if not key:
            raise HTTPException(status_code=503, detail="Integração Asaas não configurada (API Key ausente).")
        self.api_key = key
        self.base_url = (base_url or settings.asaas_base_url).rstrip("/")
        self.timeout = timeout or settings.integration_http_timeout_seconds
        self._client = httpx.Client(
            base_url=self.base_url,
            timeout=self.timeout,
            headers={
                "access_token": self.api_key,
                "User-Agent": "LETTER-Platform/0.24",
            },
        )

    def close(self) -> None:
        self._client.close()

    def __enter__(self) -> AsaasClient:
        return self

    def __exit__(self, *args) -> None:
        self.close()

    def request(self, method: str, path: str, *, json: dict | None = None, params: dict | None = None, content: bytes | None = None, headers: dict | None = None) -> dict:
        req_headers = dict(headers or {})
        # Só força JSON quando há body JSON — multipart de upload não pode herdar application/json.
        if json is not None and "Content-Type" not in req_headers:
            req_headers["Content-Type"] = "application/json"
        try:
            response = self._client.request(method, path, json=json, params=params, content=content, headers=req_headers or None)
        except httpx.HTTPError as exc:
            raise HTTPException(status_code=502, detail=f"Asaas indisponível: {exc}") from exc
        if response.status_code == 401:
            raise HTTPException(status_code=502, detail="Asaas recusou a API Key (401). Verifique ambiente Sandbox vs Produção.")
        if response.status_code >= 400:
            detail = response.text[:400]
            try:
                body = response.json()
                errors = body.get("errors")
                if isinstance(errors, list) and errors:
                    detail = errors[0].get("description") or errors[0].get("code") or detail
            except Exception:
                pass
            raise HTTPException(status_code=502, detail=f"Asaas retornou erro {response.status_code}: {detail}")
        if not response.content:
            return {}
        return response.json()

    def get_balance(self) -> dict:
        return self.request("GET", "/finance/balance")

    def list_wallets(self) -> dict:
        return self.request("GET", "/wallets/")

    def configure_default_escrow(self, *, enabled: bool, days_to_expire: int, fee_payer_subaccount: bool) -> dict:
        return self.request(
            "POST",
            "/accounts/escrow",
            json={
                "enabled": enabled,
                "isFeePayer": fee_payer_subaccount,
                "daysToExpire": days_to_expire,
            },
        )

    def configure_subaccount_escrow(
        self,
        account_id: str,
        *,
        enabled: bool,
        days_to_expire: int,
        fee_payer_subaccount: bool,
    ) -> dict:
        return self.request(
            "POST",
            f"/accounts/{account_id}/escrow",
            json={
                "enabled": enabled,
                "isFeePayer": fee_payer_subaccount,
                "daysToExpire": days_to_expire,
            },
        )

    def create_subaccount(self, payload: dict) -> dict:
        return self.request("POST", "/accounts", json=payload)

    def get_account(self, account_id: str) -> dict:
        return self.request("GET", f"/accounts/{account_id}")

    def get_commercial_info(self) -> dict:
        return self.request("GET", "/myAccount/commercialInfo/")

    def get_account_number(self) -> dict:
        return self.request("GET", "/myAccount/accountNumber")

    def list_documents(self) -> dict:
        return self.request("GET", "/myAccount/documents")

    def upload_document(
        self,
        document_group_id: str,
        *,
        file_bytes: bytes,
        filename: str,
        content_type: str,
        document_type: str,
    ) -> dict:
        """Asaas exige multipart/form-data com documentFile + type (ex.: SOCIAL_CONTRACT)."""
        mime = (content_type or "application/pdf").split(";")[0].strip() or "application/pdf"
        doc_type = (document_type or "CUSTOM").strip().upper()
        # Upload de PDF costuma passar de 10s; timeout dedicado evita "Enviando…" eterno no front.
        upload_timeout = max(float(self.timeout), 60.0)
        try:
            response = self._client.post(
                f"/myAccount/documents/{document_group_id}",
                data={"type": doc_type},
                files={"documentFile": (filename or "documento.pdf", file_bytes, mime)},
                timeout=upload_timeout,
            )
        except httpx.TimeoutException as exc:
            raise HTTPException(
                status_code=504,
                detail="Tempo esgotado ao enviar o PDF ao Asaas. Tente um arquivo menor (até 5 MB) ou use o link oficial de verificação.",
            ) from exc
        except httpx.HTTPError as exc:
            raise HTTPException(status_code=502, detail=f"Asaas indisponível: {exc}") from exc
        if response.status_code == 401:
            raise HTTPException(status_code=502, detail="Asaas recusou a API Key (401). Verifique ambiente Sandbox vs Produção.")
        if response.status_code >= 400:
            detail = response.text[:400]
            try:
                body = response.json()
                errors = body.get("errors")
                if isinstance(errors, list) and errors:
                    detail = errors[0].get("description") or errors[0].get("code") or detail
            except Exception:
                pass
            raise HTTPException(status_code=502, detail=f"Asaas retornou erro {response.status_code}: {detail}")
        if not response.content:
            return {}
        return response.json()

    def list_financial_transactions(self, *, offset: int = 0, limit: int = 50) -> dict:
        return self.request("GET", "/financialTransactions", params={"offset": offset, "limit": limit})

    def list_pix_keys(self) -> dict:
        return self.request("GET", "/pix/addressKeys")

    def create_pix_key(self, *, key_type: str = "EVP") -> dict:
        return self.request("POST", "/pix/addressKeys", json={"type": key_type})

    def get_pix_qrcode(self, key: str) -> dict:
        return self.request("GET", f"/pix/addressKeys/{key}/qrCode")

    def create_transfer(self, payload: dict) -> dict:
        return self.request("POST", "/transfers", json=payload)

    def create_bill_payment(self, payload: dict) -> dict:
        return self.request("POST", "/billPayments", json=payload)

    def create_customer(self, payload: dict) -> dict:
        return self.request("POST", "/customers", json=payload)

    def create_subscription(self, payload: dict) -> dict:
        return self.request("POST", "/subscriptions", json=payload)

    def get_subscription(self, subscription_id: str) -> dict:
        return self.request("GET", f"/subscriptions/{subscription_id}")

    def delete_subscription(self, subscription_id: str) -> dict:
        return self.request("DELETE", f"/subscriptions/{subscription_id}")

    def list_subscription_payments(self, subscription_id: str, *, limit: int = 5) -> dict:
        return self.request("GET", f"/subscriptions/{subscription_id}/payments", params={"limit": limit})

    def get_payment(self, payment_id: str) -> dict:
        return self.request("GET", f"/payments/{payment_id}")

    def create_payment(self, payload: dict) -> dict:
        return self.request("POST", "/payments", json=payload)

    def list_payments(self, *, offset: int = 0, limit: int = 20, billing_type: str | None = None) -> dict:
        params: dict = {"offset": offset, "limit": limit}
        if billing_type:
            params["billingType"] = billing_type
        return self.request("GET", "/payments", params=params)

    def update_payment(self, payment_id: str, payload: dict) -> dict:
        return self.request("PUT", f"/payments/{payment_id}", json=payload)
