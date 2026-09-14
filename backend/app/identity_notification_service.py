"""E-mails transacionais de convite administrativo."""

from __future__ import annotations

from urllib.parse import quote

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.config import settings
from app.models import CommunicationTemplate, User, UserInvitation
from app.wallet_notification_service import _queue_and_deliver


ADMIN_INVITATION_KEY = "ADMIN_USER_INVITATION"


def invitation_accept_url(raw_token: str) -> str:
    base = (settings.public_app_url or "").rstrip("/")
    token = quote(raw_token, safe="")
    if not base:
        return f"/convite?token={token}"
    return f"{base}/convite?token={token}"


def _ensure_invitation_template(db: Session, actor: User) -> CommunicationTemplate:
    item = db.scalar(
        select(CommunicationTemplate).where(
            CommunicationTemplate.organization_id == actor.organization_id,
            CommunicationTemplate.key == ADMIN_INVITATION_KEY,
            CommunicationTemplate.channel == "EMAIL",
            CommunicationTemplate.active.is_(True),
        )
    )
    if item:
        return item
    current = db.scalar(
        select(CommunicationTemplate.version).where(
            CommunicationTemplate.organization_id == actor.organization_id,
            CommunicationTemplate.key == ADMIN_INVITATION_KEY,
            CommunicationTemplate.channel == "EMAIL",
        )
    ) or 0
    item = CommunicationTemplate(
        organization_id=actor.organization_id,
        key=ADMIN_INVITATION_KEY,
        channel="EMAIL",
        version=current + 1,
        subject="Convite de acesso — LETTER Platform",
        body=(
            "Olá!\n\n"
            "Você recebeu um convite para acessar a LETTER Platform como {{role}}.\n\n"
            "Para concluir seu cadastro, abra o link abaixo (válido por 3 dias):\n"
            "{{invite_link}}\n\n"
            "Se você não esperava este convite, ignore este e-mail.\n\n"
            "Equipe {{brand_name}}"
        ),
        purpose="TRANSACTIONAL",
        active=True,
    )
    db.add(item)
    db.flush()
    return item


def dispatch_admin_invitation_notification(
    db: Session,
    actor: User,
    invite: UserInvitation,
    raw_token: str,
) -> str | None:
    destination = (invite.email or "").strip().lower()
    if not destination or "@" not in destination:
        return "SKIPPED"
    template = _ensure_invitation_template(db, actor)
    result = _queue_and_deliver(
        db,
        actor,
        template=template,
        subject_type="USER_INVITATION",
        subject_id=invite.id,
        destination=destination,
        idempotency_key=f"admin-invite:{invite.id}",
        variables={
            "role": str(invite.role),
            "invite_link": invitation_accept_url(raw_token),
            "brand_name": settings.company_trade_name,
        },
    )
    if not result:
        return "FAILED"
    return str(result.get("status") or "QUEUED")
