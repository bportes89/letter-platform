"""SDC commercial desk — Solicitação / Cadastro / Venda Cap Giro (legado Paulo)."""

from __future__ import annotations

from datetime import date
from decimal import Decimal
from json import dumps as json_dumps
from math import pow as math_pow

from fastapi import HTTPException, UploadFile
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.desk_solicitation_meta import evaluation_json_with_meta, evaluation_meta
from app.document_service import persist_upload
from app.models import Lead, Proposal, Quota, Role, SdcSolicitation, SdcSolicitationDocument, User
from app.network_service import PARTNER_NETWORK_ROLES
from app.services import money

DESK_ROLES = frozenset({
    Role.PLATFORM_ADMIN,
    Role.INTERNAL_STAFF,
    Role.MASTER_FRANCHISEE,
    Role.MANAGER,
    Role.PARTNER,
})

TIPOS_VEICULO = frozenset({"veiculo_leve", "veiculo_pesado", "maquina", "carro", "caminhao", "maquina_rural"})
TIPOS_IMOVEL = frozenset({"imovel", "casa", "lote", "imovel_rural", "imovel_comercial", "apartamento"})
IDADE_MAX = {
    "carro": 10,
    "caminhao": 15,
    "maquina_rural": 5,
    "veiculo_leve": 10,
    "veiculo_pesado": 15,
    "maquina": 5,
}
PORC_CREDITO_VEICULO = Decimal("0.50")
PORC_CREDITO_IMOVEL = Decimal("0.35")
VEICULO_PRAZO = 60
VEICULO_TAXA = Decimal("2.7")
IMOVEL_PRAZO = 180
IMOVEL_TAXA = Decimal("1.6")

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

TIPOS_LABEL = {
    "imovel": "Imóvel",
    "casa": "Imóvel",
    "lote": "Imóvel",
    "imovel_rural": "Imóvel",
    "imovel_comercial": "Imóvel",
    "apartamento": "Imóvel",
    "veiculo_leve": "Veículo leve",
    "veiculo_pesado": "Veículo pesado",
    "maquina": "Máquina",
    "carro": "Veículo leve",
    "caminhao": "Veículo pesado",
    "maquina_rural": "Máquina",
}


def assert_desk_access(user: User) -> None:
    if user.role not in DESK_ROLES:
        raise HTTPException(status_code=403, detail="Sem acesso à mesa comercial SDC")


def _dec(value) -> Decimal:
    return Decimal(str(value or 0))


def evaluate_sdc_desk(data: dict) -> dict:
    motivos: list[str] = []
    tipo_bem = str(data.get("asset_type") or data.get("tipo_bem") or "").strip().lower()
    is_veiculo = tipo_bem in TIPOS_VEICULO
    is_imovel = tipo_bem in TIPOS_IMOVEL
    if not tipo_bem or (not is_veiculo and not is_imovel):
        motivos.append("Tipo de bem inválido.")

    if not bool(data.get("asset_paid_off", data.get("bem_quitado", False))):
        motivos.append("O bem não está quitado.")
    if bool(data.get("asset_has_lien", data.get("bem_pendencia", False))):
        motivos.append("O bem possui pendência.")
    if not bool(data.get("docs_complete", data.get("documentacao_completa", False))):
        motivos.append("Documentação incompleta.")

    if is_veiculo:
        ano = int(data.get("asset_year") or data.get("ano_fabricacao") or 0)
        if ano <= 0:
            motivos.append("Informe o ano de fabricação do bem.")
        else:
            idade = date.today().year - ano
            limite = IDADE_MAX.get(tipo_bem, 0)
            if idade > limite:
                motivos.append(f"O bem excede a idade máxima permitida ({limite} anos).")

    valor = _dec(data.get("asset_value") or data.get("valor_bens") or 0)
    if valor <= 0:
        motivos.append("Informe o valor total dos bens.")

    if motivos:
        return {
            "viable": False,
            "motivos": motivos,
            "credito_estimado": "0.00",
            "parcela_estimada": "0.00",
            "prazo_meses": 0,
            "taxa_juros_mensal": "0.00",
            "tipo_categoria": "",
            "message": "NÃO FOI POSSÍVEL SEGUIR COM A SUA OPERAÇÃO",
        }

    if is_veiculo:
        porc, prazo, taxa = PORC_CREDITO_VEICULO, VEICULO_PRAZO, VEICULO_TAXA
        categoria = "veiculo"
    else:
        porc, prazo, taxa = PORC_CREDITO_IMOVEL, IMOVEL_PRAZO, IMOVEL_TAXA
        categoria = "imovel"

    credito = money(valor * porc)
    i = taxa / Decimal("100")
    parcela = credito * i / (Decimal("1") - Decimal(str(math_pow(float(1 + i), -prazo))))
    parcela = money(parcela)

    return {
        "viable": True,
        "motivos": [],
        "credito_estimado": str(credito),
        "parcela_estimada": str(parcela),
        "prazo_meses": prazo,
        "taxa_juros_mensal": str(taxa.quantize(Decimal("0.01"))),
        "tipo_categoria": categoria,
        "message": "Operação viável",
    }


def _is_admin(user: User) -> bool:
    return user.role in {Role.PLATFORM_ADMIN, Role.INTERNAL_STAFF, Role.MASTER_FRANCHISEE}


def _chain_user_ids(db: Session, user: User) -> list[str]:
    """Parceiro vê a própria cadeia (downline); admin não usa filtro."""
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


def list_solicitations(db: Session, user: User) -> list[SdcSolicitation]:
    assert_desk_access(user)
    q = select(SdcSolicitation).where(SdcSolicitation.organization_id == user.organization_id)
    if not _is_admin(user):
        chain = _chain_user_ids(db, user)
        q = q.where(SdcSolicitation.partner_user_id.in_(chain or [user.id]))
    return list(db.scalars(q.order_by(SdcSolicitation.created_at.desc())))


def list_documents(db: Session, solicitation_id: str) -> list[SdcSolicitationDocument]:
    return list(
        db.scalars(
            select(SdcSolicitationDocument)
            .where(SdcSolicitationDocument.solicitation_id == solicitation_id)
            .order_by(SdcSolicitationDocument.created_at.desc())
        )
    )


def get_solicitation(db: Session, user: User, solicitation_id: str) -> SdcSolicitation:
    assert_desk_access(user)
    item = db.scalar(
        select(SdcSolicitation).where(
            SdcSolicitation.id == solicitation_id,
            SdcSolicitation.organization_id == user.organization_id,
        )
    )
    if not item:
        raise HTTPException(status_code=404, detail="Solicitação SDC não encontrada")
    if not _is_admin(user) and item.partner_user_id not in _chain_user_ids(db, user):
        raise HTTPException(status_code=403, detail="Sem acesso a esta solicitação")
    return item


def store_solicitation(db: Session, user: User, payload: dict) -> SdcSolicitation:
    assert_desk_access(user)
    result = evaluate_sdc_desk(payload)
    if not result["viable"]:
        raise HTTPException(
            status_code=422,
            detail={"message": result["message"], "motivos": result["motivos"], "result": result},
        )
    partner_id = user.id if user.role in PARTNER_NETWORK_ROLES or user.role == Role.PARTNER else payload.get("partner_user_id") or user.id
    if _is_admin(user) and payload.get("partner_user_id"):
        partner_id = payload["partner_user_id"]

    item = SdcSolicitation(
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
        asset_value=money(_dec(payload["asset_value"])),
        asset_year=int(payload["asset_year"]) if payload.get("asset_year") else None,
        asset_paid_off=bool(payload.get("asset_paid_off", True)),
        asset_has_lien=bool(payload.get("asset_has_lien", False)),
        docs_complete=bool(payload.get("docs_complete", True)),
        credit_estimated=money(_dec(result["credito_estimado"])),
        installment_estimated=money(_dec(result["parcela_estimada"])),
        term_months=int(result["prazo_meses"]),
        interest_rate_monthly=money(_dec(result["taxa_juros_mensal"])),
        evaluation_json=evaluation_json_with_meta(
            result,
            channel="SDC_DESK",
            lead_id=str(payload.get("lead_id") or "").strip() or None,
        ),
    )
    db.add(item)
    db.flush()
    return item


def update_status(db: Session, user: User, item: SdcSolicitation, status: str, notes: str | None = None) -> SdcSolicitation:
    assert_desk_access(user)
    if not _is_admin(user):
        raise HTTPException(status_code=403, detail="Apenas operação LETTER altera o status do SDC")
    status = status.upper().strip()
    if status not in STATUS_LABELS:
        raise HTTPException(status_code=422, detail="Status inválido")
    if item.status in STATUS_TERMINAL and status != item.status:
        # allow admin override only from PENDING/UNDER_REVIEW typically; still allow change with notes
        pass
    item.status = status
    if notes is not None:
        item.status_notes = notes
    db.flush()
    return item


async def add_document(
    db: Session,
    user: User,
    item: SdcSolicitation,
    *,
    upload: UploadFile,
    doc_type: str,
    comment: str | None = None,
) -> SdcSolicitationDocument:
    assert_desk_access(user)
    if item.status in STATUS_TERMINAL:
        raise HTTPException(status_code=422, detail="Esta solicitação já está encerrada e não aceita mais documentos.")
    document = await persist_upload(upload, user, "sdc_solicitation", item.id, doc_type or "SDC_SUPPORT")
    document.status = "CLEAN"
    db.add(document)
    db.flush()
    row = SdcSolicitationDocument(
        organization_id=user.organization_id,
        solicitation_id=item.id,
        document_id=document.id,
        doc_type=(doc_type or "SDC_SUPPORT")[:80],
        comment=(comment or None),
        uploaded_by_id=user.id,
    )
    db.add(row)
    if not _is_admin(user) and item.status == STATUS_AWAITING_DOCS:
        item.status = STATUS_UNDER_REVIEW
    db.flush()
    return row


def create_sale_from_sdc(
    db: Session,
    user: User,
    item: SdcSolicitation,
    *,
    quota_id: str,
) -> dict:
    assert_desk_access(user)
    if item.status != STATUS_APPROVED:
        raise HTTPException(status_code=422, detail="Só SDCs Aprovados podem gerar cadastro de venda")
    if item.proposal_id:
        raise HTTPException(status_code=409, detail="Este SDC já possui venda vinculada")
    quota = db.scalar(
        select(Quota).where(Quota.id == quota_id, Quota.organization_id == user.organization_id)
    )
    if not quota:
        raise HTTPException(status_code=404, detail="Cota não encontrada")
    if quota.status not in {"AVAILABLE", "RESERVED"}:
        raise HTTPException(status_code=422, detail="Cota indisponível")

    lead = Lead(
        organization_id=user.organization_id,
        owner_id=item.partner_user_id or user.id,
        name=item.contact_name,
        phone=item.contact_phone or "00000000000",
        document=item.document,
        product_interest="SDC",
        status="QUALIFIED",
        source="SDC_DESK",
    )
    db.add(lead)
    db.flush()
    proposal = Proposal(
        organization_id=user.organization_id,
        lead_id=lead.id,
        product="SDC",
        requested_amount=item.credit_estimated,
        status="SUBMITTED",
        terms_json=json_dumps(
            {
                "sdc_solicitation_id": item.id,
                "quota_id": quota.id,
                "asset_type": item.asset_type,
                "asset_value": str(item.asset_value),
                "channel": "SDC_DESK",
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
    quota.status = "RESERVED"
    item.proposal_id = proposal.id
    item.quota_id = quota.id
    db.flush()
    return {"proposal_id": proposal.id, "lead_id": lead.id, "quota_id": quota.id}


def solicitation_view(item: SdcSolicitation, docs: list[SdcSolicitationDocument] | None = None) -> dict:
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
        "asset_type_label": TIPOS_LABEL.get(item.asset_type, item.asset_type),
        "asset_value": str(money(_dec(item.asset_value))),
        "asset_year": item.asset_year,
        "asset_paid_off": item.asset_paid_off,
        "asset_has_lien": item.asset_has_lien,
        "docs_complete": item.docs_complete,
        "credit_estimated": str(money(_dec(item.credit_estimated))),
        "installment_estimated": str(money(_dec(item.installment_estimated))),
        "term_months": item.term_months,
        "interest_rate_monthly": str(money(_dec(item.interest_rate_monthly))),
        "proposal_id": item.proposal_id,
        "quota_id": item.quota_id,
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
        **evaluation_meta(item.evaluation_json),
    }
