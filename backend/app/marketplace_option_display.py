"""Formatação de opções do robô marketplace (paridade cards legado)."""

from __future__ import annotations

from collections import defaultdict
from datetime import date, datetime
from decimal import Decimal
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import Quota, QuotaCategory


def _brl(value: Decimal | str | float | int) -> str:
    amount = Decimal(str(value or 0))
    text = f"{amount:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")
    return f"R$ {text}"


def format_parcela_legacy(quotas: list[dict[str, Any]]) -> str:
    """Ex.: 124x de R$ 3.827,08 mais 44x de R$ 2.450,00"""
    groups: dict[tuple[int, str], int] = defaultdict(int)
    for q in quotas:
        try:
            n = int(q.get("remaining_installments") or 0)
        except (TypeError, ValueError):
            n = 0
        if n <= 0:
            continue
        inst = str(q.get("installment_value") or "0")
        groups[(n, inst)] += 1
    if not groups:
        return ""
    parts: list[str] = []
    for (n, inst), count in sorted(groups.items(), key=lambda x: (-x[0][0], x[0][1])):
        label = f"{n}x de {_brl(inst)}"
        if count > 1:
            label = f"{count} cotas · {label}"
        parts.append(label)
    return " mais ".join(parts)


def installment_due_hints(quotas: list[dict[str, Any]]) -> tuple[str | None, str | None]:
    """Dia fixo de vencimento e próxima data (ISO → dd/mm/aaaa)."""
    days: set[int] = set()
    dates: list[date] = []
    for q in quotas:
        raw = q.get("installment_due_date")
        if not raw:
            continue
        try:
            if isinstance(raw, date):
                d = raw
            else:
                d = date.fromisoformat(str(raw)[:10])
        except ValueError:
            continue
        days.add(d.day)
        dates.append(d)
    day_txt = str(sorted(days)[0]) if len(days) == 1 else None
    next_txt = None
    if dates:
        earliest = min(dates)
        next_txt = earliest.strftime("%d/%m/%Y")
    return day_txt, next_txt


def resolve_tipo_credito_label(
    db: Session,
    organization_id: str,
    quotas: list[dict[str, Any]],
    *,
    fallback: str = "",
) -> str:
    names: list[str] = []
    for q in quotas:
        qid = q.get("quota_id")
        if not qid:
            continue
        quota = db.scalar(
            select(Quota).where(Quota.id == qid, Quota.organization_id == organization_id)
        )
        if not quota or not quota.quota_category_id:
            continue
        cat = db.get(QuotaCategory, quota.quota_category_id)
        if cat and cat.name and cat.name not in names:
            names.append(cat.name)
    if names:
        return " / ".join(names)
    if fallback == "REAL_ESTATE":
        return "Imóvel"
    if fallback == "VEHICLE":
        return "Veículo"
    return fallback or "Carta contemplada"


def enrich_match_row_display(
    db: Session,
    organization_id: str,
    row: dict[str, Any],
    *,
    category: str,
) -> dict[str, Any]:
    """Campos de card legado (parcelas, vencimento, tipo) para chat e admin."""
    quotas = row.get("quotas") or []
    out = dict(row)
    out["parcela_legacy"] = format_parcela_legacy(quotas)
    due_day, due_next = installment_due_hints(quotas)
    out["vencimento_dia"] = due_day
    out["vencimento_proxima"] = due_next
    out["tipo_credito"] = resolve_tipo_credito_label(db, organization_id, quotas, fallback=category)
    return out


def chat_option_from_match_row(
    db: Session,
    organization_id: str,
    row: dict[str, Any],
    *,
    lane_label: str,
    category: str,
    brl_fn,
) -> dict[str, Any]:
    enriched = enrich_match_row_display(db, organization_id, row, category=category)
    quotas = enriched.get("quotas") or []
    q0 = quotas[0] if quotas else {}
    parcela_txt = enriched.get("parcela_legacy") or format_parcela_legacy(quotas)
    due_day = enriched.get("vencimento_dia")
    due_next = enriched.get("vencimento_proxima")
    tipo = enriched.get("tipo_credito") or resolve_tipo_credito_label(
        db, organization_id, quotas, fallback=category
    )
    credit = row.get("total_credit")
    entrada = row.get("total_entrada") or 0
    qids = row.get("quota_ids") or []
    key = "|".join(str(x) for x in qids)
    short = f"{lane_label}: {brl_fn(credit)} · entrada {brl_fn(entrada)}"
    return {
        "id": key,
        "name": short,
        "next": None,  # caller sets STEP_CONFIRM
        "save": key,
        "administradora": enriched.get("administrator_name") or q0.get("administrator_name"),
        "tipo_credito": tipo,
        "price": brl_fn(credit),
        "price_entrada": brl_fn(entrada),
        "parcelas": row.get("remaining_installments") or q0.get("remaining_installments"),
        "price_parcela": parcela_txt or (brl_fn(q0.get("installment_value")) if q0.get("installment_value") else ""),
        "vencimento_dia": due_day,
        "vencimento_proxima": due_next,
        "lane": lane_label,
    }
