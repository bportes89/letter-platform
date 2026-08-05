import hashlib
import json
import secrets
from datetime import UTC, datetime, timedelta
from uuid import uuid4

import pyotp
from fastapi import HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.security import create_token, decode_token, hash_password, verify_password
from app.models import AuthSession, KycCase, PasswordReset, ROLE_SCOPES, User, UserInvitation


def as_utc(value: datetime | None) -> datetime | None:
    if value is not None and value.tzinfo is None:
        return value.replace(tzinfo=UTC)
    return value


def token_hash(value: str) -> str:
    return hashlib.sha256(value.encode()).hexdigest()


def create_session_tokens(db: Session, user: User, user_agent: str | None, ip_address: str | None):
    session = AuthSession(
        user_id=user.id, organization_id=user.organization_id,
        refresh_token_hash=token_hash(secrets.token_urlsafe(32)), user_agent=user_agent,
        ip_address=ip_address, expires_at=datetime.now(UTC)+timedelta(days=settings.refresh_token_days),
    )
    db.add(session); db.flush()
    scopes=ROLE_SCOPES[user.role]
    access=create_token(user.id,"access",scopes,user.organization_id,session.id)
    refresh=create_token(user.id,"refresh",scopes,user.organization_id,session.id)
    session.refresh_token_hash=token_hash(refresh); user.last_login_at=datetime.now(UTC)
    return access,refresh,session


def rotate_refresh(db: Session, refresh_token: str):
    try: payload=decode_token(refresh_token)
    except Exception: raise HTTPException(status_code=401,detail="Refresh token inválido")
    if payload.get("type")!="refresh": raise HTTPException(status_code=401,detail="Tipo de token inválido")
    session=db.get(AuthSession,payload.get("sid"));user=db.get(User,payload.get("sub"))
    if not session or not user or not session.active or session.refresh_token_hash!=token_hash(refresh_token) or as_utc(session.expires_at)<=datetime.now(UTC): raise HTTPException(status_code=401,detail="Sessão expirada ou revogada")
    scopes=ROLE_SCOPES[user.role];access=create_token(user.id,"access",scopes,user.organization_id,session.id);refresh=create_token(user.id,"refresh",scopes,user.organization_id,session.id);session.refresh_token_hash=token_hash(refresh);session.last_seen_at=datetime.now(UTC)
    return access,refresh


def setup_mfa(user: User):
    secret=pyotp.random_base32();user.mfa_secret=secret
    return secret,pyotp.TOTP(secret).provisioning_uri(name=user.email,issuer_name="LETTER Platform")


def verify_mfa(user: User, otp: str) -> bool:
    return bool(user.mfa_secret and pyotp.TOTP(user.mfa_secret).verify(otp,valid_window=1))


def create_invitation(db:Session,user:User,email:str,role,branch_id:str|None):
    raw=secrets.token_urlsafe(32);invite=UserInvitation(organization_id=user.organization_id,branch_id=branch_id,invited_by_id=user.id,email=email.lower(),role=role,token_hash=token_hash(raw),expires_at=datetime.now(UTC)+timedelta(days=3));db.add(invite);return invite,raw


def accept_invitation(db:Session,raw:str,name:str,document:str|None,password:str):
    invite=db.scalar(select(UserInvitation).where(UserInvitation.token_hash==token_hash(raw),UserInvitation.status=="PENDING"))
    if not invite or as_utc(invite.expires_at)<=datetime.now(UTC): raise HTTPException(status_code=422,detail="Convite inválido ou expirado")
    if db.scalar(select(User).where(User.email==invite.email)): raise HTTPException(status_code=409,detail="E-mail já cadastrado")
    user=User(organization_id=invite.organization_id,branch_id=invite.branch_id,name=name,email=invite.email,document=document,password_hash=hash_password(password),role=invite.role);invite.status="ACCEPTED";invite.accepted_at=datetime.now(UTC);db.add(user);return user


def create_password_reset(db:Session,user:User):
    raw=secrets.token_urlsafe(32);item=PasswordReset(user_id=user.id,token_hash=token_hash(raw),expires_at=datetime.now(UTC)+timedelta(minutes=30));db.add(item);return raw


def confirm_password_reset(db:Session,raw:str,new_password:str):
    item=db.scalar(select(PasswordReset).where(PasswordReset.token_hash==token_hash(raw),PasswordReset.used_at.is_(None)))
    if not item or as_utc(item.expires_at)<=datetime.now(UTC): raise HTTPException(status_code=422,detail="Token inválido ou expirado")
    user=db.get(User,item.user_id);user.password_hash=hash_password(new_password);item.used_at=datetime.now(UTC)
    for session in db.scalars(select(AuthSession).where(AuthSession.user_id==user.id,AuthSession.active.is_(True))): session.active=False;session.revoked_at=datetime.now(UTC)


def create_kyc_case(user:User,subject_type:str,subject_id:str):
    return KycCase(organization_id=user.organization_id,subject_type=subject_type,subject_id=subject_id,provider="MOCK",external_id=f"mock_kyc_{uuid4().hex}")
