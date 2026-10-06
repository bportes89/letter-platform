"""Cron: consulta PIX Inter em PROCESSING / AWAITING_BALANCE (fallback ao webhook)."""

from __future__ import annotations

import os
import sys

import httpx

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from app.core.config import settings


def main() -> None:
    base = (settings.api_public_url or os.environ.get("LETTER_API_PUBLIC_URL") or "http://127.0.0.1:8000/api/v1").rstrip("/")
    url = f"{base}/system/cron/inter-payout-poll"
    secret = (settings.cron_secret or os.environ.get("LETTER_CRON_SECRET") or "").strip()
    headers = {"X-Cron-Secret": secret} if secret else {}
    with httpx.Client(timeout=120) as client:
        resp = client.post(url, headers=headers)
    print(resp.status_code, resp.text)
    if resp.status_code >= 400:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
