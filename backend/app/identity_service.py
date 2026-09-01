import hashlib
import secrets
from datetime import UTC, datetime, timedelta
from uuid import uuid4

import pyotp
from fastapi import HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.security import create_token, decode_token, hash_password, verify_password
from app.models import AuthSession, KycCase, PasswordReset, ROLE_SCOPES, Role, User, UserInvitation
from app.network_service import PARTNER_NETWORK_ROLES, attach_partner_under_sponsor


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


def create_partner_invitation(db: Session, inviter: User, email: str, role: Role) -> tuple[UserInvitation, str]:
    if inviter.role not in PARTNER_NETWORK_ROLES:
        raise HTTPException(status_code=403, detail="Perfil sem permissão para convidar parceiros")
    if role not in PARTNER_NETWORK_ROLES:
        raise HTTPException(status_code=422, detail="Parceiros só podem convidar perfis comerciais da rede")
    normalized = email.strip().lower()
    if db.scalar(select(User).where(User.email == normalized)):
        raise HTTPException(status_code=409, detail="E-mail já cadastrado")
    pending = db.scalar(select(UserInvitation).where(
        UserInvitation.organization_id == inviter.organization_id,
        UserInvitation.email == normalized,
        UserInvitation.status == "PENDING",
    ))
    if pending:
        raise HTTPException(status_code=409, detail="Já existe convite pendente para este e-mail")
    invite, raw = create_invitation(db, inviter, normalized, role, inviter.branch_id)
    invite.partner_contract_required = True
    return invite, raw


def list_partner_invitations(db: Session, inviter: User) -> list[UserInvitation]:
    return list(db.scalars(select(UserInvitation).where(
        UserInvitation.organization_id == inviter.organization_id,
        UserInvitation.invited_by_id == inviter.id,
    ).order_by(UserInvitation.created_at.desc())))


def accept_invitation(
    db: Session,
    raw: str,
    name: str,
    document: str | None,
    password: str,
    *,
    company_name: str | None = None,
    company_cnpj: str | None = None,
    company_address: str | None = None,
    company_city: str | None = None,
    company_state: str | None = None,
    phone: str | None = None,
    terms_accepted: bool = False,
    scroll_completed: bool = False,
    verification_reference: str | None = None,
    ip_address: str | None = None,
    user_agent: str | None = None,
):
    from app.partner_contract_service import record_partner_contract_acceptance, validate_partner_contract_payload

    invite = db.scalar(select(UserInvitation).where(UserInvitation.token_hash == token_hash(raw), UserInvitation.status == "PENDING"))
    if not invite or as_utc(invite.expires_at) <= datetime.now(UTC):
        raise HTTPException(status_code=422, detail="Convite inválido ou expirado")
    if db.scalar(select(User).where(User.email == invite.email)):
        raise HTTPException(status_code=409, detail="E-mail já cadastrado")
    validate_partner_contract_payload(
        invite,
        company_name=company_name,
        company_cnpj=company_cnpj,
        company_address=company_address,
        company_city=company_city,
        company_state=company_state,
        terms_accepted=terms_accepted,
        scroll_completed=scroll_completed,
        verification_reference=verification_reference,
        phone=phone,
    )
    user = User(
        organization_id=invite.organization_id,
        branch_id=invite.branch_id,
        name=name,
        email=invite.email,
        document=document,
        phone=(phone or "").strip() or None,
        company_name=(company_name or "").strip() or None,
        company_cnpj=(company_cnpj or "").strip() or None,
        company_address=(company_address or "").strip() or None,
        company_city=(company_city or "").strip() or None,
        company_state=(company_state or "").strip().upper()[:2] or None,
        password_hash=hash_password(password),
        role=invite.role,
    )
    db.add(user)
    db.flush()
    inviter = db.get(User, invite.invited_by_id)
    if inviter:
        attach_partner_under_sponsor(db, invite.organization_id, user, inviter)
    if invite.partner_contract_required:
        record_partner_contract_acceptance(
            db,
            invite=invite,
            user=user,
            company_name=company_name or name,
            company_cnpj=company_cnpj or "",
            company_address=company_address or "",
            company_city=company_city or "",
            company_state=company_state or "",
            representative_name=name,
            representative_document=document or "",
            verification_reference=verification_reference or "",
            ip_address=ip_address,
            user_agent=user_agent,
        )
    invite.status = "ACCEPTED"
    invite.accepted_at = datetime.now(UTC)
    return user


def create_password_reset(db:Session,user:User):
    raw=secrets.token_urlsafe(32);item=PasswordReset(user_id=user.id,token_hash=token_hash(raw),expires_at=datetime.now(UTC)+timedelta(minutes=30));db.add(item);return raw


def confirm_password_reset(db:Session,raw:str,new_password:str):
    item=db.scalar(select(PasswordReset).where(PasswordReset.token_hash==token_hash(raw),PasswordReset.used_at.is_(None)))
    if not item or as_utc(item.expires_at)<=datetime.now(UTC): raise HTTPException(status_code=422,detail="Token inválido ou expirado")
    user=db.get(User,item.user_id);user.password_hash=hash_password(new_password);item.used_at=datetime.now(UTC)
    for session in db.scalars(select(AuthSession).where(AuthSession.user_id==user.id,AuthSession.active.is_(True))): session.active=False;session.revoked_at=datetime.now(UTC)


def create_kyc_case(user:User,subject_type:str,subject_id:str):
    return KycCase(organization_id=user.organization_id,subject_type=subject_type,subject_id=subject_id,provider="MOCK",external_id=f"mock_kyc_{uuid4().hex}")
