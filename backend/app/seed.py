import json
import os
from decimal import Decimal

from sqlalchemy import select

from app.core.security import hash_password
from app.db import Base, SessionLocal, engine
from app.models import Administrator, CommissionRule, Lead, Organization, Proposal, Quota, Role, User


LEVEL_SHARES = ["50", "20", "15", "10", "5"]
DEMO_USER_EMAILS = (
    "admin@letter.com.br",
    "parceiro@letter.com.br",
    "cliente@letter.com.br",
    "revisor1@letter.com.br",
    "revisor2@letter.com.br",
    "investidor@letter.com.br",
    "fundo@letter.com.br",
)


def _demo_password() -> str:
    return os.environ.get("LETTER_DEMO_PASSWORD", "Letter@123")


def _sync_demo_passwords(db, password: str) -> None:
    """Em staging/dev, realinha senhas demo com LETTER_DEMO_PASSWORD a cada deploy."""
    if os.environ.get("LETTER_ENV", "development") not in {"development", "staging"}:
        return
    users = list(db.scalars(select(User).where(User.email.in_(DEMO_USER_EMAILS))))
    if not users:
        return
    hashed = hash_password(password)
    for user in users:
        user.password_hash = hashed
    db.commit()
    print(f"Senhas demo sincronizadas para {len(users)} usuários.")


def _ensure_profile_demo_users(db, org_id, password: str) -> None:
    """Cria usuários demo de perfis adicionais se ainda não existirem (idempotente)."""
    specs = (
        ("cliente@letter.com.br", "Cliente Demonstração", "66666666666", Role.CLIENT),
        ("fundo@letter.com.br", "Fundo Institucional Demo", "77777777777", Role.INSTITUTIONAL_FUND),
    )
    hashed = hash_password(password)
    created = 0
    for email, name, document, role in specs:
        if db.scalar(select(User).where(User.email == email)):
            continue
        db.add(
            User(
                organization_id=org_id,
                name=name,
                email=email,
                document=document,
                password_hash=hashed,
                role=role,
            )
        )
        created += 1
    if created:
        db.commit()
        print(f"Usuários demo de perfil criados: {created}.")


def seed():
    Base.metadata.create_all(engine)
    password = _demo_password()
    with SessionLocal() as db:
        if db.scalar(select(User).where(User.email == "admin@letter.com.br")):
            org = db.scalar(select(Organization).limit(1))
            if org:
                _ensure_profile_demo_users(db, org.id, password)
            _sync_demo_passwords(db, password)
            print("Seed já aplicado.")
            return
        org = Organization(name="LETTER Matriz", document="00000000000000", kind="HEADQUARTERS")
        db.add(org); db.flush()
        admin = User(
            organization_id=org.id, name="Administrador LETTER", email="admin@letter.com.br",
            document="00000000000", password_hash=hash_password(password), role=Role.PLATFORM_ADMIN,
        )
        partner = User(
            organization_id=org.id, name="Parceiro Demonstração", email="parceiro@letter.com.br",
            document="11111111111", password_hash=hash_password(password), role=Role.PARTNER,
        )
        reviewer_one = User(
            organization_id=org.id, name="Revisor Financeiro 1", email="revisor1@letter.com.br",
            document="33333333333", password_hash=hash_password(password), role=Role.INTERNAL_STAFF,
        )
        reviewer_two = User(
            organization_id=org.id, name="Revisor Financeiro 2", email="revisor2@letter.com.br",
            document="44444444444", password_hash=hash_password(password), role=Role.INTERNAL_STAFF,
        )
        investor = User(
            organization_id=org.id, name="Investidor Varejo", email="investidor@letter.com.br",
            document="55555555555", password_hash=hash_password(password), role=Role.RETAIL_INVESTOR,
        )
        client = User(
            organization_id=org.id, name="Cliente Demonstração", email="cliente@letter.com.br",
            document="66666666666", password_hash=hash_password(password), role=Role.CLIENT,
        )
        fund = User(
            organization_id=org.id, name="Fundo Institucional Demo", email="fundo@letter.com.br",
            document="77777777777", password_hash=hash_password(password), role=Role.INSTITUTIONAL_FUND,
        )
        adm = Administrator(name="Embracon", document="22222222000122", authorization_status="APPROVED_MANUALLY")
        db.add_all([admin, partner, reviewer_one, reviewer_two, investor, client, fund, adm]); db.flush()
        lead = Lead(organization_id=org.id, owner_id=partner.id, name="Cliente Piloto", phone="32999999999", product_interest="MARKETPLACE", status="QUALIFIED")
        db.add(lead); db.flush()
        db.add_all([
            Quota(organization_id=org.id, administrator_id=adm.id, seller_id=admin.id, group_code="1001", quota_code="001", category="REAL_ESTATE", credit_value=Decimal("400000"), outstanding_balance=Decimal("250000"), premium_value=Decimal("80000")),
            Quota(organization_id=org.id, administrator_id=adm.id, seller_id=admin.id, group_code="1001", quota_code="002", category="REAL_ESTATE", credit_value=Decimal("400000"), outstanding_balance=Decimal("250000"), premium_value=Decimal("78000")),
        ])
        db.add(Proposal(organization_id=org.id, lead_id=lead.id, product="MARKETPLACE", requested_amount=Decimal("800000"), status="DRAFT"))
        db.add_all([
            CommissionRule(
                organization_id=org.id, product="FLASH_CREDIT", commission_type="SALES", version=1,
                base_type="NET_PAYOUT", pool_rate_percent=Decimal("3"), levels_json=json.dumps(LEVEL_SHARES), active=True,
            ),
            CommissionRule(
                organization_id=org.id, product="SDC", commission_type="SALES", version=1,
                base_type="INTERMEDIATION_FEE", pool_rate_percent=Decimal("3"), levels_json=json.dumps(LEVEL_SHARES), active=True,
            ),
        ])
        db.commit()
        print("Seed concluído: admin@letter.com.br / (senha de LETTER_DEMO_PASSWORD ou Letter@123)")


if __name__ == "__main__":
    seed()
