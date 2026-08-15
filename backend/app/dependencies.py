from collections.abc import Callable

import jwt
from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy.orm import Session

from app.core.security import decode_token
from app.db import get_db
from app.models import AuthSession, ROLE_SCOPES, User
from datetime import UTC, datetime

bearer = HTTPBearer(auto_error=False)


def as_utc(value: datetime | None) -> datetime | None:
    """Normaliza timestamps do SQLite, que podem voltar sem timezone."""
    if value is not None and value.tzinfo is None:
        return value.replace(tzinfo=UTC)
    return value


def get_current_user(
    credentials: HTTPAuthorizationCredentials | None = Depends(bearer),
    db: Session = Depends(get_db),
) -> User:
    if credentials is None:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Autenticação obrigatória")
    try:
        payload = decode_token(credentials.credentials)
    except jwt.PyJWTError:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Token inválido ou expirado")
    if payload.get("type") != "access":
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Tipo de token inválido")
    user = db.get(User, payload.get("sub"))
    if not user or not user.active:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Usuário inativo ou inexistente")
    if user.organization_id != payload.get("organization_id"):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Contexto organizacional inválido")
    session_id = payload.get("sid")
    session = db.get(AuthSession, session_id) if session_id else None
    if not session or not session.active or as_utc(session.expires_at) <= datetime.now(UTC):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Sessão revogada ou expirada")
    session.last_seen_at = datetime.now(UTC)
    return user


def require_scope(required: str) -> Callable:
    def checker(user: User = Depends(get_current_user)) -> User:
        scopes = ROLE_SCOPES[user.role]
        if "*" not in scopes and required not in scopes:
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=f"Escopo obrigatório: {required}")
        return user
    return checker


def require_step_up(user: User = Depends(get_current_user), credentials: HTTPAuthorizationCredentials | None = Depends(bearer), db: Session = Depends(get_db)) -> User:
    payload = decode_token(credentials.credentials) if credentials else {}
    session = db.get(AuthSession, payload.get("sid"))
    if not session or not session.step_up_until or as_utc(session.step_up_until) <= datetime.now(UTC):
        raise HTTPException(status_code=status.HTTP_428_PRECONDITION_REQUIRED, detail="Autenticação reforçada obrigatória")
    return user
