"""Filtros de perfil do cliente alinhados ao motor Esteira 2 / chat (paridade venda direta)."""

from __future__ import annotations

from datetime import UTC, datetime
from decimal import Decimal

from sqlalchemy.orm import Session

from app.models import Administrator, Quota


def quota_matches_category_tree(
    db: Session,
    organization_id: str,
    quota: Quota,
    quota_category_id: str | None,
) -> bool:
    if not quota_category_id:
        return True
    from app.quota_category_service import quota_category_filter_ids

    allowed = quota_category_filter_ids(db, organization_id, quota_category_id)
    if not allowed:
        return True
    return bool(quota.quota_category_id and quota.quota_category_id in allowed)


def quota_client_profile_blockers(
    db: Session,
    organization_id: str,
    quota: Quota,
    admin: Administrator | None,
    *,
    category: str,
    asset_year: int | None = None,
    asset_is_zero_km: bool = False,
    has_credit_restriction: bool = False,
    quota_category_id: str | None = None,
    client_bank_administrator_ids: list[str] | None = None,
    client_problem_bank_administrator_ids: list[str] | None = None,
) -> list[str]:
    """Bloqueios por administradora×categoria (alienações), bancos e subcategoria — sem régua de crédito."""
    if not quota_matches_category_tree(db, organization_id, quota, quota_category_id):
        return ["Cota fora da subcategoria selecionada."]

    if not admin:
        return ["Administradora da cota não encontrada."]

    bank_ids = set(client_bank_administrator_ids or []) if client_bank_administrator_ids else None
    problem_ids = (
        set(client_problem_bank_administrator_ids or [])
        if client_problem_bank_administrator_ids
        else None
    )
    if bank_ids or problem_ids:
        from app.administrator_marketplace_profile import administrator_in_client_pool

        if not administrator_in_client_pool(
            admin,
            client_bank_administrator_ids=bank_ids,
            client_problem_bank_administrator_ids=problem_ids,
        ):
            return [f"{admin.name} incompatível com bancos correntista / bancos problema informados."]

    if has_credit_restriction:
        from app.administrator_marketplace_profile import administrator_accepts_dirty_name

        if not administrator_accepts_dirty_name(admin):
            return [
                f"Administradora {admin.name} não aceita cliente com restrição SPC/Serasa (regras internas)."
            ]

    year = int(asset_year) if asset_year is not None else None
    if category == "VEHICLE" and year is None:
        year = datetime.now(UTC).year

    from app.administrator_marketplace_profile import alienation_blockers

    return alienation_blockers(
        db,
        admin,
        quota,
        category=category,
        asset_year=year or 0,
        asset_is_zero_km=asset_is_zero_km,
    )


def combo_client_profile_blockers(
    db: Session,
    organization_id: str,
    quotas: list[Quota],
    *,
    category: str,
    asset_year: int,
    asset_is_zero_km: bool,
    has_credit_restriction: bool,
    quota_category_id: str | None = None,
    client_bank_administrator_ids: list[str] | None = None,
    client_problem_bank_administrator_ids: list[str] | None = None,
    monthly_income: Decimal,
    asset_value: Decimal,
    credit_total: Decimal,
    installment_total: Decimal,
) -> list[str]:
    """Bacen + alienações para junção manual (mesma base do motor Esteira 2)."""
    if not quotas:
        return ["Informe ao menos uma cota."]
    admin = db.get(Administrator, quotas[0].administrator_id)
    from app.marketplace_service import admin_profile_blockers

    blockers = admin_profile_blockers(
        admin,
        category=category,
        asset_year=asset_year,
        asset_is_zero_km=asset_is_zero_km,
        has_credit_restriction=has_credit_restriction,
        credit_total=credit_total,
        installment_total=installment_total,
        monthly_income=monthly_income,
        asset_value=asset_value,
        combo_size=len(quotas),
        marketplace_income_rule=True,
    )
    for quota in quotas:
        blockers.extend(
            quota_client_profile_blockers(
                db,
                organization_id,
                quota,
                admin,
                category=category,
                asset_year=asset_year,
                asset_is_zero_km=asset_is_zero_km,
                has_credit_restriction=has_credit_restriction,
                quota_category_id=quota_category_id,
                client_bank_administrator_ids=client_bank_administrator_ids,
                client_problem_bank_administrator_ids=client_problem_bank_administrator_ids,
            )
        )
    return blockers
