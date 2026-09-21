"""Login do administrador da plataforma (demo → e-mail corporativo)."""

from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.security import verify_password
from app.models import Role, User

LEGACY_PLATFORM_ADMIN_EMAIL = "admin@letter.com.br"


def platform_admin_login_email() -> str:
    return (settings.platform_admin_email or "comercial@letter.app.br").strip().lower()


def authenticate_platform_login(db: Session, email: str, password: str) -> User | None:
    """Resolve login corporativo e senha, inclusive alias comercial → admin legado."""
    normalized = email.strip().lower()
    user = db.scalar(select(User).where(User.email == normalized))
    if user and user.active and verify_password(password, user.password_hash):
        return user
    if normalized != platform_admin_login_email():
        return None
    legacy = db.scalar(
        select(User).where(User.email == LEGACY_PLATFORM_ADMIN_EMAIL, User.role == Role.PLATFORM_ADMIN),
    )
    if legacy and legacy.active and verify_password(password, legacy.password_hash):
        return legacy
    return None
