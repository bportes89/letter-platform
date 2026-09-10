"""Auth do portal do fornecedor — token opaco em QuotaSupplier."""

from __future__ import annotations

import hashlib
import secrets
from datetime import UTC, datetime

from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db import get_db
from app.models import QuotaSupplier

bearer = HTTPBearer(auto_error=False)


def hash_portal_token(raw: str) -> str:
    return hashlib.sha256(raw.strip().encode("utf-8")).hexdigest()


def issue_portal_token(supplier: QuotaSupplier) -> str:
    raw = f"SUP-{secrets.token_urlsafe(24)}"
    supplier.portal_token_hash = hash_portal_token(raw)
    supplier.portal_token_created_at = datetime.now(UTC)
    return raw


def revoke_portal_token(supplier: QuotaSupplier) -> None:
    supplier.portal_token_hash = None
    supplier.portal_token_created_at = None


def find_supplier_by_portal_token(db: Session, raw: str) -> QuotaSupplier | None:
    token = (raw or "").strip()
    if not token:
        return None
    digest = hash_portal_token(token)
    return db.scalar(
        select(QuotaSupplier).where(
            QuotaSupplier.portal_token_hash == digest,
            QuotaSupplier.active.is_(True),
        )
    )


def get_current_supplier(
    credentials: HTTPAuthorizationCredentials | None = Depends(bearer),
    db: Session = Depends(get_db),
) -> QuotaSupplier:
    if credentials is None:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Token do portal obrigatório")
    supplier = find_supplier_by_portal_token(db, credentials.credentials)
    if not supplier:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Token do portal inválido")
    return supplier
