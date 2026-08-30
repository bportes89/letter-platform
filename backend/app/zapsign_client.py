"""Cliente HTTP mínimo para a API ZapSign v1."""

from __future__ import annotations

import httpx
from fastapi import HTTPException

from app.core.config import settings


class ZapSignClient:
    def __init__(
        self,
        *,
        api_token: str | None = None,
        base_url: str | None = None,
        timeout: float | None = None,
    ) -> None:
        token = (api_token or settings.zapsign_api_token or "").strip()
        if not token:
            raise HTTPException(status_code=503, detail="Integração ZapSign não configurada (API Token ausente).")
        self.api_token = token
        self.base_url = (base_url or settings.zapsign_base_url).rstrip("/")
        self.timeout = timeout or settings.integration_http_timeout_seconds
        self._client = httpx.Client(
            base_url=self.base_url,
            timeout=self.timeout,
            headers={
                "Authorization": f"Bearer {token}",
                "Content-Type": "application/json",
                "User-Agent": "LETTER-Platform/0.24",
            },
        )

    def close(self) -> None:
        self._client.close()

    def __enter__(self) -> ZapSignClient:
        return self

    def __exit__(self, *args) -> None:
        self.close()

    def request(self, method: str, path: str, *, json: dict | None = None) -> dict:
        try:
            response = self._client.request(method, path, json=json)
        except httpx.HTTPError as exc:
            raise HTTPException(status_code=502, detail=f"ZapSign indisponível: {exc}") from exc
        if response.status_code == 401:
            raise HTTPException(status_code=502, detail="ZapSign recusou o API Token (401). Verifique ambiente Sandbox vs Produção.")
        if response.status_code >= 400:
            detail = response.text[:400]
            try:
                body = response.json()
                for key in ("detail", "message", "error"):
                    if isinstance(body.get(key), str) and body[key]:
                        detail = body[key]
                        break
            except Exception:
                pass
            raise HTTPException(status_code=502, detail=f"ZapSign retornou erro {response.status_code}: {detail}")
        if not response.content:
            return {}
        return response.json()

    def list_docs(self, *, page: int = 1) -> dict:
        return self.request("GET", f"/docs/?page={page}")

    def get_doc(self, token: str) -> dict:
        return self.request("GET", f"/docs/{token}/")

    def create_doc_from_pdf(
        self,
        *,
        name: str,
        base64_pdf: str,
        signers: list[dict],
        external_id: str = "",
        lang: str = "pt-br",
    ) -> dict:
        return self.request(
            "POST",
            "/docs/",
            json={
                "name": name,
                "base64_pdf": base64_pdf,
                "signers": signers,
                "external_id": external_id,
                "lang": lang,
            },
        )
