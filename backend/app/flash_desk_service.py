"""Flash Capital commercial desk — solicitação → docs/status → proposta + partes PJ."""

from __future__ import annotations

from decimal import Decimal
from json import dumps as json_dumps, loads as json_loads
from math import pow as math_pow

from fastapi import HTTPException, UploadFile
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.document_service import persist_upload
from app.flash_valid_lss_service import configure_flash_parties
from app.models import FlashSolicitation, FlashSolicitationDocument, Lead, Proposal, Role, User
from app.network_service import PARTNER_NETWORK_ROLES
from app.product_service import FLASH_CAPITAL_PRODUCT, calculate_flash_credit
from app.services import money

DESK_ROLES = frozenset({
    Role.PLATFORM_ADMIN,
    Role.INTERNAL_STAFF,
    Role.MASTER_FRANCHISEE,
    Role.MANAGER,
    Role.PARTNER,
})

TIPOS_VEICULO = frozenset({"veiculo", "veiculo_leve", "veiculo_pesado", "maquina", "carro", "caminhao", "VEHICLE"})
TIPOS_IMOVEL = frozenset({"imovel", "casa", "lote", "imovel_rural", "imovel_comercial", "apartamento", "REAL_ESTATE"})

MAX_LTV = Decimal("0.40")
PLATFORM_FEE_PCT = Decimal("10")
ITBI_PCT = Decimal("3")
RATE_MONTHLY = Decimal("2.5")
ALLOWED_TERMS = frozenset({36, 60})

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

DOCS_REAL_ESTATE = [
    {"code": "MATRICULA_ENOTARIADO", "label": "Matrícula atualizada (e-notariado)"},
    {"code": "LAUDO_AVALIACAO", "label": "Laudo de avaliação"},
    {"code": "SERASA", "label": "Consulta Serasa"},
    {"code": "BACEN", "label": "Consulta Bacen"},
]
DOCS_VEHICLE = [
    {"code": "FIPE_MOLICAR", "label": "Tabela FIPE ou Molicar"},
    {"code": "LAUDO_AVALIACAO", "label": "Laudo de avaliação"},
    {"code": "SERASA", "label": "Consulta Serasa"},
    {"code": "BACEN", "label": "Consulta Bacen"},
    {"code": "CRLV", "label": "CRLV (DETRAN prevalece)"},
]


def assert_desk_access(user: User) -> None:
    if user.role not in DESK_ROLES:
        raise HTTPException(status_code=403, detail="Sem acesso à mesa comercial Flash Capital")


def _dec(value) -> Decimal:
    return Decimal(str(value or 0))


def _category(asset_type: str) -> str:
    t = asset_type.strip().upper() if asset_type.isupper() else asset_type.strip().lower()
    if t in {"REAL_ESTATE"} or asset_type.strip().lower() in TIPOS_IMOVEL:
        return "REAL_ESTATE"
    if t in {"VEHICLE"} or asset_type.strip().lower() in TIPOS_VEICULO:
        return "VEHICLE"
    return ""


def _docs_for(category: str) -> list[dict]:
    return DOCS_REAL_ESTATE if category == "REAL_ESTATE" else DOCS_VEHICLE if category == "VEHICLE" else []


def _price_payment(principal: Decimal, rate_pct: Decimal, months: int) -> Decimal:
    i = rate_pct / Decimal("100")
    if i <= 0 or months <= 0:
        return money(Decimal("0"))
    parcela = principal * i / (Decimal("1") - Decimal(str(math_pow(float(1 + i), -months))))
    return money(parcela)


def evaluate_flash_desk(data: dict) -> dict:
    motivos: list[str] = []
    asset_type = str(data.get("asset_type") or "").strip()
    category = _category(asset_type)
    if not category:
        motivos.append("Tipo de bem inválido (use imóvel ou veículo).")

    if not bool(data.get("asset_paid_off", True)):
        motivos.append("O bem não está quitado.")
    if bool(data.get("asset_has_lien", False)):
        motivos.append("O bem possui pendência/gravame impeditivo.")
    if not bool(data.get("docs_complete", True)):
        motivos.append("Documentação incompleta (checklist Flash Capital).")

    valor = _dec(data.get("asset_value") or 0)
    if valor <= 0:
        motivos.append("Informe o valor do bem.")

    term = int(data.get("term_months") or 36)
    if term not in ALLOWED_TERMS:
        motivos.append("Prazo deve ser 36 ou 60 meses.")

    capital_source = str(data.get("capital_source") or "RETAIL").upper()
    if capital_source not in {"RETAIL", "INSTITUTIONAL"}:
        motivos.append("Origem do capital deve ser RETAIL (pool) ou INSTITUTIONAL (fundo).")

    max_principal = money(valor * MAX_LTV) if valor > 0 else money(Decimal("0"))
    requested = data.get("requested_amount")
    principal = money(_dec(requested)) if requested not in (None, "", 0, "0") else max_principal
    if principal <= 0 and valor > 0:
        motivos.append("Informe o valor solicitado (principal).")
    if valor > 0 and principal > max_principal:
        motivos.append(f"LTV máximo de 40% excedido; limite {max_principal}.")

    docs = _docs_for(category)
    if motivos:
        return {
            "viable": False,
            "motivos": motivos,
            "category": category,
            "required_docs": docs,
            "principal": "0.00",
            "ltv_percent": "0.00",
            "platform_fee": "0.00",
            "itbi_provision": "0.00",
            "net_payout": "0.00",
            "monthly_payment": "0.00",
            "term_months": term,
            "interest_rate_monthly": str(RATE_MONTHLY),
            "capital_source": capital_source,
            "message": "NÃO FOI POSSÍVEL SEGUIR COM A SUA OPERAÇÃO",
        }

    ltv = money(principal / valor * Decimal("100"))
    platform_fee = money(principal * PLATFORM_FEE_PCT / Decimal("100"))
    itbi = money(principal * ITBI_PCT / Decimal("100"))
    net = money(principal - platform_fee - itbi)
    parcela = _price_payment(principal, RATE_MONTHLY, term)

    return {
        "viable": True,
        "motivos": [],
        "category": category,
        "required_docs": docs,
        "principal": str(principal),
        "ltv_percent": str(ltv),
        "platform_fee": str(platform_fee),
        "itbi_provision": str(itbi),
        "net_payout": str(net),
        "partner_commission_base": str(net),
        "monthly_payment": str(parcela),
        "term_months": term,
        "interest_rate_monthly": str(RATE_MONTHLY),
        "capital_source": capital_source,
        "message": "Operação viável — Flash Capital",
    }


def _is_admin(user: User) -> bool:
    return user.role in {Role.PLATFORM_ADMIN, Role.INTERNAL_STAFF, Role.MASTER_FRANCHISEE}


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


def list_solicitations(db: Session, user: User) -> list[FlashSolicitation]:
    assert_desk_access(user)
    q = select(FlashSolicitation).where(FlashSolicitation.organization_id == user.organization_id)
    if not _is_admin(user):
        chain = _chain_user_ids(db, user)
        q = q.where(FlashSolicitation.partner_user_id.in_(chain or [user.id]))
    return list(db.scalars(q.order_by(FlashSolicitation.created_at.desc())))


def list_documents(db: Session, solicitation_id: str) -> list[FlashSolicitationDocument]:
    return list(
        db.scalars(
            select(FlashSolicitationDocument)
            .where(FlashSolicitationDocument.solicitation_id == solicitation_id)
            .order_by(FlashSolicitationDocument.created_at.desc())
        )
    )


def get_solicitation(db: Session, user: User, solicitation_id: str) -> FlashSolicitation:
    assert_desk_access(user)
    item = db.scalar(
        select(FlashSolicitation).where(
            FlashSolicitation.id == solicitation_id,
            FlashSolicitation.organization_id == user.organization_id,
        )
    )
    if not item:
        raise HTTPException(status_code=404, detail="Solicitação Flash Capital não encontrada")
    if not _is_admin(user) and item.partner_user_id not in _chain_user_ids(db, user):
        raise HTTPException(status_code=403, detail="Sem acesso a esta solicitação")
    return item


def store_solicitation(db: Session, user: User, payload: dict) -> FlashSolicitation:
    assert_desk_access(user)
    result = evaluate_flash_desk(payload)
    if not result["viable"]:
        raise HTTPException(
            status_code=422,
            detail={"message": result["message"], "motivos": result["motivos"], "result": result},
        )
    partner_id = user.id if user.role in PARTNER_NETWORK_ROLES or user.role == Role.PARTNER else payload.get("partner_user_id") or user.id
    if _is_admin(user) and payload.get("partner_user_id"):
        partner_id = payload["partner_user_id"]

    item = FlashSolicitation(
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
        asset_type=str(payload["asset_type"]).strip().lower(),
        asset_category=result["category"],
        asset_value=money(_dec(payload["asset_value"])),
        asset_year=int(payload["asset_year"]) if payload.get("asset_year") else None,
        asset_paid_off=bool(payload.get("asset_paid_off", True)),
        asset_has_lien=bool(payload.get("asset_has_lien", False)),
        docs_complete=bool(payload.get("docs_complete", True)),
        capital_source=result["capital_source"],
        term_months=int(result["term_months"]),
        principal=money(_dec(result["principal"])),
        ltv_percent=money(_dec(result["ltv_percent"])),
        platform_fee=money(_dec(result["platform_fee"])),
        itbi_provision=money(_dec(result["itbi_provision"])),
        net_payout=money(_dec(result["net_payout"])),
        installment_estimated=money(_dec(result["monthly_payment"])),
        interest_rate_monthly=money(_dec(result["interest_rate_monthly"])),
        evaluation_json=json_dumps(result, ensure_ascii=False),
        parties_json="{}",
    )
    db.add(item)
    db.flush()
    return item


def update_status(db: Session, user: User, item: FlashSolicitation, status: str, notes: str | None = None) -> FlashSolicitation:
    assert_desk_access(user)
    if not _is_admin(user):
        raise HTTPException(status_code=403, detail="Apenas operação LETTER altera o status do Flash Capital")
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
    item: FlashSolicitation,
    *,
    upload: UploadFile,
    doc_type: str,
    comment: str | None = None,
) -> FlashSolicitationDocument:
    assert_desk_access(user)
    if item.status in STATUS_TERMINAL:
        raise HTTPException(status_code=422, detail="Esta solicitação já está encerrada e não aceita mais documentos.")
    document = await persist_upload(upload, user, "flash_solicitation", item.id, doc_type or "FLASH_SUPPORT")
    document.status = "CLEAN"
    db.add(document)
    db.flush()
    row = FlashSolicitationDocument(
        organization_id=user.organization_id,
        solicitation_id=item.id,
        document_id=document.id,
        doc_type=(doc_type or "FLASH_SUPPORT")[:80],
        comment=(comment or None),
        uploaded_by_id=user.id,
    )
    db.add(row)
    if not _is_admin(user) and item.status == STATUS_AWAITING_DOCS:
        item.status = STATUS_UNDER_REVIEW
    db.flush()
    return row


def create_sale_from_flash(
    db: Session,
    user: User,
    item: FlashSolicitation,
    *,
    parties: dict | None = None,
) -> dict:
    assert_desk_access(user)
    if item.status != STATUS_APPROVED:
        raise HTTPException(status_code=422, detail="Só Flash Capital Aprovado pode gerar proposta")
    if item.proposal_id:
        raise HTTPException(status_code=409, detail="Este Flash Capital já possui proposta vinculada")

    lead = Lead(
        organization_id=user.organization_id,
        owner_id=item.partner_user_id or user.id,
        name=item.contact_name,
        phone=item.contact_phone or "00000000000",
        document=item.document,
        product_interest="FLASH_CREDIT",
        status="QUALIFIED",
        source="FLASH_DESK",
    )
    db.add(lead)
    db.flush()
    proposal = Proposal(
        organization_id=user.organization_id,
        lead_id=lead.id,
        product=FLASH_CAPITAL_PRODUCT,
        requested_amount=item.principal,
        status="SUBMITTED",
        terms_json=json_dumps(
            {
                "flash_solicitation_id": item.id,
                "asset_type": item.asset_type,
                "asset_category": item.asset_category,
                "asset_value": str(item.asset_value),
                "capital_source": item.capital_source,
                "term_months": item.term_months,
                "channel": "FLASH_DESK",
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

    calculation = calculate_flash_credit(
        db,
        user,
        proposal,
        asset_value=_dec(item.asset_value),
        capital_source=item.capital_source,
        term_months=int(item.term_months),
        ipca_annual=Decimal("0"),
    )

    route = None
    if parties and parties.get("borrower_cnpj"):
        route = configure_flash_parties(
            db,
            user,
            proposal,
            borrower_cnpj=str(parties["borrower_cnpj"]),
            property_owner_type=str(parties.get("property_owner_type") or "PJ_BORROWER"),
            property_owner_document=str(parties.get("property_owner_document") or parties["borrower_cnpj"]),
            legal_representative_document=parties.get("legal_representative_document"),
            liveness_reference=parties.get("liveness_reference"),
            qsa_representative_match=parties.get("qsa_representative_match"),
            consent_confirmation=bool(parties.get("consent_confirmation", False)),
        )
        item.parties_json = json_dumps(route, ensure_ascii=False)

    item.proposal_id = proposal.id
    db.flush()
    return {
        "proposal_id": proposal.id,
        "lead_id": lead.id,
        "calculation_id": calculation.id,
        "flash_route": route,
    }


def solicitation_view(item: FlashSolicitation, docs: list[FlashSolicitationDocument] | None = None) -> dict:
    uploaded = {d.doc_type for d in (docs or [])}
    required = _docs_for(item.asset_category)
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
        "asset_type": item.asset_type,
        "asset_category": item.asset_category,
        "asset_value": str(money(_dec(item.asset_value))),
        "asset_year": item.asset_year,
        "asset_paid_off": item.asset_paid_off,
        "asset_has_lien": item.asset_has_lien,
        "docs_complete": item.docs_complete,
        "capital_source": item.capital_source,
        "term_months": item.term_months,
        "principal": str(money(_dec(item.principal))),
        "ltv_percent": str(money(_dec(item.ltv_percent))),
        "platform_fee": str(money(_dec(item.platform_fee))),
        "itbi_provision": str(money(_dec(item.itbi_provision))),
        "net_payout": str(money(_dec(item.net_payout))),
        "installment_estimated": str(money(_dec(item.installment_estimated))),
        "interest_rate_monthly": str(money(_dec(item.interest_rate_monthly))),
        "proposal_id": item.proposal_id,
        "parties": json_loads(item.parties_json or "{}"),
        "required_docs": [
            {**d, "uploaded": d["code"] in uploaded} for d in required
        ],
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
        "can_create_sale": item.status == STATUS_APPROVED and not item.proposal_id,
    }
