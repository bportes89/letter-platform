"""Cadastra webhook banking pix-pagamento no Banco Inter (app pagamentos)."""

from __future__ import annotations

import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from app.core.config import settings
from app.inter_payout_client import InterPayoutClient


def main() -> None:
    webhook = (os.environ.get("LETTER_INTER_PAYOUT_WEBHOOK_URL") or "").strip()
    if not webhook:
        public = (settings.api_public_url or "").rstrip("/")
        webhook = f"{public}/webhooks/inter-payout" if public else ""
    if not webhook:
        raise SystemExit("Defina LETTER_API_PUBLIC_URL ou LETTER_INTER_PAYOUT_WEBHOOK_URL")

    client = InterPayoutClient()
    body = client.register_pix_payment_webhook(webhook)
    print("OK", body)


if __name__ == "__main__":
    main()
