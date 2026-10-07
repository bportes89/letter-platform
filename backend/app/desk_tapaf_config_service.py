"""Valores TAPAF editáveis por organização (mesas SDC / Flash / QuitCon alienação)."""

from __future__ import annotations

from decimal import Decimal, InvalidOperation

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import OrganizationSetting
from app.tapaf_constants import TAPAF_NOMINAL

_KEYS = {
    "SDC": "desk.tapaf.nominal.sdc",
    "FLASH": "desk.tapaf.nominal.flash",
    "QUITCON_ALIENACAO": "desk.tapaf.nominal.quitcon_alienacao",
}


def _read_org_decimal(db: Session, organization_id: str, field_key: str) -> Decimal | None:
    row = db.execute(
        select(OrganizationSetting).where(
            OrganizationSetting.organization_id == organization_id,
            OrganizationSetting.field_key == field_key,
        ),
    ).scalar_one_or_none()
    if not row or not str(row.value or "").strip():
        return None
    try:
        val = Decimal(str(row.value).strip().replace(",", "."))
    except (InvalidOperation, ValueError):
        return None
    if val <= 0:
        return None
    return val.quantize(Decimal("0.01"))


def resolve_desk_tapaf_nominal(db: Session | None, organization_id: str | None, channel: str) -> Decimal:
    """channel: SDC | FLASH | QUITCON_ALIENACAO"""
    key = _KEYS.get(str(channel or "").strip().upper())
    if db and organization_id and key:
        custom = _read_org_decimal(db, organization_id, key)
        if custom is not None:
            return custom
    return TAPAF_NOMINAL


def list_desk_tapaf_config(db: Session, organization_id: str) -> dict[str, str]:
    out: dict[str, str] = {}
    for ch, fk in _KEYS.items():
        custom = _read_org_decimal(db, organization_id, fk)
        out[ch] = str(custom if custom is not None else TAPAF_NOMINAL)
    return out


def save_desk_tapaf_config(db: Session, organization_id: str, values: dict[str, str | Decimal]) -> dict[str, str]:
    saved = list_desk_tapaf_config(db, organization_id)
    for ch, raw in values.items():
        fk = _KEYS.get(str(ch).strip().upper())
        if not fk:
            continue
        try:
            amount = Decimal(str(raw).strip().replace(",", ".")).quantize(Decimal("0.01"))
        except (InvalidOperation, ValueError):
            raise ValueError(f"Valor TAPAF inválido para {ch}")
        if amount <= 0:
            raise ValueError(f"Valor TAPAF deve ser positivo ({ch})")
        row = db.execute(
            select(OrganizationSetting).where(
                OrganizationSetting.organization_id == organization_id,
                OrganizationSetting.field_key == fk,
            ),
        ).scalar_one_or_none()
        if row:
            row.value = str(amount)
        else:
            db.add(OrganizationSetting(organization_id=organization_id, field_key=fk, value=str(amount)))
        saved[ch.upper()] = str(amount)
    db.flush()
    return saved
