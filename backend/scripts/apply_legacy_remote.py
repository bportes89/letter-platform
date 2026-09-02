"""Upload bundle.json para dry-run/apply na API remota com timeout longo."""

from __future__ import annotations

import argparse
import json
import os
import sys
import time
from pathlib import Path

import httpx

DEFAULT_API = "https://letter-api-fobc.onrender.com/api/v1"
DEFAULT_BUNDLE = Path(__file__).resolve().parents[2] / "legacy" / "export" / "bundle.json"
DEFAULT_OUT = Path(__file__).resolve().parents[2] / "artifacts"


def login(client: httpx.Client, base_url: str, email: str, password: str) -> str:
    response = client.post(
        f"{base_url}/auth/login",
        json={"email": email, "password": password},
    )
    response.raise_for_status()
    token = response.json().get("access_token")
    if not token:
        raise RuntimeError("Login nao retornou access_token")
    return token


def main() -> int:
    parser = argparse.ArgumentParser(description="Apply remoto da migracao legada")
    parser.add_argument("--api-base", default=os.environ.get("LETTER_API_BASE", DEFAULT_API))
    parser.add_argument("--bundle", type=Path, default=DEFAULT_BUNDLE)
    parser.add_argument("--email", default=os.environ.get("LETTER_ADMIN_EMAIL", "admin@letter.com.br"))
    parser.add_argument("--password", default=os.environ.get("LETTER_ADMIN_PASSWORD", ""))
    parser.add_argument("--token", default=os.environ.get("LETTER_ACCESS_TOKEN", ""))
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--timeout", type=int, default=3600)
    parser.add_argument("--retries", type=int, default=3)
    args = parser.parse_args()

    if not args.bundle.is_file():
        print(f"Bundle nao encontrado: {args.bundle}", file=sys.stderr)
        return 1

    password = args.password
    if not args.token and not password:
        password = os.environ.get("LETTER_DEMO_PASSWORD", "Letter@123")

    bundle_raw = args.bundle.read_text(encoding="utf-8")
    bundle = json.loads(bundle_raw)
    size_mb = args.bundle.stat().st_size / (1024 * 1024)
    print(f"Bundle: {args.bundle} ({size_mb:.2f} MB)")
    print(f"legacy_source: {bundle.get('legacy_source')}")
    entities = bundle.get("entities") or {}
    for name in sorted(entities):
        value = entities[name]
        if isinstance(value, list):
            print(f"  - {name}: {len(value)}")

    endpoint = "dry-run" if args.dry_run else "apply"
    url = f"{args.api_base.rstrip('/')}/admin/migration/{endpoint}"
    print(f"Destino: POST {url} (timeout {args.timeout}s)")

    timeout = httpx.Timeout(args.timeout, connect=60.0)
    with httpx.Client(timeout=timeout) as client:
        token = args.token or login(client, args.api_base, args.email, password)
        headers = {"Authorization": f"Bearer {token}"}

        last_error: Exception | None = None
        for attempt in range(1, args.retries + 1):
            started = time.perf_counter()
            print(f"Tentativa {attempt}/{args.retries}...")
            try:
                response = client.post(
                    url,
                    headers={**headers, "Content-Type": "application/json; charset=utf-8"},
                    content=bundle_raw.encode("utf-8"),
                )
                elapsed = time.perf_counter() - started
                print(f"Resposta em {elapsed:.1f}s (HTTP {response.status_code})")
                if response.status_code >= 400:
                    print(response.text[:4000], file=sys.stderr)
                    response.raise_for_status()
                payload = response.json()
                break
            except Exception as exc:  # noqa: BLE001
                last_error = exc
                if attempt == args.retries:
                    raise
                wait = 10 * attempt
                print(f"Falha: {exc}. Aguardando {wait}s...")
                time.sleep(wait)
        else:
            raise last_error or RuntimeError("Falha desconhecida")

    DEFAULT_OUT.mkdir(parents=True, exist_ok=True)
    stamp = time.strftime("%Y%m%d-%H%M%S")
    out_file = DEFAULT_OUT / f"migration-{endpoint}-{stamp}.json"
    out_file.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"Salvo em: {out_file}")

    summary = payload.get("summary") or {}
    print(f"Run ID:  {payload.get('id')}")
    print(f"Status:  {payload.get('status')}")
    print(f"Modo:    {payload.get('mode')}")
    if payload.get("error_message"):
        print(f"Erro:    {payload['error_message']}")
    if "ready" in summary:
        print(f"Pronto:  {summary['ready']}")
    if summary.get("created"):
        print("Criados:", summary["created"])
    if summary.get("reused"):
        print("Reutilizados:", summary["reused"])
    if summary.get("skipped"):
        print("Ignorados:", summary["skipped"])

    if payload.get("status") != "COMPLETED":
        return 2
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
