import json
import os
from datetime import date
from decimal import Decimal

from sqlalchemy import select

from app.core.security import hash_password
from app.db import Base, SessionLocal, engine
from app.models import Administrator, CommissionRule, Lead, Organization, Proposal, Quota, Role, User


LEVEL_SHARES = ["50", "35", "7", "5", "3"]
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


DEMO_USER_PHONES = {
    "admin@letter.com.br": "11900000001",
    "parceiro@letter.com.br": "11900000002",
    "revisor1@letter.com.br": "11900000003",
    "revisor2@letter.com.br": "11900000004",
    "investidor@letter.com.br": "11900000005",
    "cliente@letter.com.br": "11900000006",
    "fundo@letter.com.br": "11900000007",
}


def _sync_demo_phones(db) -> None:
    """Preenche telefone dos usuários demo quando ausente (KYC / Minha Carteira)."""
    if os.environ.get("LETTER_ENV", "development") not in {"development", "staging"}:
        return
    updated = 0
    for email, phone in DEMO_USER_PHONES.items():
        user = db.scalar(select(User).where(User.email == email))
        if user and not (user.phone or "").strip():
            user.phone = phone
            updated += 1
    if updated:
        db.commit()
        print(f"Telefones demo sincronizados para {updated} usuários.")


def _demo_phone(email: str) -> str | None:
    return DEMO_USER_PHONES.get(email)


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
                phone=_demo_phone(email),
                password_hash=hashed,
                role=role,
            )
        )
        created += 1
    if created:
        db.commit()
        print(f"Usuários demo de perfil criados: {created}.")


def _sync_headquarters_org(db) -> None:
    from app.company_profile_service import company_profile

    profile = company_profile()
    org = db.scalar(select(Organization).where(Organization.kind == "HEADQUARTERS"))
    if not org:
        return
    org.name = profile["legal_name"]
    org.document = profile["cnpj_digits"]
    db.commit()


def _ensure_master_trees(db, org_id: str, password: str) -> None:
    from app.master_tree_service import MASTER_TREE_LETTER_BANK, ensure_master_roots, sync_user_master_tree

    masters = ensure_master_roots(db, org_id, password)
    partner = db.scalar(select(User).where(User.email == "parceiro@letter.com.br"))
    if partner and not partner.master_tree_key:
        partner.master_tree_key = MASTER_TREE_LETTER_BANK
        sync_user_master_tree(db, partner)
    db.commit()
    if masters:
        print(f"Masters comerciais sincronizados: {', '.join(masters.keys())}.")


def seed():
    Base.metadata.create_all(engine)
    password = _demo_password()
    with SessionLocal() as db:
        if db.scalar(select(User).where(User.email == "admin@letter.com.br")):
            org = db.scalar(select(Organization).limit(1))
            if org:
                _ensure_profile_demo_users(db, org.id, password)
                _ensure_master_trees(db, org.id, password)
                from app.vender_cota_service import ensure_default_ranges, ensure_quota_sell_commission_rule
                from app.quota_supplier_service import ensure_default_suppliers

                ensure_default_ranges(db, org.id)
                ensure_quota_sell_commission_rule(db, org.id)
                ensure_default_suppliers(db, org.id)
                db.commit()
            _sync_headquarters_org(db)
            _sync_demo_phones(db)
            _sync_demo_passwords(db, password)
            print("Seed já aplicado.")
            return
        org = Organization(name="LETTER FRANQUEADORA LTDA", document="57255607000130", kind="HEADQUARTERS")
        db.add(org); db.flush()
        admin = User(
            organization_id=org.id, name="Administrador LETTER", email="admin@letter.com.br",
            document="00000000000", phone=_demo_phone("admin@letter.com.br"),
            password_hash=hash_password(password), role=Role.PLATFORM_ADMIN,
        )
        partner = User(
            organization_id=org.id, name="Parceiro Demonstração", email="parceiro@letter.com.br",
            document="11111111111", phone=_demo_phone("parceiro@letter.com.br"),
            password_hash=hash_password(password), role=Role.PARTNER,
        )
        reviewer_one = User(
            organization_id=org.id, name="Revisor Financeiro 1", email="revisor1@letter.com.br",
            document="33333333333", phone=_demo_phone("revisor1@letter.com.br"),
            password_hash=hash_password(password), role=Role.INTERNAL_STAFF,
        )
        reviewer_two = User(
            organization_id=org.id, name="Revisor Financeiro 2", email="revisor2@letter.com.br",
            document="44444444444", phone=_demo_phone("revisor2@letter.com.br"),
            password_hash=hash_password(password), role=Role.INTERNAL_STAFF,
        )
        investor = User(
            organization_id=org.id, name="Investidor Varejo", email="investidor@letter.com.br",
            document="55555555555", phone=_demo_phone("investidor@letter.com.br"),
            password_hash=hash_password(password), role=Role.RETAIL_INVESTOR,
        )
        client = User(
            organization_id=org.id, name="Cliente Demonstração", email="cliente@letter.com.br",
            document="66666666666", phone=_demo_phone("cliente@letter.com.br"),
            password_hash=hash_password(password), role=Role.CLIENT,
        )
        fund = User(
            organization_id=org.id, name="Fundo Institucional Demo", email="fundo@letter.com.br",
            document="77777777777", phone=_demo_phone("fundo@letter.com.br"),
            password_hash=hash_password(password), role=Role.INSTITUTIONAL_FUND,
        )
        adms = [
            Administrator(name="Embracon", code="EMBRACON", document="22222222000122", authorization_status="AUTHORIZED", bacen_rules_version=1),
            Administrator(name="HS Consórcios", code="HS_CONSORCIOS", document="33333333000133", authorization_status="AUTHORIZED", bacen_rules_version=1),
            Administrator(name="Ademicon", code="ADEMICON", document="44444444000144", authorization_status="AUTHORIZED", bacen_rules_version=1),
            Administrator(name="Ancora", code="ANCORA", document="55555555000155", authorization_status="AUTHORIZED", bacen_rules_version=1),
            Administrator(name="Whitelabel Ancora", code="WHITELABEL_ANCORA", document="66666666000166", authorization_status="AUTHORIZED", bacen_rules_version=1),
        ]
        db.add_all([admin, partner, reviewer_one, reviewer_two, investor, client, fund, *adms]); db.flush()
        adm = adms[0]
        lead = Lead(organization_id=org.id, owner_id=partner.id, name="Cliente Piloto", phone="32999999999", product_interest="MARKETPLACE", status="QUALIFIED")
        db.add(lead); db.flush()
        db.add_all([
            Quota(organization_id=org.id, administrator_id=adm.id, seller_id=admin.id, group_code="1001", quota_code="001", category="REAL_ESTATE", credit_value=Decimal("400000"), outstanding_balance=Decimal("250000"), premium_value=Decimal("80000"), installment_value=Decimal("2800"), installment_due_date=date(2026, 9, 10), remaining_installments=48, supplier_source="FRAGA"),
            Quota(organization_id=org.id, administrator_id=adm.id, seller_id=admin.id, group_code="1001", quota_code="002", category="REAL_ESTATE", credit_value=Decimal("400000"), outstanding_balance=Decimal("250000"), premium_value=Decimal("78000"), installment_value=Decimal("2750"), installment_due_date=date(2026, 9, 15), remaining_installments=48, supplier_source="UNI_CONTEMPLADOS"),
            Quota(organization_id=org.id, administrator_id=adm.id, seller_id=admin.id, group_code="1002", quota_code="010", category="REAL_ESTATE", credit_value=Decimal("380000"), outstanding_balance=Decimal("240000"), premium_value=Decimal("76000"), installment_value=Decimal("2600"), installment_due_date=date(2026, 10, 20), remaining_installments=60, supplier_source="LUME"),
            Quota(organization_id=org.id, administrator_id=adm.id, seller_id=admin.id, group_code="1002", quota_code="011", category="REAL_ESTATE", credit_value=Decimal("420000"), outstanding_balance=Decimal("260000"), premium_value=Decimal("84000"), installment_value=Decimal("2900"), installment_due_date=date(2026, 11, 5), remaining_installments=54, supplier_source="BITTELO"),
        ])
        db.add(Proposal(organization_id=org.id, lead_id=lead.id, product="MARKETPLACE", requested_amount=Decimal("800000"), status="DRAFT"))
        from app.quota_supplier_service import ensure_default_suppliers

        ensure_default_suppliers(db, org.id)
        db.add_all([
            CommissionRule(
                organization_id=org.id, product="FLASH_CREDIT", commission_type="SALES", version=1,
                base_type="NET_PAYOUT", pool_rate_percent=Decimal("3"), levels_json=json.dumps(LEVEL_SHARES), active=True,
            ),
            CommissionRule(
                organization_id=org.id, product="SDC", commission_type="SALES", version=1,
                base_type="INTERMEDIATION_FEE", pool_rate_percent=Decimal("3"), levels_json=json.dumps(LEVEL_SHARES), active=True,
            ),
            CommissionRule(
                organization_id=org.id, product="QUOTA_SELL", commission_type="SALES", version=1,
                base_type="CREDIT_VALUE", pool_rate_percent=Decimal("3"), levels_json=json.dumps(LEVEL_SHARES), active=True,
            ),
            CommissionRule(
                organization_id=org.id, product="QUITCON", commission_type="SALES", version=1,
                base_type="QUITACAO_VP", pool_rate_percent=Decimal("3"), levels_json=json.dumps(LEVEL_SHARES), active=True,
            ),
        ])
        db.commit()
        from app.vender_cota_service import ensure_default_ranges

        ensure_default_ranges(db, org.id)
        db.commit()
        _ensure_master_trees(db, org.id, password)
        print("Seed concluído: admin@letter.com.br / (senha de LETTER_DEMO_PASSWORD ou Letter@123)")


if __name__ == "__main__":
    seed()
