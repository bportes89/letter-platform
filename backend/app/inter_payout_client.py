"""Cliente HTTP — OAuth mTLS + Pix pagamento (banking/v2)."""

from __future__ import annotations

import time
from datetime import date
from decimal import Decimal
from typing import Any

import httpx
from fastapi import HTTPException

from app.core.config import settings
from app.inter_payout_common import (
    INTER_PAYOUT_SCOPE,
    inter_payout_base_url,
    inter_payout_configured,
    inter_payout_conta,
)
from app.services import money

_token_cache: dict[str, Any] = {"access_token": None, "expires_at": 0.0}


class InterPayoutClient:
    def __init__(self) -> None:
        if not inter_payout_configured():
            raise HTTPException(status_code=503, detail="Inter pagamentos (PIX saída) não configurado")
        self.base = inter_payout_base_url()
        self.cert = (settings.inter_payout_cert_path, settings.inter_payout_key_path)
        self.timeout = float(settings.integration_http_timeout_seconds or 15)

    def _client(self) -> httpx.Client:
        return httpx.Client(cert=self.cert, verify=False, timeout=self.timeout)

    def access_token(self) -> str:
        now = time.time()
        cached = _token_cache.get("access_token")
        expires = float(_token_cache.get("expires_at") or 0)
        if cached and expires > now + 30:
            return str(cached)
        with self._client() as client:
            resp = client.post(
                f"{self.base}/oauth/v2/token",
                data={
                    "client_id": settings.inter_payout_client_id,
                    "client_secret": settings.inter_payout_client_secret,
                    "grant_type": "client_credentials",
                    "scope": INTER_PAYOUT_SCOPE,
                },
                headers={"Content-Type": "application/x-www-form-urlencoded"},
            )
        if resp.status_code >= 400:
            raise HTTPException(status_code=502, detail=f"Inter pagamentos OAuth falhou ({resp.status_code})")
        data = resp.json() if resp.content else {}
        token = data.get("access_token")
        if not token:
            raise HTTPException(status_code=502, detail="Inter pagamentos OAuth sem access_token")
        expires_in = int(data.get("expires_in") or 300)
        _token_cache["access_token"] = token
        _token_cache["expires_at"] = now + expires_in
        return str(token)

    def _headers(self, *, idempotency: str | None = None) -> dict[str, str]:
        headers = {
            "Authorization": f"Bearer {self.access_token()}",
            "Content-Type": "application/json",
            "x-conta-corrente": inter_payout_conta(),
        }
        if idempotency:
            headers["x-id-idempotente"] = idempotency[:72]
        return headers

    def saldo(self) -> Decimal:
        with self._client() as client:
            resp = client.get(f"{self.base}/banking/v2/saldo", headers=self._headers())
        if resp.status_code >= 400:
            raise HTTPException(status_code=502, detail=f"Inter saldo falhou ({resp.status_code})")
        body = resp.json() if resp.content else {}
        disponivel = body.get("disponivel") or body.get("saldo") or body.get("valor")
        return money(Decimal(str(disponivel or 0)))

    def incluir_pix(
        self,
        *,
        valor: Decimal,
        chave_pix: str,
        descricao: str,
        idempotency_key: str,
    ) -> dict:
        payload = {
            "valor": float(money(valor)),
            "dataPagamento": date.today().isoformat(),
            "descricao": (descricao or "Pagamento LETTER")[:140],
            "destinatario": {
                "tipo": "CHAVE",
                "chave": chave_pix.strip(),
            },
        }
        with self._client() as client:
            resp = client.post(
                f"{self.base}/banking/v2/pix",
                json=payload,
                headers=self._headers(idempotency=idempotency_key),
            )
        body = resp.json() if resp.content else {}
        if resp.status_code >= 400:
            detail = body.get("detail") or body.get("title") or body.get("message") or resp.text[:400]
            raise HTTPException(status_code=502, detail=f"Inter PIX pagamento falhou: {detail}")
        return body if isinstance(body, dict) else {"raw": body}

    def consultar_pix(self, codigo_solicitacao: str) -> dict:
        codigo = (codigo_solicitacao or "").strip()
        with self._client() as client:
            resp = client.get(
                f"{self.base}/banking/v2/pix/{codigo}",
                headers=self._headers(),
            )
        body = resp.json() if resp.content else {}
        if resp.status_code >= 400:
            raise HTTPException(status_code=502, detail=f"Inter consulta PIX falhou ({resp.status_code})")
        return body if isinstance(body, dict) else {"raw": body}
