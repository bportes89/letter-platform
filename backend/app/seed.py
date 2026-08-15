from decimal import Decimal

from sqlalchemy import select

from app.core.security import hash_password
from app.db import Base, SessionLocal, engine
from app.models import Administrator, Lead, Organization, Proposal, Quota, Role, User


def seed():
    Base.metadata.create_all(engine)
    with SessionLocal() as db:
        if db.scalar(select(User).where(User.email == "admin@letter.com.br")):
            print("Seed já aplicado.")
            return
        org = Organization(name="LETTER Matriz", document="00000000000000", kind="HEADQUARTERS")
        db.add(org); db.flush()
        admin = User(
            organization_id=org.id, name="Administrador LETTER", email="admin@letter.com.br",
            document="00000000000", password_hash=hash_password("Letter@123"), role=Role.PLATFORM_ADMIN,
        )
        partner = User(
            organization_id=org.id, name="Parceiro Demonstração", email="parceiro@letter.com.br",
            document="11111111111", password_hash=hash_password("Letter@123"), role=Role.PARTNER,
        )
        reviewer_one = User(
            organization_id=org.id, name="Revisor Financeiro 1", email="revisor1@letter.com.br",
            document="33333333333", password_hash=hash_password("Letter@123"), role=Role.INTERNAL_STAFF,
        )
        reviewer_two = User(
            organization_id=org.id, name="Revisor Financeiro 2", email="revisor2@letter.com.br",
            document="44444444444", password_hash=hash_password("Letter@123"), role=Role.INTERNAL_STAFF,
        )
        investor = User(
            organization_id=org.id, name="Investidor Varejo", email="investidor@letter.com.br",
            document="55555555555", password_hash=hash_password("Letter@123"), role=Role.RETAIL_INVESTOR,
        )
        adm = Administrator(name="Administradora Demonstração", document="22222222000122", authorization_status="APPROVED_MANUALLY")
        db.add_all([admin, partner, reviewer_one, reviewer_two, investor, adm]); db.flush()
        lead = Lead(organization_id=org.id, owner_id=partner.id, name="Cliente Piloto", phone="32999999999", product_interest="MARKETPLACE", status="QUALIFIED")
        db.add(lead); db.flush()
        db.add_all([
            Quota(organization_id=org.id, administrator_id=adm.id, seller_id=admin.id, group_code="1001", quota_code="001", category="REAL_ESTATE", credit_value=Decimal("400000"), outstanding_balance=Decimal("250000"), premium_value=Decimal("80000")),
            Quota(organization_id=org.id, administrator_id=adm.id, seller_id=admin.id, group_code="1001", quota_code="002", category="REAL_ESTATE", credit_value=Decimal("400000"), outstanding_balance=Decimal("250000"), premium_value=Decimal("78000")),
        ])
        db.add(Proposal(organization_id=org.id, lead_id=lead.id, product="MARKETPLACE", requested_amount=Decimal("800000"), status="DRAFT"))
        db.commit()
        print("Seed concluído: admin@letter.com.br / Letter@123")


if __name__ == "__main__":
    seed()
