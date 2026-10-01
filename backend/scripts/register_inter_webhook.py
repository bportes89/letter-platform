"""Cadastra URL de webhook de cobrança no Banco Inter (rodar no PC com .env + cert)."""

from __future__ import annotations

import os
import sys

import httpx

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from app.core.config import settings
from app.inter_client import InterClient


def main() -> None:
    webhook = (os.environ.get("LETTER_INTER_WEBHOOK_URL") or "").strip()
    if not webhook:
        public = (settings.api_public_url or "").rstrip("/")
        webhook = f"{public}/webhooks/inter" if public else ""
    if not webhook:
        raise SystemExit("Defina LETTER_API_PUBLIC_URL ou LETTER_INTER_WEBHOOK_URL")

    client = InterClient()
    token = client.access_token()
    headers = {
        "Authorization": f"Bearer {token}",
        "Content-Type": "application/json",
        "x-conta-corrente": (settings.inter_conta_corrente or "").strip(),
    }
    cert = (settings.inter_cert_path, settings.inter_key_path)
    base = settings.inter_base_url.rstrip("/")
    with httpx.Client(cert=cert, verify=False, timeout=30) as h:
        r = h.put(f"{base}/cobranca/v3/cobrancas/webhook", json={"webhookUrl": webhook}, headers=headers)
    print(r.status_code, r.text)
    if r.status_code >= 400:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
