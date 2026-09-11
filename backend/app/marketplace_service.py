"""Marketplace cartas contempladas — Esteira 1 (parceiro) e Esteira 2 (robô Nina / Paulo).

Esteira 2 (WhatsApp Paulo Stutz):
- Régua de corte 5% em crédito e entrada
- ~2 opções por crédito + ~2 por entrada (dedupe)
- Parcela vencendo em ≤7 dias: −1 prazo + valor na entrada
- Markup sobre crédito na entrada: Fraga/Bittelo/Lance +3%; Uni/Contemplado SP/Lume +10%
- Regras Bacen via approval_rules já sincronizadas em Administrator.rules_json
"""

from __future__ import annotations

import itertools
from datetime import UTC, date, datetime, timedelta
from decimal import Decimal

from fastapi import HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.administrator_service import APPROVED_STATUSES, parse_rules
from app.models import Administrator, Quota, User
from app.quota_inventory_service import run_nina_quota_scan
from app.services import money

DEFAULT_INCOME_RATIO = Decimal("3")
ESTEIRA2_BAND_PERCENT = Decimal("5")
ESTEIRA2_CREDIT_LANE_LIMIT = 2
ESTEIRA2_ENTRADA_LANE_LIMIT = 2
INSTALLMENT_ROLLOVER_DAYS = 7


def normalize_supplier_key(value: str | None) -> str:
    from app.quota_supplier_service import normalize_supplier_key as _norm

    return _norm(value or "") if value else ""


def supplier_markup_percent(supplier_source: str | None) -> Decimal:
    from app.quota_supplier_service import resolve_supplier_fees

    return resolve_supplier_fees(supplier_source)["markup_percent"]


def _within_band(value: Decimal, target: Decimal, band_percent: Decimal = ESTEIRA2_BAND_PERCENT) -> bool:
    if target <= 0:
        return False
    deviation = abs((value - target) / target * 100)
    return deviation <= band_percent


def _deviation_percent(value: Decimal, target: Decimal) -> Decimal:
    if target <= 0:
        return Decimal("100")
    return money(abs((value - target) / target * 100))


def apply_installment_rollover(
    *,
    entrada_base: Decimal,
    installment_value: Decimal,
    installment_due_date: date | None,
    remaining_installments: int | None,
    as_of: date | None = None,
) -> dict:
    """Se parcela vence em ≤7 dias: −1 prazo e soma a parcela na entrada."""
    today = as_of or datetime.now(UTC).date()
    applied = False
    entrada = money(entrada_base)
    remaining = remaining_installments
    days_to_due = None
    if installment_due_date:
        days_to_due = (installment_due_date - today).days
        if 0 <= days_to_due <= INSTALLMENT_ROLLOVER_DAYS:
            applied = True
            entrada = money(entrada + money(installment_value))
            if remaining is not None and remaining > 0:
                remaining = remaining - 1
    return {
        "applied": applied,
        "entrada": entrada,
        "remaining_installments": remaining,
        "days_to_due": days_to_due,
    }


def normalize_supplier_key(value: str | None) -> str:
    from app.quota_supplier_service import normalize_supplier_key as _norm

    return _norm(value)


def supplier_markup_percent(supplier_source: str | None) -> Decimal:
    from app.quota_supplier_service import resolve_supplier_fees

    return resolve_supplier_fees(supplier_source)["markup_percent"]


def apply_supplier_markup(
    *,
    entrada: Decimal,
    credit: Decimal,
    supplier_source: str | None,
    suppliers: dict | None = None,
) -> dict:
    from app.quota_supplier_service import resolve_supplier_fees

    fees = resolve_supplier_fees(supplier_source, suppliers=suppliers)
    markup_pct = fees["markup_percent"]
    platform_pct = fees["platform_fee_percent"]
    markup_amount = money(credit * markup_pct / Decimal("100")) if markup_pct > 0 else Decimal("0.00")
    platform_amount = money(credit * platform_pct / Decimal("100")) if platform_pct > 0 else Decimal("0.00")
    add_on = money(markup_amount + platform_amount)
    return {
        "markup_percent": str(markup_pct),
        "markup_amount": str(add_on),
        "platform_fee_percent": str(platform_pct),
        "platform_fee_amount": str(platform_amount),
        "quem_paga_comissao": fees["quem_paga_comissao"],
        "entrada": money(entrada + add_on),
    }


def pricing_for_quota(
    quota: Quota,
    *,
    as_of: date | None = None,
    suppliers: dict | None = None,
    affiliate_markup: dict[str, str] | None = None,
) -> dict:
    """Entrada efetiva após rollover 7 dias + markup do fornecedor (+ comissão embutida)."""
    from app.affiliate_markup_service import affiliate_markup_amount

    credit = money(Decimal(str(quota.credit_value)))
    base_entrada = money(Decimal(str(quota.premium_value or 0)))
    installment = money(Decimal(str(quota.installment_value or 0)))
    rollover = apply_installment_rollover(
        entrada_base=base_entrada,
        installment_value=installment,
        installment_due_date=quota.installment_due_date,
        remaining_installments=quota.remaining_installments,
        as_of=as_of,
    )
    markup = apply_supplier_markup(
        entrada=rollover["entrada"],
        credit=credit,
        supplier_source=quota.supplier_source,
        suppliers=suppliers,
    )
    affiliate_amount = affiliate_markup_amount(credit, affiliate_markup)
    entrada_final = money(markup["entrada"] + affiliate_amount)
    porc_a_mais = str((affiliate_markup or {}).get("porc_a_mais") or "0")
    porc_a_mais_sellers = str((affiliate_markup or {}).get("porc_a_mais_sellers") or "0")
    return {
        "credit": credit,
        "entrada_base": base_entrada,
        "entrada_after_rollover": rollover["entrada"],
        "entrada_final": entrada_final,
        "installment": installment,
        "rollover_applied": rollover["applied"],
        "remaining_installments": rollover["remaining_installments"],
        "days_to_due": rollover["days_to_due"],
        "markup_percent": markup["markup_percent"],
        "markup_amount": markup["markup_amount"],
        "platform_fee_percent": markup.get("platform_fee_percent"),
        "quem_paga_comissao": markup.get("quem_paga_comissao", 0),
        "supplier_source": quota.supplier_source,
        "porc_a_mais": porc_a_mais,
        "porc_a_mais_sellers": porc_a_mais_sellers,
        "affiliate_markup_amount": str(affiliate_amount),
    }


def pricing_for_combo(
    quotas: list[Quota],
    *,
    as_of: date | None = None,
    suppliers: dict | None = None,
    affiliate_markup: dict[str, str] | None = None,
) -> dict:
    rows = [pricing_for_quota(q, as_of=as_of, suppliers=suppliers, affiliate_markup=affiliate_markup) for q in quotas]
    credit = money(sum((r["credit"] for r in rows), Decimal("0")))
    entrada_final = money(sum((r["entrada_final"] for r in rows), Decimal("0")))
    installment = money(sum((r["installment"] for r in rows), Decimal("0")))
    return {
        "credit": credit,
        "entrada_final": entrada_final,
        "installment": installment,
        "rollover_applied": any(r["rollover_applied"] for r in rows),
        "remaining_installments": (
            sum(r["remaining_installments"] for r in rows if r["remaining_installments"] is not None)
            if any(r["remaining_installments"] is not None for r in rows)
            else None
        ),
        "markup_amount": money(sum((Decimal(r["markup_amount"]) for r in rows), Decimal("0"))),
        "quotas_pricing": rows,
    }


def _quota_summary(
    quota: Quota,
    admin: Administrator | None,
    *,
    as_of: date | None = None,
    suppliers: dict | None = None,
    affiliate_markup: dict[str, str] | None = None,
) -> dict:
    pricing = pricing_for_quota(quota, as_of=as_of, suppliers=suppliers, affiliate_markup=affiliate_markup)
    return {
        "quota_id": quota.id,
        "group_code": quota.group_code,
        "quota_code": quota.quota_code,
        "category": quota.category,
        "credit_value": str(pricing["credit"]),
        "premium_value": str(pricing["entrada_base"]),
        "entrada_final": str(pricing["entrada_final"]),
        "installment_value": str(pricing["installment"]),
        "installment_due_date": quota.installment_due_date.isoformat() if quota.installment_due_date else None,
        "remaining_installments": pricing["remaining_installments"],
        "supplier_source": quota.supplier_source,
        "markup_percent": pricing["markup_percent"],
        "markup_amount": pricing["markup_amount"],
        "rollover_applied": pricing["rollover_applied"],
        "administrator_name": admin.name if admin else None,
        "status": quota.status,
        "nina_scan_status": quota.nina_scan_status,
    }


def _installment_total(quotas: list[Quota]) -> Decimal:
    return money(sum((Decimal(str(q.installment_value or 0)) for q in quotas), Decimal("0")))


def admin_profile_blockers(
    admin: Administrator | None,
    *,
    category: str,
    asset_year: int,
    asset_is_zero_km: bool,
    has_credit_restriction: bool,
    credit_total: Decimal,
    installment_total: Decimal,
    monthly_income: Decimal,
    asset_value: Decimal,
    target_amount: Decimal | None = None,
    combo_size: int = 1,
) -> list[str]:
    """Bloqueios a partir de rules_json (painel + approval_rules Bacen sincronizadas)."""
    blockers: list[str] = []
    check_amount = target_amount or credit_total

    if asset_value <= 0:
        blockers.append("Informe o valor de avaliação do bem.")
    elif check_amount > asset_value:
        blockers.append(
            f"Crédito alvo (R$ {money(check_amount)}) excede o valor do bem (R$ {money(asset_value)})."
        )

    if monthly_income <= 0:
        blockers.append("Informe a renda mensal comprovada do cliente.")

    if not admin:
        blockers.append("Administradora da cota não encontrada.")
        return blockers

    if admin.authorization_status not in APPROVED_STATUSES:
        blockers.append(f"Administradora {admin.name} com status {admin.authorization_status}.")

    rules = parse_rules(admin.rules_json)
    products = rules.get("products_enabled") or []
    if products and "MARKETPLACE" not in products:
        blockers.append(f"Administradora {admin.name} sem produto MARKETPLACE habilitado nas regras internas.")

    allowed_categories = rules.get("allowed_categories") or []
    if allowed_categories and category not in allowed_categories:
        blockers.append(
            f"Categoria {category} não permitida pelas regras internas de {admin.name}."
        )

    max_age = int(rules.get("max_asset_age_years") or 15)
    if asset_is_zero_km:
        if not bool(rules.get("accepts_zero_km", True)):
            blockers.append(f"Administradora {admin.name} não aceita bem zero km.")
    elif category == "VEHICLE":
        age = datetime.now(UTC).year - int(asset_year)
        if age > max_age:
            blockers.append(
                f"Bem com {age} anos — acima do limite de {max_age} anos nas regras de {admin.name}."
            )

    if has_credit_restriction and not bool(rules.get("accepts_dirty_name", False)):
        blockers.append(
            f"Administradora {admin.name} não aceita cliente com restrição SPC/Serasa (regras internas)."
        )

    ratio = Decimal(str(rules.get("min_income_to_installment_ratio") or DEFAULT_INCOME_RATIO))
    approval = rules.get("approval_rules") if isinstance(rules.get("approval_rules"), dict) else {}
    # Bacen sync: margem de renda em approval_rules.min_income_margin (ex.: 0.30 = 30%)
    if approval.get("min_income_margin") is not None:
        try:
            margin = Decimal(str(approval["min_income_margin"]))
            if margin > 0:
                # se veio como 30 (percentual) ou 0.30 (fração)
                if margin > 1:
                    ratio = max(ratio, Decimal("100") / margin)
                else:
                    ratio = max(ratio, Decimal("1") / margin)
        except Exception:
            pass

    if installment_total > 0 and monthly_income > 0:
        max_installment = money(monthly_income / ratio)
        if installment_total > max_installment:
            blockers.append(
                f"Renda comprovada (R$ {money(monthly_income)}) precisa cobrir no mínimo "
                f"{ratio:g}× a parcela (R$ {installment_total}); teto da parcela: R$ {max_installment}."
            )

    max_ltv = approval.get("max_ltv_percent")
    # LTV Bacen (ex.: 40%) vale para crédito fiduciário (Flash/SDC), não para matching de carta contemplada.
    # No Marketplace o lastro continua sendo crédito ≤ valor do bem (teto 100%).
    _ = max_ltv

    if approval.get("scr_clear_required") and has_credit_restriction:
        blockers.append(
            f"Regras Bacen de {admin.name} exigem SCR limpo — cliente com restrição cadastral."
        )

    credit_rules = rules.get("credit_utilization_rules") if isinstance(rules.get("credit_utilization_rules"), dict) else {}
    max_credit = credit_rules.get("max_credit_per_operation_brl")
    if max_credit and credit_total > Decimal(str(max_credit)):
        blockers.append(
            f"Crédito (R$ {money(credit_total)}) excede o teto interno de {admin.name} (R$ {money(Decimal(str(max_credit)))})."
        )
    max_combined = credit_rules.get("max_combined_quotas")
    if max_combined and combo_size > int(max_combined):
        blockers.append(
            f"Combinação de {combo_size} cotas excede o máximo de {max_combined} nas regras de {admin.name}."
        )

    return blockers


def _eligible_combo_candidate(
    db: Session,
    quotas: tuple[Quota, ...],
    *,
    category: str,
    asset_value: Decimal,
    asset_year: int,
    monthly_income: Decimal,
    has_credit_restriction: bool,
    asset_is_zero_km: bool,
    target_amount: Decimal,
    as_of: date | None = None,
    suppliers: dict | None = None,
    affiliate_markup: dict[str, str] | None = None,
) -> dict | None:
    if len({q.administrator_id for q in quotas}) > 1:
        return None
    admin = db.get(Administrator, quotas[0].administrator_id)
    pricing = pricing_for_combo(list(quotas), as_of=as_of, suppliers=suppliers, affiliate_markup=affiliate_markup)
    blockers = admin_profile_blockers(
        admin,
        category=category,
        asset_year=asset_year,
        asset_is_zero_km=asset_is_zero_km,
        has_credit_restriction=has_credit_restriction,
        credit_total=pricing["credit"],
        installment_total=pricing["installment"],
        monthly_income=monthly_income,
        asset_value=asset_value,
        target_amount=target_amount,
        combo_size=len(quotas),
    )
    if blockers:
        return None
    credit_dev = _deviation_percent(pricing["credit"], target_amount)
    score = max(0, 1000 - int(credit_dev * 20) - len(quotas) * 5)
    return {
        "quota_ids": [q.id for q in quotas],
        "quotas": [
            _quota_summary(
                q,
                db.get(Administrator, q.administrator_id),
                as_of=as_of,
                suppliers=suppliers,
                affiliate_markup=affiliate_markup,
            )
            for q in quotas
        ],
        "total_credit": str(pricing["credit"]),
        "total_entrada": str(pricing["entrada_final"]),
        "deviation_percent": str(credit_dev),
        "entrada_deviation_percent": None,
        "score": score,
        "administrator_id": quotas[0].administrator_id,
        "administrator_name": admin.name if admin else None,
        "lane": None,
        "rollover_applied": pricing["rollover_applied"],
        "markup_amount": str(pricing["markup_amount"]),
        "remaining_installments": pricing["remaining_installments"],
        "explanation": (
            f"Nina selecionou {len(quotas)} cota(s) · crédito R$ {pricing['credit']} "
            f"(desvio {credit_dev}%) · entrada efetiva R$ {pricing['entrada_final']}."
        ),
        "message": "Combinação compatível com perfil, Bacen/approval_rules e régua de 5%.",
    }


def _rank_alternatives(
    db: Session,
    user: User,
    *,
    target_amount: Decimal,
    category: str,
    asset_value: Decimal,
    asset_year: int,
    monthly_income: Decimal,
    has_credit_restriction: bool,
    asset_is_zero_km: bool,
    exclude_quota_id: str | None = None,
    limit: int = 5,
    target_entrada: Decimal | None = None,
    band_percent: Decimal = ESTEIRA2_BAND_PERCENT,
    as_of: date | None = None,
    affiliate_markup: dict[str, str] | None = None,
) -> list[dict]:
    """Candidatos na banda de crédito (e entrada, se informada)."""
    from app.quota_supplier_service import suppliers_index

    suppliers = suppliers_index(db, user.organization_id)
    quotas = list(
        db.scalars(
            select(Quota).where(
                Quota.organization_id == user.organization_id,
                Quota.status == "AVAILABLE",
                Quota.category == category,
            )
        )
    )
    candidates: list[dict] = []
    for size in range(1, min(3, len(quotas)) + 1):
        for combo in itertools.combinations(quotas, size):
            if exclude_quota_id and exclude_quota_id in {q.id for q in combo}:
                continue
            item = _eligible_combo_candidate(
                db,
                combo,
                category=category,
                asset_value=asset_value,
                asset_year=asset_year,
                monthly_income=monthly_income,
                has_credit_restriction=has_credit_restriction,
                asset_is_zero_km=asset_is_zero_km,
                target_amount=target_amount,
                as_of=as_of,
                suppliers=suppliers,
                affiliate_markup=affiliate_markup,
            )
            if not item:
                continue
            credit = Decimal(item["total_credit"])
            if not _within_band(credit, target_amount, band_percent):
                continue
            if target_entrada is not None and target_entrada > 0:
                entrada = Decimal(item["total_entrada"])
                if not _within_band(entrada, target_entrada, band_percent):
                    # ainda pode servir na lane de crédito; marca desvio de entrada
                    item["entrada_deviation_percent"] = str(_deviation_percent(entrada, target_entrada))
                else:
                    item["entrada_deviation_percent"] = str(_deviation_percent(entrada, target_entrada))
            candidates.append(item)
    return sorted(candidates, key=lambda x: (-x["score"], Decimal(x["deviation_percent"])))[: max(limit * 4, 20)]


def esteira1_partner_select(
    db: Session,
    user: User,
    *,
    quota_id: str,
    monthly_income: Decimal,
    monthly_commitment: Decimal,
    asset_value: Decimal,
    asset_year: int,
    has_credit_restriction: bool = False,
    asset_is_zero_km: bool = False,
) -> dict:
    """Esteira 1: parceiro escolhe a carta → Nina varre → sugere alternativas se perfil não couber."""
    del monthly_commitment
    quota = db.scalar(select(Quota).where(Quota.id == quota_id, Quota.organization_id == user.organization_id))
    if not quota:
        raise HTTPException(status_code=404, detail="Cota não encontrada.")
    if quota.status not in {"AVAILABLE", "RESERVED"}:
        raise HTTPException(status_code=409, detail="Cota indisponível para análise.")

    admin = db.get(Administrator, quota.administrator_id)
    if quota.nina_scan_status != "CLEARED":
        try:
            run_nina_quota_scan(db, user, quota)
        except HTTPException as exc:
            return {
                "esteira": "SELF_SELECT",
                "eligible": False,
                "quota": _quota_summary(quota, admin),
                "blockers": [str(exc.detail)],
                "alternatives": _rank_alternatives(
                    db,
                    user,
                    target_amount=Decimal(str(quota.credit_value)),
                    category=quota.category,
                    asset_value=asset_value,
                    asset_year=asset_year,
                    monthly_income=monthly_income,
                    has_credit_restriction=has_credit_restriction,
                    asset_is_zero_km=asset_is_zero_km,
                    exclude_quota_id=quota.id,
                    band_percent=Decimal("100"),  # alternativas Esteira 1: ranking amplo
                ),
                "message": "Varredura cadastral Nina reprovou a cota escolhida.",
            }

    credit = Decimal(str(quota.credit_value))
    blockers = admin_profile_blockers(
        admin,
        category=quota.category,
        asset_year=asset_year,
        asset_is_zero_km=asset_is_zero_km,
        has_credit_restriction=has_credit_restriction,
        credit_total=credit,
        installment_total=_installment_total([quota]),
        monthly_income=monthly_income,
        asset_value=asset_value,
        combo_size=1,
    )

    eligible = len(blockers) == 0
    alternatives = []
    if not eligible:
        alternatives = _rank_alternatives(
            db,
            user,
            target_amount=credit,
            category=quota.category,
            asset_value=asset_value,
            asset_year=asset_year,
            monthly_income=monthly_income,
            has_credit_restriction=has_credit_restriction,
            asset_is_zero_km=asset_is_zero_km,
            exclude_quota_id=quota.id,
            band_percent=Decimal("100"),
        )

    return {
        "esteira": "SELF_SELECT",
        "eligible": eligible,
        "quota": _quota_summary(quota, admin),
        "blockers": blockers,
        "alternatives": alternatives,
        "message": (
            "Cliente apto para a carta escolhida (regras internas + Bacen/approval_rules). Prossiga com trava de 60 min e proposta."
            if eligible
            else "Cliente sem perfil para esta carta. Nina indicou alternativas compatíveis."
        ),
    }


def esteira2_nina_curated_match(
    db: Session,
    user: User,
    *,
    target_amount: Decimal,
    category: str,
    asset_year: int,
    monthly_income: Decimal,
    monthly_commitment: Decimal,
    asset_value: Decimal,
    has_credit_restriction: bool = False,
    asset_is_zero_km: bool = False,
    target_entrada: Decimal | None = None,
    limit: int = 8,
    as_of: date | None = None,
    affiliate_markup: dict[str, str] | None = None,
) -> dict:
    """Esteira 2 robô: banda 5%, lanes crédito/entrada, rollover 7d e markup fornecedor."""
    del monthly_commitment
    if category not in {"REAL_ESTATE", "VEHICLE"}:
        raise HTTPException(status_code=422, detail="Categoria deve ser REAL_ESTATE ou VEHICLE.")

    if monthly_income <= 0:
        return {
            "esteira": "NINA_CURATED",
            "eligible": False,
            "blockers": ["Informe a renda mensal comprovada do cliente."],
            "matches": [],
            "credit_matches": [],
            "entrada_matches": [],
            "band_percent": str(ESTEIRA2_BAND_PERCENT),
            "message": "Perfil incompleto para matching.",
        }
    if asset_value <= 0:
        return {
            "esteira": "NINA_CURATED",
            "eligible": False,
            "blockers": ["Informe o valor de avaliação do bem."],
            "matches": [],
            "credit_matches": [],
            "entrada_matches": [],
            "band_percent": str(ESTEIRA2_BAND_PERCENT),
            "message": "Perfil incompleto para matching.",
        }
    if target_amount > asset_value:
        return {
            "esteira": "NINA_CURATED",
            "eligible": False,
            "blockers": [
                f"Crédito alvo (R$ {money(target_amount)}) excede o valor do bem (R$ {money(asset_value)})."
            ],
            "matches": [],
            "credit_matches": [],
            "entrada_matches": [],
            "band_percent": str(ESTEIRA2_BAND_PERCENT),
            "message": "Perfil do cliente não permite matching automático. Ajuste renda, bem ou valor alvo.",
        }

    pool = _rank_alternatives(
        db,
        user,
        target_amount=target_amount,
        category=category,
        asset_value=asset_value,
        asset_year=asset_year,
        monthly_income=monthly_income,
        has_credit_restriction=has_credit_restriction,
        asset_is_zero_km=asset_is_zero_km,
        limit=max(limit, 12),
        target_entrada=target_entrada,
        band_percent=ESTEIRA2_BAND_PERCENT,
        as_of=as_of,
        affiliate_markup=affiliate_markup,
    )

    credit_lane: list[dict] = []
    for item in sorted(pool, key=lambda x: (Decimal(x["deviation_percent"]), -x["score"])):
        row = {**item, "lane": "CREDIT"}
        credit_lane.append(row)
        if len(credit_lane) >= ESTEIRA2_CREDIT_LANE_LIMIT:
            break

    entrada_lane: list[dict] = []
    if target_entrada is not None and target_entrada > 0:
        ranked_entrada = sorted(
            [
                x
                for x in pool
                if x.get("entrada_deviation_percent") is not None
                and Decimal(x["entrada_deviation_percent"]) <= ESTEIRA2_BAND_PERCENT
            ],
            key=lambda x: (Decimal(x["entrada_deviation_percent"]), -x["score"]),
        )
        seen = {tuple(x["quota_ids"]) for x in credit_lane}
        for item in ranked_entrada:
            key = tuple(item["quota_ids"])
            if key in seen:
                # ainda conta na lane entrada se couber na banda
                pass
            row = {**item, "lane": "ENTRADA"}
            entrada_lane.append(row)
            seen.add(key)
            if len(entrada_lane) >= ESTEIRA2_ENTRADA_LANE_LIMIT:
                break
    else:
        # Sem entrada alvo: completa com as próximas melhores por crédito (até 2 extras)
        seen = {tuple(x["quota_ids"]) for x in credit_lane}
        for item in pool:
            key = tuple(item["quota_ids"])
            if key in seen:
                continue
            entrada_lane.append({**item, "lane": "CREDIT_EXTRA"})
            seen.add(key)
            if len(entrada_lane) >= ESTEIRA2_ENTRADA_LANE_LIMIT:
                break

    # matches = união ordenada credit + entrada (dedupe preservando ordem)
    matches: list[dict] = []
    seen_ids: set[tuple[str, ...]] = set()
    for item in credit_lane + entrada_lane:
        key = tuple(item["quota_ids"])
        if key in seen_ids:
            continue
        seen_ids.add(key)
        matches.append(item)
        if len(matches) >= limit:
            break

    band_msg = (
        f"régua {ESTEIRA2_BAND_PERCENT}% · até {ESTEIRA2_CREDIT_LANE_LIMIT} por crédito"
        + (f" + {ESTEIRA2_ENTRADA_LANE_LIMIT} por entrada" if target_entrada else "")
        + f" · rollover {INSTALLMENT_ROLLOVER_DAYS}d · markup fornecedor"
    )
    return {
        "esteira": "NINA_CURATED",
        "eligible": bool(matches),
        "blockers": [] if matches else ["Nenhuma combinação na régua de 5% para o perfil e as regras Bacen/internas."],
        "matches": matches,
        "credit_matches": credit_lane,
        "entrada_matches": entrada_lane,
        "band_percent": str(ESTEIRA2_BAND_PERCENT),
        "message": (
            f"Robô Nina: {len(matches)} opção(ões) para crédito R$ {money(target_amount)}"
            + (f" / entrada R$ {money(target_entrada)}" if target_entrada else "")
            + f" ({band_msg})."
            if matches
            else f"Sem opções na {band_msg}. Cadastre cotas ou ajuste alvos."
        ),
    }
