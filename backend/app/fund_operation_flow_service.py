"""Acompanhamento de operação no escritório do Fundo (Flash Capital institucional).

Fluxo legado Cremona/Nordeste sem a etapa «Carta Paulo Letter» — inicia em Term Sheet.
"""

from __future__ import annotations

import json
from datetime import UTC, datetime
from typing import Any

from fastapi import HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import FlashSolicitation, Role, User

FLOW_STATUS_COMPLETED = "COMPLETED"
FLOW_STATUS_IN_PROGRESS = "IN_PROGRESS"
FLOW_STATUS_PENDING = "PENDING"

FUND_OPERATION_STEP_DEFS: list[dict[str, str]] = [
    {
        "code": "TERM_SHEET",
        "title": "Term Sheet",
        "description": (
            "Assinatura do term sheet, incluindo o vendedor que assume disposição de vender "
            "os autos com o deságio acordado."
        ),
    },
    {
        "code": "DOCS_COMPLIANCE",
        "title": "Documentações dos veículos e compliance",
        "description": "Vendedor envia documentação dos veículos e compliance do vendedor.",
    },
    {
        "code": "ESCROW_OPENING",
        "title": "Abertura da escrow",
        "description": "Abertura da conta escrow para a operação.",
    },
    {
        "code": "QUOTA_CESSAO",
        "title": "Termo de cessão de cotas",
        "description": "Assinatura do termo de cessão de cotas.",
    },
    {
        "code": "QUOTA_PURCHASE",
        "title": "Compra das cotas",
        "description": "Compra das cotas contempladas.",
    },
    {
        "code": "TRANSFER_CLIENT",
        "title": "Transferência ao cliente",
        "description": "Transferência das cotas ao cliente.",
    },
    {
        "code": "INVOICE_AF",
        "title": "Faturamento + AF",
        "description": "Emissão da nota comercial e aceite financeiro (AF).",
    },
    {
        "code": "FINANCIAL_SETTLEMENT",
        "title": "Liquidação financeira",
        "description": "Liquidação financeira da operação.",
    },
]

FUND_OFFICE_ROLES = frozenset({Role.INSTITUTIONAL_FUND, Role.PLATFORM_ADMIN, Role.INTERNAL_STAFF})


def _now_iso() -> str:
    return datetime.now(UTC).isoformat()


def _load_eval(item: FlashSolicitation) -> dict:
    try:
        data = json.loads(item.evaluation_json or "{}")
    except (TypeError, ValueError, json.JSONDecodeError):
        data = {}
    return data if isinstance(data, dict) else {}


def _save_eval(item: FlashSolicitation, data: dict) -> None:
    item.evaluation_json = json.dumps(data, ensure_ascii=False)


def default_fund_operation_flow() -> dict:
    steps: list[dict[str, Any]] = []
    for index, spec in enumerate(FUND_OPERATION_STEP_DEFS):
        status = FLOW_STATUS_IN_PROGRESS if index == 0 else FLOW_STATUS_PENDING
        steps.append({**spec, "status": status})
    return {
        "version": 1,
        "deadline_days": 30,
        "disclaimer": (
            "Prazo total estimado: até 30 dias. Ajustes de preço podem ocorrer após o prazo. "
            "A LETTER não se responsabiliza por atrasos operacionais de terceiros."
        ),
        "steps": steps,
        "updated_at": _now_iso(),
    }


def ensure_fund_operation_flow(item: FlashSolicitation) -> dict | None:
    if (item.capital_source or "").upper() != "INSTITUTIONAL":
        return None
    data = _load_eval(item)
    flow = data.get("fund_operation_flow")
    if not isinstance(flow, dict) or not flow.get("steps"):
        flow = default_fund_operation_flow()
        data["fund_operation_flow"] = flow
        _save_eval(item, data)
    return flow


def fund_operation_flow_view(item: FlashSolicitation) -> dict | None:
    if (item.capital_source or "").upper() != "INSTITUTIONAL":
        return None
    data = _load_eval(item)
    flow = data.get("fund_operation_flow")
    if not isinstance(flow, dict):
        return default_fund_operation_flow()
    return flow


def assert_fund_office_access(user: User) -> None:
    if user.role not in FUND_OFFICE_ROLES:
        raise HTTPException(status_code=403, detail="Acesso restrito ao escritório do Fundo.")


def list_fund_office_operations(db: Session, user: User) -> list[dict]:
    assert_fund_office_access(user)
    rows = list(
        db.scalars(
            select(FlashSolicitation)
            .where(
                FlashSolicitation.organization_id == user.organization_id,
                FlashSolicitation.capital_source == "INSTITUTIONAL",
            )
            .order_by(FlashSolicitation.created_at.desc())
        )
    )
    out: list[dict] = []
    for item in rows:
        flow = ensure_fund_operation_flow(item) or fund_operation_flow_view(item)
        current = current_flow_step(flow) if flow else None
        out.append(
            {
                "id": item.id,
                "contact_name": item.contact_name,
                "document": item.document,
                "status": item.status,
                "principal": str(item.principal),
                "asset_value": str(item.asset_value),
                "created_at": item.created_at.isoformat() if item.created_at else None,
                "current_step_code": current.get("code") if current else None,
                "current_step_title": current.get("title") if current else None,
                "current_step_status": current.get("status") if current else None,
            }
        )
    return out


def get_fund_office_operation(db: Session, user: User, solicitation_id: str) -> FlashSolicitation:
    assert_fund_office_access(user)
    item = db.scalar(
        select(FlashSolicitation).where(
            FlashSolicitation.id == solicitation_id,
            FlashSolicitation.organization_id == user.organization_id,
            FlashSolicitation.capital_source == "INSTITUTIONAL",
        )
    )
    if not item:
        raise HTTPException(status_code=404, detail="Operação do fundo não encontrada.")
    ensure_fund_operation_flow(item)
    return item


def current_flow_step(flow: dict | None) -> dict | None:
    if not flow:
        return None
    steps = flow.get("steps") or []
    for step in steps:
        if step.get("status") == FLOW_STATUS_IN_PROGRESS:
            return step
    for step in steps:
        if step.get("status") == FLOW_STATUS_PENDING:
            return step
    return steps[-1] if steps else None


def update_fund_operation_step(
    item: FlashSolicitation,
    *,
    step_code: str,
    status: str,
    advance_next: bool = True,
) -> dict:
    if (item.capital_source or "").upper() != "INSTITUTIONAL":
        raise HTTPException(status_code=422, detail="Fluxo do fundo só se aplica a origem INSTITUTIONAL.")
    status = status.upper()
    if status not in {FLOW_STATUS_COMPLETED, FLOW_STATUS_IN_PROGRESS, FLOW_STATUS_PENDING}:
        raise HTTPException(status_code=422, detail="Status inválido.")
    data = _load_eval(item)
    flow = ensure_fund_operation_flow(item) or default_fund_operation_flow()
    steps = flow.get("steps") or []
    index = next((i for i, s in enumerate(steps) if s.get("code") == step_code), None)
    if index is None:
        raise HTTPException(status_code=404, detail="Etapa não encontrada.")
    steps[index]["status"] = status
    if status == FLOW_STATUS_COMPLETED and advance_next:
        for j in range(len(steps)):
            if j < index:
                steps[j]["status"] = FLOW_STATUS_COMPLETED
            elif j == index:
                steps[j]["status"] = FLOW_STATUS_COMPLETED
            elif j == index + 1:
                steps[j]["status"] = FLOW_STATUS_IN_PROGRESS
            else:
                if steps[j].get("status") == FLOW_STATUS_IN_PROGRESS:
                    steps[j]["status"] = FLOW_STATUS_PENDING
    elif status == FLOW_STATUS_IN_PROGRESS:
        for j, step in enumerate(steps):
            if j != index and step.get("status") == FLOW_STATUS_IN_PROGRESS:
                step["status"] = FLOW_STATUS_PENDING
    flow["steps"] = steps
    flow["updated_at"] = _now_iso()
    data["fund_operation_flow"] = flow
    _save_eval(item, data)
    return flow
