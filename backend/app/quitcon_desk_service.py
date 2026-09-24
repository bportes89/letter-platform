"""QuitCon commercial desk — solicitação → docs/status → operação AGUARDANDO_TAPAF."""

from __future__ import annotations

from decimal import Decimal
from json import dumps as json_dumps

from fastapi import HTTPException, UploadFile
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.desk_solicitation_meta import desk_payload_extras, evaluation_json_with_meta, evaluation_meta
from app.document_service import persist_upload, purge_document, purge_document_links
from app.models import (
    CommissionRule,
    Document,
    Lead,
    Proposal,
    QuitConSolicitation,
    QuitConSolicitationDocument,
    Role,
    User,
)
from app.network_service import PARTNER_NETWORK_ROLES
from app.quitcon_engine import EngineQuitConLetter
from app.quitcon_service import create_operacao, generate_tapaf_checkout
from app.services import money

QUITCON_PRODUCT = "QUITCON"
LEVEL_SHARES = ["50", "35", "7", "5", "3"]

DESK_ROLES = frozenset({
    Role.PLATFORM_ADMIN,
    Role.INTERNAL_STAFF,
    Role.MASTER_FRANCHISEE,
    Role.MANAGER,
    Role.PARTNER,
})

STATUS_AWAITING_DOCS = "AWAITING_DOCS"
STATUS_UNDER_REVIEW = "UNDER_REVIEW"
STATUS_PENDING = "PENDING"
STATUS_APPROVED = "APPROVED"
STATUS_REJECTED = "REJECTED"
STATUS_CANCELLED = "CANCELLED"
STATUS_TERMINAL = frozenset({STATUS_APPROVED, STATUS_REJECTED, STATUS_CANCELLED})

STATUS_LABELS = {
    STATUS_AWAITING_DOCS: "Aguardando Documentação",
    STATUS_UNDER_REVIEW: "Em Análise",
    STATUS_PENDING: "Pendente",
    STATUS_APPROVED: "Aprovado",
    STATUS_REJECTED: "Reprovado",
    STATUS_CANCELLED: "Cancelado",
}

REQUIRED_DOCS = [
    {"code": "EXTRATO_CONSORCIO", "label": "Extrato atualizado da cota"},
    {"code": "CONTRATO_CONSORCIO", "label": "Contrato / regulamento do grupo"},
    {"code": "DOCUMENTOS_PESSOAIS", "label": "Documentos pessoais (RG/CPF ou CNPJ)"},
    {"code": "COMPROVANTE_PARCELAS", "label": "Comprovante de parcelas em dia"},
]


def assert_desk_access(user: User) -> None:
    if user.role not in DESK_ROLES:
        raise HTTPException(status_code=403, detail="Sem acesso à mesa comercial QuitCon")


def _dec(value) -> Decimal:
    return Decimal(str(value or 0))


def _split_group_quota(raw: dict) -> tuple[str, str]:
    group_code = str(raw.get("group_code") or "").strip()
    quota_code = str(raw.get("quota_code") or "").strip()
    if group_code and quota_code:
        return group_code, quota_code
    registry_number = str(raw.get("registry_number") or "").strip()
    if "/" in registry_number:
        left, right = registry_number.split("/", 1)
        return left.strip(), right.strip()
    return registry_number, ""


def _compute_quota_breakdown(
    lines: list,
    engine: EngineQuitConLetter | None = None,
) -> tuple[list[dict], Decimal, Decimal, int, str]:
    engine = engine or EngineQuitConLetter()
    rows: list[dict] = []
    total_saldo = Decimal(0)
    total_vp = Decimal(0)
    max_meses = 0
    reg_parts: list[str] = []
    for raw in lines:
        if not isinstance(raw, dict):
            continue
        group_code, quota_code = _split_group_quota(raw)
        if not group_code or not quota_code:
            continue
        parcela = _dec(raw.get("installment_value") or 0)
        meses = int(raw.get("meses_restantes") or 0)
        if meses <= 0 or meses > 240:
            continue
        saldo_manual = _dec(raw.get("outstanding_balance") or 0)
        if parcela > 0:
            saldo = money(parcela * meses)
        elif saldo_manual > 0:
            saldo = money(saldo_manual)
        else:
            continue
        vp = engine.calcular_valor_quitcon_vp(saldo, meses)
        credit = money(_dec(raw.get("credit_at_billing") or 0))
        total_saldo += saldo
        total_vp += vp
        max_meses = max(max_meses, meses)
        reg_parts.append(f"{group_code}/{quota_code}")
        rows.append(
            {
                "group_code": group_code,
                "quota_code": quota_code,
                "registry_number": f"{group_code}/{quota_code}",
                "credit_at_billing": str(credit),
                "installment_value": str(money(parcela)),
                "meses_restantes": meses,
                "saldo_devedor_calculado": str(saldo),
                "valor_quitacao_vp": str(vp),
                "economia_linha": str(money(saldo - vp)),
            }
        )
    if not rows:
        return [], Decimal(0), Decimal(0), 0, ""
    if len(reg_parts) == 1:
        registry_number = reg_parts[0]
    else:
        registry_number = f"{reg_parts[0]} (+{len(reg_parts) - 1} cotas)"
    return rows, total_saldo, total_vp, max_meses, registry_number


def _apply_total_vp_to_snapshot(
    engine: EngineQuitConLetter,
    snapshot: dict,
    *,
    total_vp: Decimal,
    total_saldo: Decimal,
    max_meses: int,
    operational_service: bool,
) -> dict:
    vp = money(total_vp)
    sb = money(total_saldo)
    snapshot["saldo_devedor_bruto"] = str(sb)
    snapshot["meses_restantes"] = max_meses
    snapshot["valor_presente_quitacao"] = str(vp)
    taxa_intermediacao = engine.calcular_taxa_intermediacao_sobre_quitacao(vp)
    pagamento_total_cedente = engine.calcular_pagamento_total_cedente(vp)
    taxa_servico_inicio = (
        engine.calcular_taxa_servico_operacional_inicio(vp) if operational_service else money(Decimal("0"))
    )
    liberacao = engine.calcular_liberacao_cessionario(vp)
    taxa_sucesso_escrow = engine.calcular_taxa_sucesso_escrow(vp)
    snapshot["custos_entrada"] = engine.montar_custos_entrada(vp, operational_service=operational_service)
    snapshot["cedente"] = {
        **(snapshot.get("cedente") or {}),
        "quitacao_vista_vp": str(vp),
        "taxa_intermediacao_3_porcento_sobre_quitacao": str(taxa_intermediacao),
        "pagamento_total_quitacao_mais_intermediacao": str(pagamento_total_cedente),
        "taxa_servico_operacional_2_porcento_inicio": str(taxa_servico_inicio),
        "servico_operacional_contratado": operational_service,
    }
    snapshot["cessionario"] = {
        **(snapshot.get("cessionario") or {}),
        "valor_base_quitacao": liberacao["valor_base_quitacao"],
        "taxa_plataforma_5_porcento_na_liberacao": liberacao["taxa_plataforma_5_porcento"],
        "capital_giro_liquido_na_liberacao": liberacao["capital_giro_liquido_na_liberacao"],
        "taxa_sucesso_escrow_10_porcento": str(taxa_sucesso_escrow),
    }
    return snapshot


def _format_address(addr: dict | None) -> str | None:
    if not addr or not isinstance(addr, dict):
        return None
    parts = [
        addr.get("street"),
        addr.get("number"),
        addr.get("complement"),
        addr.get("district"),
        addr.get("city"),
        addr.get("state"),
        addr.get("zip"),
    ]
    text = ", ".join(str(p).strip() for p in parts if p and str(p).strip())
    return text or None


def _address_errors(addr: dict | None, label: str) -> list[str]:
    if not addr or not isinstance(addr, dict):
        return [f"{label}: informe o endereço completo (CEP, logradouro, número, cidade e UF)."]
    errs: list[str] = []
    if not str(addr.get("zip") or "").strip():
        errs.append(f"{label}: informe o CEP.")
    if not str(addr.get("street") or "").strip():
        errs.append(f"{label}: informe o logradouro.")
    if not str(addr.get("number") or "").strip():
        errs.append(f"{label}: informe o número.")
    if not str(addr.get("city") or "").strip():
        errs.append(f"{label}: informe a cidade.")
    if not str(addr.get("state") or "").strip():
        errs.append(f"{label}: informe a UF.")
    return errs


def _is_admin(user: User) -> bool:
    return user.role in {Role.PLATFORM_ADMIN, Role.INTERNAL_STAFF, Role.MASTER_FRANCHISEE}


def evaluate_quitcon_desk(data: dict) -> dict:
    motivos: list[str] = []
    engine = EngineQuitConLetter()
    quota_lines = data.get("quota_lines") or []
    breakdown: list[dict] = []
    total_vp_override: Decimal | None = None

    saldo = Decimal(0)
    meses = 0
    registry_number = ""

    if quota_lines:
        breakdown, saldo, total_vp, meses, registry_number = _compute_quota_breakdown(quota_lines, engine)
        if not breakdown:
            motivos.append("Informe ao menos uma cota válida (grupo, cota, parcela atual e prazo restante).")
        else:
            data = {
                **data,
                "outstanding_balance": str(saldo),
                "meses_restantes": meses,
                "registry_number": registry_number,
            }
            total_vp_override = total_vp
            for row in breakdown:
                if _dec(row.get("credit_at_billing")) <= 0:
                    motivos.append(
                        f"Cota {row['registry_number']}: informe o valor do crédito quando faturou o bem."
                    )
    else:
        saldo = _dec(data.get("outstanding_balance") or 0)
        if saldo <= 0:
            motivos.append("Informe o saldo devedor bruto da cota.")
        raw_meses = data.get("meses_restantes")
        if raw_meses is None or str(raw_meses).strip() == "":
            meses = 0
        else:
            meses = int(raw_meses)
        if meses <= 0 or meses > 240:
            motivos.append("Meses restantes inválidos.")
        registry_number = str(data.get("registry_number") or "").strip()
        if not registry_number:
            motivos.append("Informe grupo e cota.")

    if saldo <= 0 and not motivos:
        motivos.append("Informe o saldo devedor (parcela × prazo ou cotas válidas).")
    if meses <= 0 or meses > 240:
        if "Meses restantes inválidos." not in motivos:
            motivos.append("Meses restantes inválidos.")
    if not registry_number and not motivos:
        motivos.append("Informe grupo e cota.")

    registry_office = str(data.get("registry_office") or data.get("administrator_name") or "").strip()
    if not registry_office:
        motivos.append("Informe a administradora (whitelist doc253).")

    if not bool(data.get("docs_complete", True)):
        motivos.append("Documentação incompleta.")

    contemplada = bool(data.get("contemplada", True))
    bem_faturado = bool(data.get("bem_faturado", True))
    parcelas_em_dia = bool(data.get("parcelas_em_dia", True))
    operational_service = bool(data.get("operational_service", False))

    totais = None
    if breakdown:
        totais = {
            "saldo_devedor_total": str(money(saldo)),
            "quitacao_vp_total": str(money(total_vp_override or 0)),
            "economia_total": str(money(saldo - (total_vp_override or 0))),
        }

    if motivos and saldo <= 0:
        return {
            "viable": False,
            "motivos": motivos,
            "required_docs": REQUIRED_DOCS,
            "snapshot": None,
            "valor_presente_quitacao": "0.00",
            "custos_entrada": None,
            "quota_breakdown": breakdown,
            "totais": totais,
            "message": "NÃO FOI POSSÍVEL SEGUIR COM A SUA OPERAÇÃO",
        }

    snapshot = engine.simular_quitcon_doc253(
        saldo,
        max(meses, 1),
        operational_service=operational_service,
        administrator_name=registry_office or None,
        contemplada=contemplada,
        bem_faturado=bem_faturado,
        parcelas_em_dia=parcelas_em_dia,
    )
    if total_vp_override is not None:
        snapshot = _apply_total_vp_to_snapshot(
            engine,
            snapshot,
            total_vp=total_vp_override,
            total_saldo=saldo,
            max_meses=meses,
            operational_service=operational_service,
        )
        if breakdown:
            snapshot["quota_breakdown"] = breakdown
            snapshot["totais"] = totais

    eleg = snapshot["elegibilidade"]
    if not eleg["elegivel"]:
        for b in eleg["blockers"]:
            motivos.append(f"Elegibilidade: {b}")

    if motivos:
        return {
            "viable": False,
            "motivos": motivos,
            "required_docs": REQUIRED_DOCS,
            "snapshot": snapshot,
            "valor_presente_quitacao": snapshot.get("valor_presente_quitacao", "0.00"),
            "custos_entrada": snapshot.get("custos_entrada"),
            "quota_breakdown": breakdown,
            "totais": totais,
            "message": "NÃO FOI POSSÍVEL SEGUIR COM A SUA OPERAÇÃO",
        }

    return {
        "viable": True,
        "motivos": [],
        "required_docs": REQUIRED_DOCS,
        "snapshot": snapshot,
        "valor_presente_quitacao": snapshot["valor_presente_quitacao"],
        "custos_entrada": snapshot["custos_entrada"],
        "cedente": snapshot["cedente"],
        "cessionario": snapshot["cessionario"],
        "quota_breakdown": breakdown,
        "totais": totais,
        "message": "Operação viável — QuitCon doc253",
    }


def _chain_user_ids(db: Session, user: User) -> list[str]:
    from app.models import NetworkNode

    ids = {user.id}
    changed = True
    while changed:
        changed = False
        children = list(
            db.scalars(
                select(NetworkNode).where(
                    NetworkNode.organization_id == user.organization_id,
                    NetworkNode.sponsor_user_id.in_(list(ids)),
                    NetworkNode.tree_type == "SALES",
                )
            )
        )
        for child in children:
            if child.user_id not in ids:
                ids.add(child.user_id)
                changed = True
    return list(ids)


def list_solicitations(db: Session, user: User) -> list[QuitConSolicitation]:
    assert_desk_access(user)
    q = select(QuitConSolicitation).where(QuitConSolicitation.organization_id == user.organization_id)
    if not _is_admin(user):
        chain = _chain_user_ids(db, user)
        q = q.where(QuitConSolicitation.partner_user_id.in_(chain or [user.id]))
    return list(db.scalars(q.order_by(QuitConSolicitation.created_at.desc())))


def list_documents(db: Session, solicitation_id: str) -> list[QuitConSolicitationDocument]:
    return list(
        db.scalars(
            select(QuitConSolicitationDocument)
            .where(QuitConSolicitationDocument.solicitation_id == solicitation_id)
            .order_by(QuitConSolicitationDocument.created_at.desc())
        )
    )


def get_solicitation(db: Session, user: User, solicitation_id: str) -> QuitConSolicitation:
    assert_desk_access(user)
    item = db.scalar(
        select(QuitConSolicitation).where(
            QuitConSolicitation.id == solicitation_id,
            QuitConSolicitation.organization_id == user.organization_id,
        )
    )
    if not item:
        raise HTTPException(status_code=404, detail="Solicitação QuitCon não encontrada")
    if not _is_admin(user) and item.partner_user_id not in _chain_user_ids(db, user):
        raise HTTPException(status_code=403, detail="Sem acesso a esta solicitação")
    return item


def store_solicitation(db: Session, user: User, payload: dict) -> QuitConSolicitation:
    assert_desk_access(user)
    addr_errors = _address_errors(payload.get("client_address_json"), "Endereço do cliente")
    addr_errors.extend(_address_errors(payload.get("asset_address_json"), "Endereço do bem alienado"))
    if addr_errors:
        raise HTTPException(status_code=422, detail={"message": "Endereço incompleto", "motivos": addr_errors})
    if bool(payload.get("operational_service")) and not bool(payload.get("operational_service_accepted")):
        raise HTTPException(
            status_code=422,
            detail={
                "message": "Aceite a taxa de serviço LETTER (2%) para continuar.",
                "motivos": [
                    "A taxa de serviço não é reembolsável, refere-se à intermediação/representação junto à "
                    "administradora e não é o fee de sucesso após a conclusão da operação."
                ],
            },
        )
    client_address = payload.get("client_address_json")
    formatted_client = _format_address(client_address if isinstance(client_address, dict) else None)
    if formatted_client:
        payload = {**payload, "address": formatted_client}
    result = evaluate_quitcon_desk(payload)
    if not result["viable"]:
        raise HTTPException(
            status_code=422,
            detail={"message": result["message"], "motivos": result["motivos"], "result": result},
        )
    partner_id = user.id if user.role in PARTNER_NETWORK_ROLES or user.role == Role.PARTNER else payload.get("partner_user_id") or user.id
    if _is_admin(user) and payload.get("partner_user_id"):
        partner_id = payload["partner_user_id"]

    item = QuitConSolicitation(
        organization_id=user.organization_id,
        partner_user_id=partner_id,
        created_by_id=user.id,
        status=STATUS_AWAITING_DOCS,
        contact_name=str(payload["contact_name"]).strip(),
        contact_email=str(payload["contact_email"]).strip().lower(),
        contact_phone=str(payload.get("contact_phone") or "").strip(),
        document=str(payload.get("document") or "").strip() or None,
        person_type=str(payload.get("person_type") or "PF").upper()[:2],
        address=str(payload.get("address") or "").strip() or None,
        occupation=str(payload.get("occupation") or "").strip() or None,
        income_value=money(_dec(payload.get("income_value") or 0)),
        outstanding_balance=money(_dec(payload["outstanding_balance"])),
        meses_restantes=int(payload["meses_restantes"]),
        registry_number=str(payload["registry_number"]).strip(),
        registry_office=str(payload["registry_office"]).strip(),
        property_type=str(payload.get("property_type") or "CONSORCIO").upper()[:40],
        appraisal_value=money(_dec(payload.get("appraisal_value") or payload["outstanding_balance"])),
        operational_service=bool(payload.get("operational_service", False)),
        contemplada=bool(payload.get("contemplada", True)),
        bem_faturado=bool(payload.get("bem_faturado", True)),
        parcelas_em_dia=bool(payload.get("parcelas_em_dia", True)),
        docs_complete=bool(payload.get("docs_complete", True)),
        quitacao_vp_amount=money(_dec(result["valor_presente_quitacao"])),
        evaluation_json=evaluation_json_with_meta(
            {
                **result,
                **desk_payload_extras(
                    payload,
                    (
                        "quota_lines",
                        "client_address_json",
                        "asset_address_json",
                        "operational_service_accepted",
                        "alienated_property_registry",
                        "alienated_asset_address",
                        "alienated_vehicle_plate",
                        "alienated_vehicle_chassi",
                        "alienated_vehicle_renavam",
                        "partners_json",
                    ),
                ),
            },
            channel="QUITCON_DESK",
            lead_id=str(payload.get("lead_id") or "").strip() or None,
        ),
    )
    db.add(item)
    db.flush()
    return item


def update_status(db: Session, user: User, item: QuitConSolicitation, status: str, notes: str | None = None) -> QuitConSolicitation:
    assert_desk_access(user)
    if not _is_admin(user):
        raise HTTPException(status_code=403, detail="Apenas operação LETTER altera o status do QuitCon")
    status = status.upper().strip()
    if status not in STATUS_LABELS:
        raise HTTPException(status_code=422, detail="Status inválido")
    item.status = status
    if notes is not None:
        item.status_notes = notes
    db.flush()
    return item


async def add_document(
    db: Session,
    user: User,
    item: QuitConSolicitation,
    *,
    upload: UploadFile,
    doc_type: str,
    comment: str | None = None,
) -> QuitConSolicitationDocument:
    assert_desk_access(user)
    if item.status in STATUS_TERMINAL and not _is_admin(user):
        raise HTTPException(status_code=422, detail="Esta solicitação já está encerrada e não aceita mais documentos.")
    document = await persist_upload(upload, user, "quitcon_solicitation", item.id, doc_type or "QUITCON_SUPPORT")
    document.status = "CLEAN"
    db.add(document)
    db.flush()
    row = QuitConSolicitationDocument(
        organization_id=user.organization_id,
        solicitation_id=item.id,
        document_id=document.id,
        doc_type=(doc_type or "QUITCON_SUPPORT")[:80],
        comment=(comment or None),
        uploaded_by_id=user.id,
    )
    db.add(row)
    if not _is_admin(user) and item.status == STATUS_AWAITING_DOCS:
        item.status = STATUS_UNDER_REVIEW
    db.flush()
    return row


def remove_document(db: Session, user: User, item: QuitConSolicitation, link_id: str) -> None:
    assert_desk_access(user)
    if not _is_admin(user):
        raise HTTPException(status_code=403, detail="Apenas operação LETTER pode excluir documentos")
    row = db.scalar(
        select(QuitConSolicitationDocument).where(
            QuitConSolicitationDocument.id == link_id,
            QuitConSolicitationDocument.solicitation_id == item.id,
            QuitConSolicitationDocument.organization_id == user.organization_id,
        )
    )
    if not row:
        raise HTTPException(status_code=404, detail="Documento não encontrado")
    document = db.get(Document, row.document_id)
    db.delete(row)
    if document:
        purge_document_links(db, document.id)
        purge_document(db, document)
    db.flush()


def _document_link_view(db: Session, row: QuitConSolicitationDocument) -> dict:
    document = db.get(Document, row.document_id)
    return {
        "id": row.id,
        "doc_type": row.doc_type,
        "comment": row.comment,
        "document_id": row.document_id,
        "filename": document.filename if document else None,
        "status": document.status if document else None,
        "created_at": row.created_at.isoformat() if row.created_at else None,
    }


def ensure_quitcon_commission_rule(db: Session, organization_id: str) -> CommissionRule:
    existing = db.scalar(
        select(CommissionRule).where(
            CommissionRule.organization_id == organization_id,
            CommissionRule.product == QUITCON_PRODUCT,
            CommissionRule.commission_type == "SALES",
            CommissionRule.active.is_(True),
        )
    )
    if existing:
        return existing
    version = db.scalar(
        select(CommissionRule.version).where(
            CommissionRule.organization_id == organization_id,
            CommissionRule.product == QUITCON_PRODUCT,
            CommissionRule.commission_type == "SALES",
        ).order_by(CommissionRule.version.desc())
    ) or 0
    rule = CommissionRule(
        organization_id=organization_id,
        product=QUITCON_PRODUCT,
        commission_type="SALES",
        version=version + 1,
        base_type="QUITACAO_VP",
        pool_rate_percent=Decimal("3"),
        levels_json=json_dumps(LEVEL_SHARES),
        active=True,
    )
    db.add(rule)
    db.flush()
    return rule


def create_sale_from_quitcon(db: Session, user: User, item: QuitConSolicitation) -> dict:
    assert_desk_access(user)
    if item.status != STATUS_APPROVED:
        raise HTTPException(status_code=422, detail="Só QuitCon Aprovado pode abrir operação")
    if item.quitcon_operacao_id or item.proposal_id:
        raise HTTPException(status_code=409, detail="Este QuitCon já possui operação/proposta vinculada")

    ensure_quitcon_commission_rule(db, user.organization_id)

    lead = Lead(
        organization_id=user.organization_id,
        owner_id=item.partner_user_id or user.id,
        name=item.contact_name,
        phone=item.contact_phone or "00000000000",
        document=item.document,
        product_interest=QUITCON_PRODUCT,
        status="QUALIFIED",
        source="QUITCON_DESK",
    )
    db.add(lead)
    db.flush()
    proposal = Proposal(
        organization_id=user.organization_id,
        lead_id=lead.id,
        product=QUITCON_PRODUCT,
        requested_amount=item.quitacao_vp_amount,
        status="SUBMITTED",
        terms_json=json_dumps(
            {
                "quitcon_solicitation_id": item.id,
                "outstanding_balance": str(item.outstanding_balance),
                "meses_restantes": item.meses_restantes,
                "registry_office": item.registry_office,
                "channel": "QUITCON_DESK",
            },
            ensure_ascii=False,
        ),
        sale_channel="PARTNER_OFFICE",
        served_by_user_id=user.id,
        commission_originator_id=item.partner_user_id,
        created_by_user_id=user.id,
    )
    db.add(proposal)
    db.flush()

    operacao = create_operacao(
        db,
        user,
        proposal,
        outstanding_balance=item.outstanding_balance,
        registry_number=item.registry_number,
        registry_office=item.registry_office,
        property_type=item.property_type,
        appraisal_value=item.appraisal_value,
        owner_user_id=item.partner_user_id or user.id,
        meses_restantes=item.meses_restantes,
        operational_service=item.operational_service,
        contemplada=item.contemplada,
        bem_faturado=item.bem_faturado,
        parcelas_em_dia=item.parcelas_em_dia,
    )
    checkout = generate_tapaf_checkout(operacao)
    item.proposal_id = proposal.id
    item.quitcon_operacao_id = operacao.id
    db.flush()
    return {
        "proposal_id": proposal.id,
        "lead_id": lead.id,
        "quitcon_operacao_id": operacao.id,
        "operacao_code": operacao.operacao_code,
        "operacao_status": operacao.status,
        "tapaf_checkout": checkout,
    }


def solicitation_view(
    item: QuitConSolicitation,
    docs: list[QuitConSolicitationDocument] | None = None,
    db: Session | None = None,
) -> dict:
    uploaded = {d.doc_type for d in (docs or [])}
    return {
        "id": item.id,
        "status": item.status,
        "status_label": STATUS_LABELS.get(item.status, item.status),
        "status_notes": item.status_notes,
        "partner_user_id": item.partner_user_id,
        "contact_name": item.contact_name,
        "contact_email": item.contact_email,
        "contact_phone": item.contact_phone,
        "document": item.document,
        "person_type": item.person_type,
        "address": item.address,
        "occupation": item.occupation,
        "income_value": str(money(_dec(item.income_value))),
        "outstanding_balance": str(money(_dec(item.outstanding_balance))),
        "meses_restantes": item.meses_restantes,
        "registry_number": item.registry_number,
        "registry_office": item.registry_office,
        "property_type": item.property_type,
        "appraisal_value": str(money(_dec(item.appraisal_value))),
        "operational_service": item.operational_service,
        "contemplada": item.contemplada,
        "bem_faturado": item.bem_faturado,
        "parcelas_em_dia": item.parcelas_em_dia,
        "docs_complete": item.docs_complete,
        "quitacao_vp_amount": str(money(_dec(item.quitacao_vp_amount))),
        "proposal_id": item.proposal_id,
        "quitcon_operacao_id": item.quitcon_operacao_id,
        "required_docs": [{**d, "uploaded": d["code"] in uploaded} for d in REQUIRED_DOCS],
        "documents": [
            _document_link_view(db, d) if db else {
                "id": d.id,
                "doc_type": d.doc_type,
                "comment": d.comment,
                "document_id": d.document_id,
                "filename": None,
                "status": None,
                "created_at": d.created_at.isoformat() if d.created_at else None,
            }
            for d in (docs or [])
        ],
        "created_at": item.created_at.isoformat() if item.created_at else None,
        "can_create_sale": item.status == STATUS_APPROVED and not item.quitcon_operacao_id,
        **evaluation_meta(item.evaluation_json),
    }
