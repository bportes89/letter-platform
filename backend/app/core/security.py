from datetime import UTC, datetime, timedelta
from typing import Any
from uuid import uuid4

import jwt
from pwdlib import PasswordHash

from app.core.config import settings

password_hash = PasswordHash.recommended()
ALGORITHM = "HS256"  # Development default. Production adapter migrates to asymmetric KMS keys.


def hash_password(password: str) -> str:
    return password_hash.hash(password)


def verify_password(password: str, encoded: str) -> bool:
    return password_hash.verify(password, encoded)


def create_token(subject: str, token_type: str, scopes: list[str], organization_id: str, session_id: str | None = None) -> str:
    now = datetime.now(UTC)
    expires = now + (
        timedelta(minutes=settings.access_token_minutes)
        if token_type == "access"
        else timedelta(days=settings.refresh_token_days)
    )
    payload: dict[str, Any] = {
        "sub": subject,
        "type": token_type,
        "scopes": scopes,
        "organization_id": organization_id,
        "iat": now,
        "nbf": now,
        "exp": expires,
        "jti": str(uuid4()),
        "iss": "letter-platform",
        "aud": "letter-platform",
    }
    if session_id:
        payload["sid"] = session_id
    return jwt.encode(payload, settings.secret_key, algorithm=ALGORITHM)


def decode_token(token: str) -> dict[str, Any]:
    return jwt.decode(
        token,
        settings.secret_key,
        algorithms=[ALGORITHM],
        audience="letter-platform",
        issuer="letter-platform",
    )
