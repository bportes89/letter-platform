"""E-mail OTP challenge after password verification at login."""

from __future__ import annotations

import secrets
from datetime import UTC, datetime, timedelta

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.config import settings
from app.email_delivery_service import send_transactional_email
from app.identity_service import token_hash
from app.models import LoginEmailOtp, User

OTP_TTL_MINUTES = 10


def _generate_code() -> str:
    return f"{secrets.randbelow(1_000_000):06d}"


def issue_login_email_otp(db: Session, user: User) -> None:
    raw = _generate_code()
    now = datetime.now(UTC)
    for item in db.scalars(select(LoginEmailOtp).where(LoginEmailOtp.user_id == user.id, LoginEmailOtp.used_at.is_(None))):
        item.used_at = now
    challenge = LoginEmailOtp(
        user_id=user.id,
        code_hash=token_hash(raw),
        expires_at=now + timedelta(minutes=OTP_TTL_MINUTES),
    )
    db.add(challenge)
    subject = "Código de acesso LETTER"
    body = (
        f"Olá, {user.name}.\n\n"
        f"Seu código de verificação para entrar na plataforma LETTER é: {raw}\n\n"
        f"Ele expira em {OTP_TTL_MINUTES} minutos. Se você não tentou entrar, ignore este e-mail.\n"
    )
    send_transactional_email(user.email, subject, body)


def _active_email_otp(db: Session, user: User, code: str) -> LoginEmailOtp | None:
    now = datetime.now(UTC)
    item = db.scalar(
        select(LoginEmailOtp)
        .where(
            LoginEmailOtp.user_id == user.id,
            LoginEmailOtp.code_hash == token_hash(code.strip()),
            LoginEmailOtp.used_at.is_(None),
        )
        .order_by(LoginEmailOtp.created_at.desc())
    )
    if not item:
        return None
    expires = item.expires_at
    if expires.tzinfo is None:
        expires = expires.replace(tzinfo=UTC)
    if expires <= now:
        return None
    return item


def email_login_otp_satisfied(db: Session, user: User, code: str | None) -> bool:
    if not settings.login_email_otp:
        return True
    if not code or len(code.strip()) != 6:
        return False
    return _active_email_otp(db, user, code) is not None


def consume_login_email_otp(db: Session, user: User, code: str | None) -> None:
    if not settings.login_email_otp or not code:
        return
    item = _active_email_otp(db, user, code)
    if item:
        item.used_at = datetime.now(UTC)
