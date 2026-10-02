"""Grava cert/key mTLS do Inter a partir de env (Render free, sem disco/Shell)."""

from __future__ import annotations

import base64
import os
from pathlib import Path


def _materialize(prefix: str, label: str) -> None:
    cert_b64 = (os.environ.get(f"{prefix}_CERT_BASE64") or "").strip()
    key_b64 = (os.environ.get(f"{prefix}_KEY_BASE64") or "").strip()
    cert_path = (os.environ.get(f"{prefix}_CERT_PATH") or "").strip()
    key_path = (os.environ.get(f"{prefix}_KEY_PATH") or "").strip()

    if not cert_b64 and not key_b64:
        return

    if not cert_b64 or not key_b64:
        raise SystemExit(f"[letter] {prefix}_CERT_BASE64 e {prefix}_KEY_BASE64 devem ser definidos juntos")
    if not cert_path or not key_path:
        raise SystemExit(f"[letter] {prefix}_CERT_PATH e {prefix}_KEY_PATH são obrigatórios com BASE64")

    cp = Path(cert_path)
    kp = Path(key_path)
    cp.parent.mkdir(parents=True, exist_ok=True)
    kp.parent.mkdir(parents=True, exist_ok=True)
    cp.write_bytes(base64.b64decode(cert_b64))
    kp.write_bytes(base64.b64decode(key_b64))
    print(f"[letter] {label} mTLS certs materialized at {cp} and {kp}")


def main() -> None:
    _materialize("LETTER_INTER", "Inter cobrança")
    _materialize("LETTER_INTER_PAYOUT", "Inter pagamentos PIX")


if __name__ == "__main__":
    main()
