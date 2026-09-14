"""Listagem administrativa de usuários com serialização tolerante a dados legados."""

from __future__ import annotations

import logging

from pydantic import EmailStr, TypeAdapter, ValidationError
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import Role, User
from app.schemas import UserView

logger = logging.getLogger("letter.identity")
_email_adapter = TypeAdapter(EmailStr)


def _safe_email(email: str | None, user_id: str) -> str:
    candidate = (email or "").strip()
    try:
        return str(_email_adapter.validate_python(candidate))
    except Exception:
        return f"legacy-{user_id[:8]}@example.com"


def safe_user_view(user: User) -> UserView:
    try:
        return UserView.model_validate(user)
    except ValidationError as exc:
        logger.warning(
            "admin_user_view_fallback",
            extra={"user_id": user.id, "email": user.email, "errors": exc.errors()},
        )
        role = user.role if isinstance(user.role, Role) else Role.CLIENT
        return UserView(
            id=user.id,
            organization_id=user.organization_id,
            branch_id=user.branch_id,
            name=(user.name or "Usuário").strip() or "Usuário",
            email=_safe_email(user.email, user.id),
            role=role,
            active=bool(user.active),
            mfa_enabled=bool(user.mfa_enabled),
            last_login_at=user.last_login_at,
        )


def list_organization_users(db: Session, organization_id: str) -> list[UserView]:
    rows = list(
        db.scalars(
            select(User)
            .where(User.organization_id == organization_id)
            .order_by(User.created_at.desc())
        )
    )
    return [safe_user_view(row) for row in rows]
