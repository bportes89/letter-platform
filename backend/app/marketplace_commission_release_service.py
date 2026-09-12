"""Liberação real de comissão Marketplace no Cadastro CONCLUIDO.

- Linhas fornecedor/plataforma → snapshot em terms_json.lifecycle.commission_release
- Rede afiliada → CommissionEntry via Universal MMN (product=MARKETPLACE)
"""

from __future__ import annotations

import json
from datetime import UTC, datetime
from decimal import Decimal

from fastapi import HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.affiliate_chain_commission_service import (
    allocate_bolo_chain_commissions,
    bolo_chain_affiliate_total,
    chain_commissions_block,
)
from app.models import CommissionEntry, CommissionRule, Lead, NetworkNode, Proposal, Quota, User
from app.network_service import LEVEL_SHARES, allocate_commissions
from app.quota_supplier_service import normalize_supplier_key, suppliers_index
from app.services import money

COMM_RELEASED = "RELEASED"
COMM_RELEASED_STUB = "RELEASED_STUB"
MARKETPLACE_POOL_PERCENT = Decimal("3")
REFERENCE_PREFIX = "MARKETPLACE_RELEASE:"


def release_reference(proposal_id: str) -> str:
    return f"{REFERENCE_PREFIX}{proposal_id}"


def _parse_json(raw: str | None) -> dict:
    try:
        data = json.loads(raw or "{}")
        return data if isinstance(data, dict) else {}
    except json.JSONDecodeError:
        return {}


def ensure_marketplace_commission_rule(db: Session, organization_id: str) -> CommissionRule:
    rule = db.scalar(
        select(CommissionRule).where(
            CommissionRule.organization_id == organization_id,
            CommissionRule.product == "MARKETPLACE",
            CommissionRule.commission_type == "SALES",
            CommissionRule.active.is_(True),
        )
    )
    if rule:
        return rule
    current = (
        db.scalar(
            select(CommissionRule.version).where(
                CommissionRule.organization_id == organization_id,
                CommissionRule.product == "MARKETPLACE",
                CommissionRule.commission_type == "SALES",
            )
        )
        or 0
    )
    rule = CommissionRule(
        organization_id=organization_id,
        product="MARKETPLACE",
        commission_type="SALES",
        version=int(current) + 1,
        base_type="CREDIT_VALUE",
        pool_rate_percent=MARKETPLACE_POOL_PERCENT,
        levels_json=json.dumps([str(x) for x in LEVEL_SHARES]),
        active=True,
    )
    db.add(rule)
    db.flush()
    return rule


def _sales_node(db: Session, organization_id: str, user_id: str) -> NetworkNode | None:
    return db.scalar(
        select(NetworkNode).where(
            NetworkNode.organization_id == organization_id,
            NetworkNode.user_id == user_id,
            NetworkNode.tree_type == "SALES",
        )
    )


def resolve_marketplace_originator(db: Session, proposal: Proposal, terms: dict) -> str | None:
    candidates: list[str] = []
    if proposal.commission_originator_id:
        candidates.append(str(proposal.commission_originator_id))
    partner = terms.get("partner_user_id")
    if partner:
        candidates.append(str(partner))
    if proposal.lead_id:
        lead = db.get(Lead, proposal.lead_id)
        if lead and lead.owner_id:
            candidates.append(str(lead.owner_id))
    seen: set[str] = set()
    for uid in candidates:
        if not uid or uid in seen:
            continue
        seen.add(uid)
        if _sales_node(db, proposal.organization_id, uid):
            return uid
    return None


def _platform_pct_for_release(supplier) -> Decimal:
    """Na liberação, usa platform_fee_percent do cadastro (sempre), não só se quem_paga=1."""
    if supplier is None:
        return Decimal("0.00")
    return money(Decimal(str(supplier.platform_fee_percent or 0)))


def compute_supplier_platform_lines(db: Session, proposal: Proposal) -> list[dict]:
    terms = _parse_json(proposal.terms_json)
    suppliers = suppliers_index(db, proposal.organization_id)
    lines: list[dict] = []

    quota_rows = [r for r in (terms.get("quotas") or []) if isinstance(r, dict)]
    if not quota_rows:
        quota_ids = [str(x) for x in (terms.get("quota_ids") or []) if x]
        if not quota_ids and terms.get("quota_id"):
            quota_ids = [str(terms["quota_id"])]
        quotas = list(db.scalars(select(Quota).where(Quota.id.in_(quota_ids)))) if quota_ids else []
        from app.marketplace_service import pricing_for_quota

        for quota in quotas:
            pricing = pricing_for_quota(quota, suppliers=suppliers)
            quota_rows.append(
                {
                    "quota_id": quota.id,
                    "supplier_source": quota.supplier_source,
                    "credit_value": str(pricing["credit"]),
                    "entrada_final": str(pricing["entrada_final"]),
                }
            )

    for row in quota_rows:
        quota_id = str(row.get("quota_id") or "")
        source = row.get("supplier_source")
        if not source and quota_id:
            quota = db.get(Quota, quota_id)
            source = quota.supplier_source if quota else None
        key = normalize_supplier_key(source)
        supplier = suppliers.get(key) if key else None
        if supplier is None and key:
            for sk, row_s in suppliers.items():
                if sk in key or key in sk:
                    supplier = row_s
                    break

        credit = money(Decimal(str(row.get("credit_value") or row.get("credit") or 0)))
        if credit <= 0 and quota_id:
            quota = db.get(Quota, quota_id)
            if quota:
                credit = money(Decimal(str(quota.credit_value)))

        entrada_raw = row.get("entrada_final") or row.get("entrada")
        if entrada_raw is None and quota_id:
            from app.marketplace_service import pricing_for_quota

            quota = db.get(Quota, quota_id)
            if quota:
                entrada_raw = pricing_for_quota(quota, suppliers=suppliers)["entrada_final"]
        entrada = money(Decimal(str(entrada_raw or 0)))

        platform_pct = _platform_pct_for_release(supplier)
        platform_amount = money(credit * platform_pct / Decimal("100")) if platform_pct > 0 else Decimal("0.00")
        supplier_amount = money(max(Decimal("0.00"), entrada - platform_amount))

        base = {
            "quota_id": quota_id or None,
            "supplier_source": source,
            "supplier_id": supplier.id if supplier else None,
            "supplier_name": supplier.name if supplier else None,
            "credit": str(credit),
            "entrada": str(entrada),
            "platform_pct": str(platform_pct),
            "platform_amount": str(platform_amount),
            "supplier_amount": str(supplier_amount),
        }
        lines.append({**base, "type": "platform_fee", "amount": str(platform_amount)})
        lines.append({**base, "type": "supplier_release", "amount": str(supplier_amount)})
    return lines


def _affiliate_calculation_base(proposal: Proposal, terms: dict) -> Decimal:
    raw = terms.get("total_credit")
    if raw is None:
        raw = proposal.requested_amount
    return money(Decimal(str(raw or 0)))


def _existing_entries(db: Session, proposal: Proposal, reference: str) -> list[CommissionEntry]:
    return list(
        db.scalars(
            select(CommissionEntry).where(
                CommissionEntry.organization_id == proposal.organization_id,
                CommissionEntry.reference == reference,
            )
        )
    )


def release_marketplace_commissions(db: Session, actor: User, proposal: Proposal) -> dict:
    """Idempotente: primeira CONCLUIDO libera; reentradas devolvem snapshot."""
    terms = _parse_json(proposal.terms_json)
    life = terms.get("lifecycle") if isinstance(terms.get("lifecycle"), dict) else {}
    reference = release_reference(proposal.id)

    if life.get("commission_release_status") == COMM_RELEASED and isinstance(life.get("commission_release"), dict):
        snap = life["commission_release"]
        from app.supplier_wallet_service import credit_supplier_releases_from_snapshot

        snap["supplier_wallet_credits"] = credit_supplier_releases_from_snapshot(db, proposal, snap)
        life["commission_release"] = snap
        terms["lifecycle"] = life
        proposal.terms_json = json.dumps(terms, ensure_ascii=False)
        db.flush()
        return snap

    existing = _existing_entries(db, proposal, reference)
    lines = compute_supplier_platform_lines(db, proposal)
    originator_id = resolve_marketplace_originator(db, proposal, terms)
    affiliate_ids: list[str] = [e.id for e in existing]
    affiliate_total = money(sum((Decimal(str(e.amount)) for e in existing), Decimal("0")))
    affiliate_skipped: str | None = None
    affiliate_mode: str | None = None

    if not existing and originator_id:
        use_bolo = chain_commissions_block(terms) is not None
        if use_bolo:
            affiliate_mode = "BOLO_CHAIN"
            try:
                entries = allocate_bolo_chain_commissions(
                    db,
                    actor,
                    originator_id=originator_id,
                    proposal=proposal,
                    reference=reference,
                    terms=terms,
                )
                affiliate_ids = [e.id for e in entries]
                affiliate_total = money(sum((Decimal(str(e.amount)) for e in entries), Decimal("0")))
                if affiliate_total <= 0:
                    affiliate_skipped = "bolo_chain_zero"
            except HTTPException as exc:
                if exc.status_code == 409:
                    existing = _existing_entries(db, proposal, reference)
                    affiliate_ids = [e.id for e in existing]
                    affiliate_total = money(sum((Decimal(str(e.amount)) for e in existing), Decimal("0")))
                else:
                    affiliate_skipped = str(exc.detail)
        else:
            affiliate_mode = "UNIVERSAL_MMN"
            ensure_marketplace_commission_rule(db, proposal.organization_id)
            base = _affiliate_calculation_base(proposal, terms)
            if base > 0:
                try:
                    entries = allocate_commissions(
                        db,
                        actor,
                        originator_id,
                        proposal.id,
                        reference,
                        "MARKETPLACE",
                        "SALES",
                        base,
                    )
                    now = datetime.now(UTC)
                    for entry in entries:
                        entry.status = "AVAILABLE"
                        entry.released_at = now
                    db.flush()
                    affiliate_ids = [e.id for e in entries]
                    affiliate_total = money(sum((Decimal(str(e.amount)) for e in entries), Decimal("0")))
                except HTTPException as exc:
                    if exc.status_code == 409:
                        existing = _existing_entries(db, proposal, reference)
                        affiliate_ids = [e.id for e in existing]
                        affiliate_total = money(sum((Decimal(str(e.amount)) for e in existing), Decimal("0")))
                    else:
                        affiliate_skipped = str(exc.detail)
            else:
                affiliate_skipped = "calculation_base_zero"
    elif not originator_id:
        affiliate_skipped = "no_originator_in_sales_tree"

    snapshot = {
        "reference": reference,
        "released_at": datetime.now(UTC).isoformat(),
        "lines": lines,
        "affiliate_originator_id": originator_id,
        "affiliate_mode": affiliate_mode,
        "affiliate_entry_ids": affiliate_ids,
        "affiliate_total": str(affiliate_total),
        "affiliate_bolo_precalc_total": str(bolo_chain_affiliate_total(terms))
        if chain_commissions_block(terms)
        else None,
        "affiliate_skipped": affiliate_skipped,
        "platform_total": str(
            money(
                sum(
                    (Decimal(str(x["amount"])) for x in lines if x.get("type") == "platform_fee"),
                    Decimal("0"),
                )
            )
        ),
        "supplier_total": str(
            money(
                sum(
                    (Decimal(str(x["amount"])) for x in lines if x.get("type") == "supplier_release"),
                    Decimal("0"),
                )
            )
        ),
    }

    life = dict(life)
    life["commission_release_status"] = COMM_RELEASED
    life["commission_released_at"] = snapshot["released_at"]
    life["commission_release"] = snapshot
    # limpa legado stub se ainda presente no blob
    terms["lifecycle"] = life
    proposal.terms_json = json.dumps(terms, ensure_ascii=False)
    db.flush()

    from app.supplier_wallet_service import credit_supplier_releases_from_snapshot

    snapshot["supplier_wallet_credits"] = credit_supplier_releases_from_snapshot(db, proposal, snapshot)
    life["commission_release"] = snapshot
    terms["lifecycle"] = life
    proposal.terms_json = json.dumps(terms, ensure_ascii=False)
    db.flush()
    return snapshot


def list_marketplace_extrato(db: Session, user: User, *, limit: int = 200) -> list[dict]:
    """Extrato admin: linhas fornecedor/plataforma + CommissionEntry MARKETPLACE_RELEASE."""
    limit = max(1, min(int(limit or 200), 500))
    rows: list[dict] = []

    proposals = list(
        db.scalars(
            select(Proposal)
            .where(
                Proposal.organization_id == user.organization_id,
                Proposal.product == "MARKETPLACE",
            )
            .order_by(Proposal.created_at.desc())
            .limit(limit * 2)
        )
    )
    for proposal in proposals:
        terms = _parse_json(proposal.terms_json)
        life = terms.get("lifecycle") if isinstance(terms.get("lifecycle"), dict) else {}
        snap = life.get("commission_release")
        if not isinstance(snap, dict):
            continue
        released_at = snap.get("released_at") or life.get("commission_released_at")
        for line in snap.get("lines") or []:
            if not isinstance(line, dict):
                continue
            rows.append(
                {
                    "kind": line.get("type"),
                    "released_at": released_at,
                    "proposal_id": proposal.id,
                    "lead_id": proposal.lead_id,
                    "reference": snap.get("reference"),
                    "beneficiary_label": line.get("supplier_name") or line.get("supplier_source"),
                    "beneficiary_id": line.get("supplier_id"),
                    "quota_id": line.get("quota_id"),
                    "credit": line.get("credit"),
                    "percent": line.get("platform_pct") if line.get("type") == "platform_fee" else None,
                    "amount": line.get("amount"),
                    "level": None,
                    "status": COMM_RELEASED,
                }
            )

    entries = list(
        db.scalars(
            select(CommissionEntry)
            .where(
                CommissionEntry.organization_id == user.organization_id,
                CommissionEntry.product == "MARKETPLACE",
                CommissionEntry.reference.like(f"{REFERENCE_PREFIX}%"),
            )
            .order_by(CommissionEntry.created_at.desc())
            .limit(limit)
        )
    )
    user_ids = {e.beneficiary_id for e in entries} | {e.originator_id for e in entries}
    users: dict[str, User] = {}
    if user_ids:
        users = {u.id: u for u in db.scalars(select(User).where(User.id.in_(list(user_ids))))}
    for entry in entries:
        beneficiary = users.get(entry.beneficiary_id)
        rows.append(
            {
                "kind": "affiliate",
                "released_at": (entry.released_at or entry.created_at).isoformat()
                if (entry.released_at or entry.created_at)
                else None,
                "proposal_id": entry.proposal_id,
                "lead_id": None,
                "reference": entry.reference,
                "beneficiary_label": beneficiary.name if beneficiary else entry.beneficiary_id,
                "beneficiary_id": entry.beneficiary_id,
                "quota_id": None,
                "credit": str(money(Decimal(str(entry.calculation_base)))),
                "percent": str(money(Decimal(str(entry.level_share_percent)))),
                "amount": str(money(Decimal(str(entry.amount)))),
                "level": entry.level,
                "status": entry.status,
            }
        )

    rows.sort(key=lambda r: r.get("released_at") or "", reverse=True)
    return rows[:limit]
