"""Listagem e criação administrativa de usuários."""

from __future__ import annotations

import logging

from fastapi import HTTPException
from pydantic import EmailStr, TypeAdapter, ValidationError
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.account_uniqueness import ensure_unique_account_fields, find_user_by_email
from app.admin_permissions import (
    effective_modules_for_view,
    normalize_permission_keys,
    parse_user_permissions,
    serialize_permissions,
    user_has_full_access,
    validate_admin_password,
)
from app.core.security import hash_password
from app.models import Role, User
from app.schemas import AdminUserCreate, UserView

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
        return UserView(
            id=user.id,
            organization_id=user.organization_id,
            branch_id=user.branch_id,
            name=user.name,
            email=user.email,
            role=user.role,
            active=bool(user.active),
            mfa_enabled=bool(user.mfa_enabled),
            access_all=user_has_full_access(user),
            permissions=parse_user_permissions(user),
            effective_modules=effective_modules_for_view(user),
            last_login_at=user.last_login_at,
        )
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
            access_all=user_has_full_access(user),
            permissions=parse_user_permissions(user),
            effective_modules=effective_modules_for_view(user),
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


def create_admin_user(db: Session, actor: User, payload: AdminUserCreate) -> User:
    if actor.role not in {Role.PLATFORM_ADMIN, Role.INTERNAL_STAFF}:
        raise HTTPException(status_code=403, detail="Sem permissão para criar administradores")
    email = str(payload.email).strip().lower()
    if find_user_by_email(db, email):
        raise HTTPException(status_code=409, detail="E-mail já cadastrado")
    validate_admin_password(payload.password)
    phone = (payload.phone or "").strip() or None
    permissions = normalize_permission_keys(payload.permissions)
    if payload.access_all:
        role = Role.PLATFORM_ADMIN
        access_all = True
        permissions_blob = None
    else:
        if not permissions:
            raise HTTPException(status_code=422, detail="Selecione ao menos uma permissão ou marque Acesso Total.")
        role = Role.INTERNAL_STAFF
        access_all = False
        permissions_blob = serialize_permissions(permissions)
    user = User(
        organization_id=actor.organization_id,
        branch_id=payload.branch_id,
        name=payload.name.strip(),
        email=email,
        phone=phone,
        password_hash=hash_password(payload.password),
        role=role,
        active=True,
        access_all=access_all,
        permissions_json=permissions_blob,
    )
    ensure_unique_account_fields(db, user)
    db.add(user)
    db.flush()
    return user


def apply_user_access_update(
    user: User,
    *,
    access_all: bool | None = None,
    permissions: list[str] | None = None,
) -> None:
    if access_all is None and permissions is None:
        return
    if access_all is True:
        user.access_all = True
        user.role = Role.PLATFORM_ADMIN
        user.permissions_json = None
        return
    if access_all is False:
        user.access_all = False
        if user.role == Role.PLATFORM_ADMIN:
            user.role = Role.INTERNAL_STAFF
    if permissions is not None:
        normalized = normalize_permission_keys(permissions)
        if not normalized and not user.access_all:
            raise HTTPException(status_code=422, detail="Selecione ao menos uma permissão ou marque Acesso Total.")
        user.permissions_json = serialize_permissions(normalized)
        user.access_all = False
        if user.role == Role.PLATFORM_ADMIN:
            user.role = Role.INTERNAL_STAFF
