"""Vender minha cota — robô de oferta (regras fechadas com o dono / letter.zip)."""

from __future__ import annotations

import re
from decimal import Decimal

from fastapi import HTTPException, UploadFile
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.config import settings
from app.document_service import persist_upload
from app.models import (
    Administrator,
    CommunicationTemplate,
    Document,
    Organization,
    QuotaOfferRange,
    QuotaSellOffer,
    Role,
    User,
    uid,
)
from app.services import money
from app.storage_service import get_storage
from app.tax_communication_service import mock_deliver, queue_delivery

TIPOS_IMOVEL = frozenset({"imovel"})
TIPOS_VEICULO = frozenset({"autos", "pesados", "maquinas", "produtos", "servicos"})
TIPOS_LABEL = {
    "imovel": "Imóvel",
    "autos": "Autos",
    "pesados": "Pesados",
    "maquinas": "Máquinas",
    "produtos": "Produtos",
    "servicos": "Serviços",
}


def tipo_faixa(tipo_consorcio: str) -> str:
    t = (tipo_consorcio or "").strip().lower()
    if t in TIPOS_IMOVEL:
        return "imovel"
    if t in TIPOS_VEICULO:
        return "veiculo"
    return ""


def ensure_default_ranges(db: Session, organization_id: str) -> int:
    """Idempotente: popula faixas padrão se a org ainda não tiver."""
    existing = db.scalar(
        select(QuotaOfferRange.id).where(QuotaOfferRange.organization_id == organization_id).limit(1)
    )
    if existing:
        return 0

    pago = [
        ("ate 14,99%", Decimal("0"), Decimal("14.99")),
        ("15 a 19,99%", Decimal("15"), Decimal("19.99")),
        ("20 a 24,99%", Decimal("20"), Decimal("24.99")),
        ("25 a 29,99%", Decimal("25"), Decimal("29.99")),
        ("30 a 35%", Decimal("30"), Decimal("35")),
    ]
    prazos = [
        ("imovel", "120+ meses", 120, 9999, [20, 25, 30, 35, 40]),
        ("imovel", "90 a 119", 90, 119, [15, 20, 25, 30, 35]),
        ("imovel", "60 a 89", 60, 89, [12, 15, 20, 25, 30]),
        ("veiculo", "72+ meses", 72, 9999, [15, 20, 25, 30, 35]),
        ("veiculo", "50 a 71", 50, 71, [15, 20, 25, 30, 35]),
        ("veiculo", "36 a 49", 36, 49, [12, 15, 20, 25, 30]),
    ]
    order = 1
    created = 0
    for tipo, prazo_label, prazo_init, prazo_final, porcs in prazos:
        for k, (pago_label, pago_init, pago_final) in enumerate(pago):
            db.add(
                QuotaOfferRange(
                    id=uid(),
                    organization_id=organization_id,
                    active=True,
                    name=f"{tipo.capitalize()} {prazo_label} / pago {pago_label}",
                    sort_order=order,
                    tipo=tipo,
                    prazo_init=prazo_init,
                    prazo_final=prazo_final,
                    pago_init=pago_init,
                    pago_final=pago_final,
                    porc=Decimal(str(porcs[k])),
                )
            )
            order += 1
            created += 1
    db.flush()
    return created


def default_organization_id(db: Session) -> str:
    org = db.scalar(select(Organization).where(Organization.kind == "HEADQUARTERS"))
    if not org:
        org = db.scalar(select(Organization).limit(1))
    if not org:
        raise HTTPException(status_code=503, detail="Organização não configurada")
    ensure_default_ranges(db, org.id)
    return org.id


def evaluate_offer(
    db: Session,
    *,
    organization_id: str,
    tipo_consorcio: str,
    credit_value: Decimal,
    paid_value: Decimal,
    term_months: int,
    contemplated: bool,
) -> dict:
    motivos: list[str] = []
    faixa_tipo = tipo_faixa(tipo_consorcio)
    credit = money(credit_value)
    paid = money(paid_value)

    if not faixa_tipo:
        motivos.append("Tipo de consórcio inválido.")
    if credit <= 0:
        motivos.append("Informe o valor atual do crédito.")
    if term_months <= 0:
        motivos.append("Informe o prazo contratado da cota.")
    if not contemplated:
        motivos.append("Só compramos cotas já contempladas.")

    if motivos:
        return {
            "viable": False,
            "motivos": motivos,
            "tipo_faixa": faixa_tipo,
            "credit_value": str(credit),
            "paid_percent": "0.00",
            "offer_percent": "0.00",
            "offer_value": "0.00",
        }

    paid_pct = money((paid / credit) * Decimal("100")) if credit > 0 else Decimal("0")

    ranges = list(
        db.scalars(
            select(QuotaOfferRange)
            .where(
                QuotaOfferRange.organization_id == organization_id,
                QuotaOfferRange.active.is_(True),
                QuotaOfferRange.tipo == faixa_tipo,
                QuotaOfferRange.prazo_init <= term_months,
                QuotaOfferRange.prazo_final >= term_months,
                QuotaOfferRange.pago_final >= paid_pct,
            )
            .order_by(QuotaOfferRange.pago_final.asc(), QuotaOfferRange.sort_order.asc())
        )
    )
    match = ranges[0] if ranges else None

    if not match:
        teto = db.scalar(
            select(QuotaOfferRange.pago_final)
            .where(
                QuotaOfferRange.organization_id == organization_id,
                QuotaOfferRange.active.is_(True),
                QuotaOfferRange.tipo == faixa_tipo,
                QuotaOfferRange.prazo_init <= term_months,
                QuotaOfferRange.prazo_final >= term_months,
            )
            .order_by(QuotaOfferRange.pago_final.desc())
            .limit(1)
        )
        if teto is not None:
            motivos.append(
                f"Cotas com mais de {money(Decimal(str(teto)))}% do crédito pago não são compradas."
            )
        else:
            motivos.append("O prazo contratado informado está fora das faixas de compra.")
        return {
            "viable": False,
            "motivos": motivos,
            "tipo_faixa": faixa_tipo,
            "credit_value": str(credit),
            "paid_percent": str(paid_pct),
            "offer_percent": "0.00",
            "offer_value": "0.00",
        }

    porc = money(Decimal(str(match.porc)))
    offer_value = money(credit * porc / Decimal("100"))
    return {
        "viable": True,
        "motivos": [],
        "tipo_faixa": faixa_tipo,
        "credit_value": str(credit),
        "paid_percent": str(paid_pct),
        "offer_percent": str(porc),
        "offer_value": str(offer_value),
        "range_id": match.id,
        "range_name": match.name,
    }


def _digits(value: str) -> str:
    return re.sub(r"\D", "", value or "")


def validate_contact(*, name: str, email: str, phone: str) -> list[str]:
    errors: list[str] = []
    if not (name or "").strip():
        errors.append("Digite o nome!")
    if "@" not in (email or "") or "." not in (email or "").split("@")[-1]:
        errors.append("Digite um e-mail válido!")
    if len(_digits(phone)) < 10:
        errors.append("Digite um telefone válido!")
    return errors


def bootstrap_page(db: Session) -> dict:
    org_id = default_organization_id(db)
    admins = list(
        db.scalars(
            select(Administrator).where(
                Administrator.authorization_status.in_(
                    {"AUTHORIZED", "APPROVED", "ACTIVE", "APPROVED_MANUALLY"}
                )
            ).order_by(Administrator.name.asc())
        )
    )
    return {
        "title": "Vender minha cota",
        "administrators": [{"id": a.id, "name": a.name} for a in admins],
        "tipos": [{"id": k, "label": v} for k, v in TIPOS_LABEL.items()],
        "rules_summary": (
            "Só cotas contempladas. Percentual sobre o crédito. "
            "Pago acima de 35% do crédito → recusa. "
            "Imóvel: prazo mínimo 60 meses. Autos/demais: mínimo 36 meses (72 meses entra na faixa 72+)."
        ),
        "organization_id": org_id,
    }


def store_offer(
    db: Session,
    *,
    administrator_id: str | None,
    tipo_consorcio: str,
    credit_value: Decimal,
    paid_value: Decimal,
    outstanding_balance: Decimal,
    term_months: int,
    contemplated: bool,
    contact_name: str,
    contact_email: str,
    contact_phone: str,
    document: str | None,
    person_type: str,
    partner_referral_code: str | None,
) -> dict:
    org_id = default_organization_id(db)
    result = evaluate_offer(
        db,
        organization_id=org_id,
        tipo_consorcio=tipo_consorcio,
        credit_value=credit_value,
        paid_value=paid_value,
        term_months=term_months,
        contemplated=contemplated,
    )
    if not result["viable"]:
        raise HTTPException(
            status_code=422,
            detail={"message": "NÃO FOI POSSÍVEL SEGUIR COM A SUA OFERTA", "motivos": result["motivos"]},
        )

    errors = validate_contact(name=contact_name, email=contact_email, phone=contact_phone)
    if errors:
        raise HTTPException(status_code=422, detail={"message": "Dados de contato incompletos", "motivos": errors})

    if administrator_id and not db.get(Administrator, administrator_id):
        raise HTTPException(status_code=404, detail="Administradora não encontrada")

    offer = QuotaSellOffer(
        organization_id=org_id,
        administrator_id=administrator_id or None,
        partner_referral_code=(partner_referral_code or "").strip() or None,
        status="AWAITING_STATEMENT",
        contact_name=contact_name.strip(),
        contact_email=contact_email.strip().lower(),
        contact_phone=_digits(contact_phone),
        document=_digits(document or "") or None,
        person_type=(person_type or "PF").upper()[:2],
        tipo_consorcio=tipo_consorcio.strip().lower(),
        credit_value=Decimal(result["credit_value"]),
        paid_value=money(paid_value),
        outstanding_balance=money(outstanding_balance),
        term_months=term_months,
        contemplated=True,
        paid_percent=Decimal(result["paid_percent"]),
        offer_percent=Decimal(result["offer_percent"]),
        offer_value=Decimal(result["offer_value"]),
    )
    db.add(offer)
    db.flush()
    return {
        "offer_id": offer.id,
        "status": offer.status,
        "offer_value": str(money(Decimal(str(offer.offer_value)))),
        "offer_percent": str(money(Decimal(str(offer.offer_percent)))),
        "message": "Oferta enviada com sucesso! Você já pode anexar o extrato da cota abaixo.",
        "link_dashboard": "/login",
        "result": result,
    }


def org_ops_user(db: Session, organization_id: str) -> User | None:
    return db.scalar(
        select(User)
        .where(
            User.organization_id == organization_id,
            User.active.is_(True),
            User.role.in_([Role.PLATFORM_ADMIN, Role.INTERNAL_STAFF, Role.MASTER_FRANCHISEE]),
        )
        .order_by(User.created_at.asc())
        .limit(1)
    )


def _ensure_email_template(
    db: Session, user: User, *, key: str, subject: str, body: str,
) -> CommunicationTemplate:
    item = db.scalar(
        select(CommunicationTemplate).where(
            CommunicationTemplate.organization_id == user.organization_id,
            CommunicationTemplate.key == key,
            CommunicationTemplate.channel == "EMAIL",
            CommunicationTemplate.active.is_(True),
        )
    )
    if item:
        return item
    current = db.scalar(
        select(CommunicationTemplate.version).where(
            CommunicationTemplate.organization_id == user.organization_id,
            CommunicationTemplate.key == key,
            CommunicationTemplate.channel == "EMAIL",
        )
    ) or 0
    item = CommunicationTemplate(
        organization_id=user.organization_id,
        key=key,
        channel="EMAIL",
        version=current + 1,
        subject=subject,
        body=body,
        purpose="TRANSACTIONAL",
        active=True,
    )
    db.add(item)
    db.flush()
    return item


def notify_new_offer(db: Session, offer: QuotaSellOffer) -> dict:
    """Fila e-mails mock (admin + cliente). Nunca bloqueia a oferta."""
    user = org_ops_user(db, offer.organization_id)
    if not user:
        return {"sent": False, "reason": "no_ops_user"}
    variables = {
        "name": offer.contact_name,
        "email": offer.contact_email,
        "phone": offer.contact_phone,
        "offer_value": str(money(Decimal(str(offer.offer_value)))),
        "offer_percent": str(money(Decimal(str(offer.offer_percent)))),
        "credit_value": str(money(Decimal(str(offer.credit_value)))),
        "tipo": TIPOS_LABEL.get(offer.tipo_consorcio, offer.tipo_consorcio),
        "offer_id": offer.id,
    }
    admin_tpl = _ensure_email_template(
        db, user,
        key="VENDER_COTA_ADMIN",
        subject="Nova oferta — Vender minha cota ({{name}})",
        body=(
            "Nova oferta pública recebida.\n"
            "Cliente: {{name}} · {{email}} · {{phone}}\n"
            "Tipo: {{tipo}} · Crédito R$ {{credit_value}}\n"
            "Oferta Letter: R$ {{offer_value}} ({{offer_percent}}%)\n"
            "ID: {{offer_id}}\n"
            "Painel: /modules/vender-cota"
        ),
    )
    client_tpl = _ensure_email_template(
        db, user,
        key="VENDER_COTA_CLIENT",
        subject="Recebemos sua oferta de cota — LETTER",
        body=(
            "Olá {{name}},\n\n"
            "Recebemos sua proposta de venda de cota contemplada.\n"
            "Prévia da oferta Letter: R$ {{offer_value}} ({{offer_percent}}% do crédito).\n"
            "Próximo passo: anexe o extrato da cota na página ou no escritório.\n\n"
            "LETTER"
        ),
    )
    admin_dest = (settings.company_email or "comercial@letter.app.br").strip().lower()
    deliveries = []
    for template, dest in (
        (admin_tpl, admin_dest),
        (client_tpl, offer.contact_email),
    ):
        try:
            delivery, created = queue_delivery(
                db, user, template,
                subject_type="QUOTA_SELL_OFFER",
                subject_id=offer.id,
                destination=dest,
                idempotency_key=f"vmc-{offer.id}-{template.key}-{dest}",
                variables=variables,
            )
            if created:
                mock_deliver(delivery)
            deliveries.append({"key": template.key, "destination": delivery.destination_masked, "status": delivery.status})
        except Exception:
            deliveries.append({"key": template.key, "destination": dest, "status": "FAILED"})
    return {"sent": True, "deliveries": deliveries}


async def attach_statement(
    db: Session,
    *,
    offer: QuotaSellOffer,
    upload: UploadFile,
    uploader: User,
) -> QuotaSellOffer:
    document = await persist_upload(upload, uploader, "quota_sell_offer", offer.id, "QUOTA_STATEMENT")
    document.status = "CLEAN"
    db.add(document)
    db.flush()
    offer.statement_document_id = document.id
    if offer.status in {"AWAITING_STATEMENT", "UNDER_REVIEW"}:
        offer.status = "UNDER_REVIEW"
    db.flush()
    return offer


def statement_payload(db: Session, offer: QuotaSellOffer) -> tuple[bytes, str, str]:
    if not offer.statement_document_id:
        raise HTTPException(status_code=404, detail="Extrato ainda não anexado")
    doc = db.get(Document, offer.statement_document_id)
    if not doc or doc.organization_id != offer.organization_id:
        raise HTTPException(status_code=404, detail="Documento do extrato não encontrado")
    try:
        data = get_storage().get(doc.storage_key)
    except FileNotFoundError as exc:
        raise HTTPException(status_code=404, detail="Arquivo do extrato não encontrado no storage") from exc
    name = (doc.filename or "extrato.pdf").lower()
    media = "application/pdf"
    if name.endswith(".png"):
        media = "image/png"
    elif name.endswith(".jpg") or name.endswith(".jpeg"):
        media = "image/jpeg"
    return data, doc.filename, media


def list_ranges(db: Session, organization_id: str) -> list[QuotaOfferRange]:
    ensure_default_ranges(db, organization_id)
    return list(
        db.scalars(
            select(QuotaOfferRange)
            .where(QuotaOfferRange.organization_id == organization_id)
            .order_by(QuotaOfferRange.sort_order.asc(), QuotaOfferRange.created_at.asc())
        )
    )


def list_offers(db: Session, organization_id: str) -> list[QuotaSellOffer]:
    return list(
        db.scalars(
            select(QuotaSellOffer)
            .where(QuotaSellOffer.organization_id == organization_id)
            .order_by(QuotaSellOffer.created_at.desc())
        )
    )


def range_view(item: QuotaOfferRange) -> dict:
    return {
        "id": item.id,
        "active": item.active,
        "name": item.name,
        "sort_order": item.sort_order,
        "tipo": item.tipo,
        "prazo_init": item.prazo_init,
        "prazo_final": item.prazo_final,
        "pago_init": str(money(Decimal(str(item.pago_init)))),
        "pago_final": str(money(Decimal(str(item.pago_final)))),
        "porc": str(money(Decimal(str(item.porc)))),
    }


def offer_view(item: QuotaSellOffer, admin: Administrator | None = None, statement: Document | None = None) -> dict:
    return {
        "id": item.id,
        "status": item.status,
        "contact_name": item.contact_name,
        "contact_email": item.contact_email,
        "contact_phone": item.contact_phone,
        "document": item.document,
        "person_type": item.person_type,
        "tipo_consorcio": item.tipo_consorcio,
        "tipo_label": TIPOS_LABEL.get(item.tipo_consorcio, item.tipo_consorcio),
        "administrator_id": item.administrator_id,
        "administrator_name": admin.name if admin else None,
        "credit_value": str(money(Decimal(str(item.credit_value)))),
        "paid_value": str(money(Decimal(str(item.paid_value)))),
        "outstanding_balance": str(money(Decimal(str(item.outstanding_balance)))),
        "term_months": item.term_months,
        "contemplated": item.contemplated,
        "paid_percent": str(money(Decimal(str(item.paid_percent)))),
        "offer_percent": str(money(Decimal(str(item.offer_percent)))),
        "offer_value": str(money(Decimal(str(item.offer_value)))),
        "partner_referral_code": item.partner_referral_code,
        "notes": item.notes,
        "statement_document_id": item.statement_document_id,
        "statement_filename": statement.filename if statement else None,
        "created_at": item.created_at.isoformat() if item.created_at else None,
    }
