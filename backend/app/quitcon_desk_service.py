"""QuitCon commercial desk — solicitação → docs/status → operação AGUARDANDO_TAPAF."""

from __future__ import annotations

from decimal import Decimal
from json import dumps as json_dumps

from fastapi import HTTPException, UploadFile
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.desk_solicitation_meta import evaluation_json_with_meta, evaluation_meta
from app.document_service import persist_upload
from app.models import (
    CommissionRule,
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


def _is_admin(user: User) -> bool:
    return user.role in {Role.PLATFORM_ADMIN, Role.INTERNAL_STAFF, Role.MASTER_FRANCHISEE}


def evaluate_quitcon_desk(data: dict) -> dict:
    motivos: list[str] = []
    saldo = _dec(data.get("outstanding_balance") or 0)
    if saldo <= 0:
        motivos.append("Informe o saldo devedor bruto da cota.")

    meses = int(data.get("meses_restantes") or 48)
    if meses <= 0 or meses > 240:
        motivos.append("Meses restantes inválidos.")

    registry_office = str(data.get("registry_office") or data.get("administrator_name") or "").strip()
    if not registry_office:
        motivos.append("Informe a administradora (whitelist doc253).")

    registry_number = str(data.get("registry_number") or "").strip()
    if not registry_number:
        motivos.append("Informe o número/grupo da cota (registry_number).")

    if not bool(data.get("docs_complete", True)):
        motivos.append("Documentação incompleta.")

    contemplada = bool(data.get("contemplada", True))
    bem_faturado = bool(data.get("bem_faturado", True))
    parcelas_em_dia = bool(data.get("parcelas_em_dia", True))
    operational_service = bool(data.get("operational_service", False))

    engine = EngineQuitConLetter()
    if motivos and saldo <= 0:
        return {
            "viable": False,
            "motivos": motivos,
            "required_docs": REQUIRED_DOCS,
            "snapshot": None,
            "valor_presente_quitacao": "0.00",
            "custos_entrada": None,
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
        meses_restantes=int(payload.get("meses_restantes") or 48),
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
            result,
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
    if item.status in STATUS_TERMINAL:
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


def solicitation_view(item: QuitConSolicitation, docs: list[QuitConSolicitationDocument] | None = None) -> dict:
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
            {
                "id": d.id,
                "doc_type": d.doc_type,
                "comment": d.comment,
                "document_id": d.document_id,
                "created_at": d.created_at.isoformat() if d.created_at else None,
            }
            for d in (docs or [])
        ],
        "created_at": item.created_at.isoformat() if item.created_at else None,
        "can_create_sale": item.status == STATUS_APPROVED and not item.quitcon_operacao_id,
        **evaluation_meta(item.evaluation_json),
    }
