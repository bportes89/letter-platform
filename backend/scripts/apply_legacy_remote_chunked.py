"""Apply remoto da migracao legada em lotes (evita timeout na API Render)."""

from __future__ import annotations

import argparse
import json
import os
import sys
import time
from pathlib import Path
from typing import Any

import httpx

DEFAULT_API = "https://letter-api-fobc.onrender.com/api/v1"
DEFAULT_BUNDLE = Path(__file__).resolve().parents[2] / "legacy" / "export" / "bundle.json"
DEFAULT_OUT = Path(__file__).resolve().parents[2] / "artifacts"

CHUNK_SIZES = {
    "leads": 1000,
    "quotas": 1500,
}


def login(client: httpx.Client, base_url: str, email: str, password: str) -> str:
    response = client.post(f"{base_url}/auth/login", json={"email": email, "password": password})
    response.raise_for_status()
    token = response.json().get("access_token")
    if not token:
        raise RuntimeError("Login nao retornou access_token")
    return token


def chunk_list(items: list[Any], size: int) -> list[list[Any]]:
    return [items[i : i + size] for i in range(0, len(items), size)]


def build_steps(bundle: dict[str, Any]) -> list[tuple[str, dict[str, Any]]]:
    legacy_source = bundle["legacy_source"]
    entities = bundle.get("entities") or {}
    steps: list[tuple[str, dict[str, Any]]] = []

    core_entities = {}
    for name in ("organizations", "branches", "administrators", "users", "network_nodes"):
        if entities.get(name):
            core_entities[name] = entities[name]
    if core_entities:
        steps.append(("core", {"legacy_source": legacy_source, "entities": core_entities}))

    leads = entities.get("leads") or []
    if leads:
        for index, chunk in enumerate(chunk_list(leads, CHUNK_SIZES["leads"]), start=1):
            steps.append(
                (
                    f"leads-{index}/{max(1, (len(leads) + CHUNK_SIZES['leads'] - 1) // CHUNK_SIZES['leads'])}",
                    {"legacy_source": legacy_source, "entities": {"leads": chunk}},
                )
            )

    quotas = entities.get("quotas") or []
    if quotas:
        total = max(1, (len(quotas) + CHUNK_SIZES["quotas"] - 1) // CHUNK_SIZES["quotas"])
        for index, chunk in enumerate(chunk_list(quotas, CHUNK_SIZES["quotas"]), start=1):
            steps.append(
                (
                    f"quotas-{index}/{total}",
                    {"legacy_source": legacy_source, "entities": {"quotas": chunk}},
                )
            )

    proposals = entities.get("proposals") or []
    if proposals:
        steps.append(("proposals", {"legacy_source": legacy_source, "entities": {"proposals": proposals}}))

    return steps


def post_step(
    client: httpx.Client,
    *,
    base_url: str,
    token: str,
    step_name: str,
    payload: dict[str, Any],
    dry_run: bool,
    timeout: int,
    retries: int,
) -> dict[str, Any]:
    endpoint = "dry-run" if dry_run else "apply"
    url = f"{base_url.rstrip('/')}/admin/migration/{endpoint}"
    body = json.dumps(payload, ensure_ascii=False).encode("utf-8")
    size_mb = len(body) / (1024 * 1024)
    print(f"\n==> {step_name} ({size_mb:.2f} MB) -> POST /admin/migration/{endpoint}")

    headers = {
        "Authorization": f"Bearer {token}",
        "Content-Type": "application/json; charset=utf-8",
    }

    last_error: Exception | None = None
    for attempt in range(1, retries + 1):
        started = time.perf_counter()
        print(f"    tentativa {attempt}/{retries}...")
        try:
            response = client.post(url, headers=headers, content=body)
            elapsed = time.perf_counter() - started
            print(f"    HTTP {response.status_code} em {elapsed:.1f}s")
            if response.status_code >= 400:
                print(response.text[:3000], file=sys.stderr)
                response.raise_for_status()
            result = response.json()
            status = result.get("status")
            summary = result.get("summary") or {}
            if status != "COMPLETED":
                raise RuntimeError(f"Step {step_name} terminou com status {status}: {result.get('error_message')}")
            if dry_run and summary.get("ready") is False:
                raise RuntimeError(f"Step {step_name} dry-run not ready")
            if summary.get("created"):
                print(f"    criados: {summary['created']}")
            if summary.get("reused"):
                print(f"    reutilizados: {summary['reused']}")
            return result
        except Exception as exc:  # noqa: BLE001
            last_error = exc
            if attempt == retries:
                raise
            wait = 10 * attempt
            print(f"    falha: {exc}. aguardando {wait}s...")
            time.sleep(wait)
    raise last_error or RuntimeError("falha desconhecida")


def main() -> int:
    parser = argparse.ArgumentParser(description="Apply remoto em lotes da migracao legada")
    parser.add_argument("--api-base", default=os.environ.get("LETTER_API_BASE", DEFAULT_API))
    parser.add_argument("--bundle", type=Path, default=DEFAULT_BUNDLE)
    parser.add_argument("--email", default=os.environ.get("LETTER_ADMIN_EMAIL", "admin@letter.com.br"))
    parser.add_argument("--password", default=os.environ.get("LETTER_ADMIN_PASSWORD", ""))
    parser.add_argument("--token", default=os.environ.get("LETTER_ACCESS_TOKEN", ""))
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--timeout", type=int, default=900)
    parser.add_argument("--retries", type=int, default=3)
    parser.add_argument(
        "--skip",
        nargs="*",
        default=[],
        help="Pular passos cujo nome comeca com algum destes prefixos (ex: core leads-1)",
    )
    args = parser.parse_args()

    if not args.bundle.is_file():
        print(f"Bundle nao encontrado: {args.bundle}", file=sys.stderr)
        return 1

    password = args.password or os.environ.get("LETTER_DEMO_PASSWORD", "Letter@123")
    bundle = json.loads(args.bundle.read_text(encoding="utf-8"))
    steps = build_steps(bundle)
    if args.skip:
        skip_prefixes = tuple(args.skip)
        steps = [(name, payload) for name, payload in steps if not name.startswith(skip_prefixes)]
    print(f"Bundle: {args.bundle}")
    print(f"Passos planejados: {len(steps)}")
    for name, payload in steps:
        counts = {k: len(v) for k, v in (payload.get("entities") or {}).items() if isinstance(v, list)}
        print(f"  - {name}: {counts}")

    timeout = httpx.Timeout(args.timeout, connect=60.0)
    results: list[dict[str, Any]] = []
    with httpx.Client(timeout=timeout) as client:
        token = args.token or login(client, args.api_base, args.email, password)
        for step_name, payload in steps:
            result = post_step(
                client,
                base_url=args.api_base,
                token=token,
                step_name=step_name,
                payload=payload,
                dry_run=args.dry_run,
                timeout=args.timeout,
                retries=args.retries,
            )
            results.append({"step": step_name, "result": result})

    DEFAULT_OUT.mkdir(parents=True, exist_ok=True)
    stamp = time.strftime("%Y%m%d-%H%M%S")
    mode = "dry-run" if args.dry_run else "apply"
    out_file = DEFAULT_OUT / f"migration-chunked-{mode}-{stamp}.json"
    out_file.write_text(json.dumps(results, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"\nConcluido. Relatorio: {out_file}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
