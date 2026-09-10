"""Cliente HTTP Banco Inter — OAuth mTLS + cobrança v3 (boleto/PIX)."""

from __future__ import annotations

import base64
import time
from datetime import date, timedelta
from decimal import Decimal
from typing import Any

import httpx
from fastapi import HTTPException

from app.core.config import settings
from app.inter_common import INTER_SCOPE, inter_base_url, inter_configured, inter_vencimento_dias
from app.services import money

_token_cache: dict[str, Any] = {"access_token": None, "expires_at": 0.0}


class InterClient:
    def __init__(self) -> None:
        if not inter_configured():
            raise HTTPException(status_code=503, detail="Banco Inter não configurado")
        self.base = inter_base_url()
        self.cert = (settings.inter_cert_path, settings.inter_key_path)
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
                    "client_id": settings.inter_client_id,
                    "client_secret": settings.inter_client_secret,
                    "grant_type": "client_credentials",
                    "scope": INTER_SCOPE,
                },
                headers={"Content-Type": "application/x-www-form-urlencoded"},
            )
        if resp.status_code >= 400:
            raise HTTPException(status_code=502, detail=f"Inter OAuth falhou ({resp.status_code})")
        data = resp.json() if resp.content else {}
        token = data.get("access_token")
        if not token:
            raise HTTPException(status_code=502, detail="Inter OAuth sem access_token")
        expires_in = int(data.get("expires_in") or 300)
        _token_cache["access_token"] = token
        _token_cache["expires_at"] = now + expires_in
        return str(token)

    def create_cobranca(
        self,
        *,
        seu_numero: str,
        valor: Decimal,
        pagador: dict[str, Any],
        mensagem_linhas: list[str] | None = None,
    ) -> dict:
        token = self.access_token()
        vencimento = (date.today() + timedelta(days=inter_vencimento_dias())).isoformat()
        linhas = [str(x)[:78] for x in (mensagem_linhas or []) if str(x).strip()][:4]
        payload = {
            "seuNumero": seu_numero[:15],
            "valorNominal": float(money(valor)),
            "valorAbatimento": 0,
            "dataVencimento": vencimento,
            "numDiasAgenda": 60,
            "pagador": pagador,
            "formasRecebimento": ["BOLETO", "PIX"],
        }
        if linhas:
            payload["mensagem"] = {"linha%d" % (i + 1): line for i, line in enumerate(linhas)}
        headers = {
            "Authorization": f"Bearer {token}",
            "Content-Type": "application/json",
            "x-conta-corrente": (settings.inter_conta_corrente or "").strip(),
        }
        with self._client() as client:
            resp = client.post(f"{self.base}/cobranca/v3/cobrancas", json=payload, headers=headers)
        body = resp.json() if resp.content else {}
        if resp.status_code >= 400:
            detail = body.get("detail") or body.get("title") or resp.text[:300]
            # Duplicata: tenta extrair UUID da cobrança existente
            import re

            match = re.search(
                r"[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}",
                str(detail),
                re.I,
            )
            if match:
                return {"codigoSolicitacao": match.group(0), "duplicated": True}
            raise HTTPException(status_code=502, detail=f"Inter cobrança falhou: {detail}")
        codigo = body.get("codigoSolicitacao")
        if not codigo:
            raise HTTPException(status_code=502, detail="Inter cobrança sem codigoSolicitacao")
        return {"codigoSolicitacao": str(codigo), "duplicated": False, "raw": body}

    def download_pdf_base64(self, codigo_solicitacao: str, *, attempts: int = 4) -> str:
        token = self.access_token()
        headers = {
            "Authorization": f"Bearer {token}",
            "x-conta-corrente": (settings.inter_conta_corrente or "").strip(),
        }
        last_detail = ""
        with self._client() as client:
            for attempt in range(max(1, attempts)):
                resp = client.get(
                    f"{self.base}/cobranca/v3/cobrancas/{codigo_solicitacao}/pdf",
                    headers=headers,
                )
                if resp.status_code < 400:
                    data = resp.json() if resp.headers.get("content-type", "").startswith("application/json") else {}
                    pdf = data.get("pdf") if isinstance(data, dict) else None
                    if pdf:
                        return str(pdf)
                    # alguns ambientes devolvem PDF binário
                    if resp.content and resp.content[:4] == b"%PDF":
                        return base64.b64encode(resp.content).decode("ascii")
                    last_detail = "resposta sem PDF"
                else:
                    last_detail = resp.text[:200]
                time.sleep(0.6 * (attempt + 1))
        raise HTTPException(status_code=502, detail=f"Inter PDF indisponível: {last_detail}")
