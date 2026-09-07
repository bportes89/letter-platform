"""Árvores comerciais raiz — Letter Bank e RMK (Bevi)."""

from __future__ import annotations

import os

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.security import hash_password
from app.models import NetworkNode, Role, User
from app.network_service import PARTNER_NETWORK_ROLES, attach_partner_under_sponsor

MASTER_TREE_LETTER_BANK = "LETTER_BANK"
MASTER_TREE_RMK_BEVI = "RMK_BEVI"

MASTER_TREE_LABELS = {
    MASTER_TREE_LETTER_BANK: "Letter Bank",
    MASTER_TREE_RMK_BEVI: "RMK (Bevi)",
}

MASTER_ROOT_SPECS: tuple[dict, ...] = (
    {
        "key": MASTER_TREE_LETTER_BANK,
        "name": "Letter Bank",
        "email": "letter-bank@letter.com.br",
        "document": "88888888888",
        "phone": "11988880001",
    },
    {
        "key": MASTER_TREE_RMK_BEVI,
        "name": "RMK (Bevi)",
        "email": "rmk-bevi@letter.com.br",
        "document": "99999999999",
        "phone": "11988880002",
    },
)


def _master_email(tree_key: str) -> str:
    if tree_key == MASTER_TREE_LETTER_BANK:
        return settings.master_letter_bank_email
    if tree_key == MASTER_TREE_RMK_BEVI:
        return settings.master_rmk_bevi_email
    return ""


def resolve_master_tree_key_from_legacy(legacy_source: str | None, row: dict | None = None) -> str | None:
    explicit = (row or {}).get("master_tree_key") if row else None
    if explicit:
        key = str(explicit).strip().upper()
        if key in {MASTER_TREE_LETTER_BANK, MASTER_TREE_RMK_BEVI}:
            return key
    source = (legacy_source or "").lower()
    if "bevi" in source or "rmk" in source:
        return MASTER_TREE_RMK_BEVI
    if "letter" in source and "bank" in source:
        return MASTER_TREE_LETTER_BANK
    return None


def get_master_root_user(db: Session, organization_id: str, tree_key: str) -> User | None:
    email = _master_email(tree_key).lower()
    if not email:
        return None
    return db.scalar(
        select(User).where(
            User.organization_id == organization_id,
            User.email == email,
            User.role == Role.MASTER_FRANCHISEE,
            User.active.is_(True),
        )
    )


def ensure_master_root_node(db: Session, master: User, tree_key: str) -> NetworkNode:
    existing = db.scalar(
        select(NetworkNode).where(
            NetworkNode.organization_id == master.organization_id,
            NetworkNode.user_id == master.id,
            NetworkNode.tree_type == "SALES",
        )
    )
    if existing:
        if not existing.master_tree_key:
            existing.master_tree_key = tree_key
        if existing.sponsor_user_id:
            existing.sponsor_user_id = None
        db.flush()
        return existing
    code = f"LTR-{tree_key[:3]}-{master.id.replace('-', '')[:8].upper()}"
    node = NetworkNode(
        organization_id=master.organization_id,
        user_id=master.id,
        sponsor_user_id=None,
        master_tree_key=tree_key,
        tree_type="SALES",
        referral_code=code,
    )
    db.add(node)
    db.flush()
    return node


def ensure_master_roots(db: Session, organization_id: str, password: str | None = None) -> dict[str, User]:
    pwd = password or os.environ.get("LETTER_DEMO_PASSWORD", "Letter@123")
    hashed = hash_password(pwd)
    masters: dict[str, User] = {}
    for spec in MASTER_ROOT_SPECS:
        tree_key = spec["key"]
        email = _master_email(tree_key).lower() or spec["email"]
        user = db.scalar(select(User).where(User.email == email))
        if not user:
            user = User(
                organization_id=organization_id,
                name=spec["name"],
                email=email,
                document=spec["document"],
                phone=spec["phone"],
                password_hash=hashed,
                role=Role.MASTER_FRANCHISEE,
                master_tree_key=tree_key,
                active=True,
            )
            db.add(user)
            db.flush()
        else:
            user.role = Role.MASTER_FRANCHISEE
            user.master_tree_key = tree_key
            user.active = True
            if not (user.phone or "").strip():
                user.phone = spec["phone"]
        ensure_master_root_node(db, user, tree_key)
        masters[tree_key] = user
    db.flush()
    return masters


def sync_user_master_tree(db: Session, user: User) -> NetworkNode | None:
    """Vincula parceiro migrado à árvore do master quando master_tree_key estiver definido."""
    if not user.master_tree_key or user.role not in PARTNER_NETWORK_ROLES:
        return None
    if user.role == Role.MASTER_FRANCHISEE:
        return ensure_master_root_node(db, user, user.master_tree_key)
    master = get_master_root_user(db, user.organization_id, user.master_tree_key)
    if not master:
        return None
    ensure_master_root_node(db, master, user.master_tree_key)
    node = attach_partner_under_sponsor(db, user.organization_id, user, master)
    if node and not user.master_tree_key:
        user.master_tree_key = master.master_tree_key
    return node


def list_master_trees(db: Session, organization_id: str) -> list[dict]:
    rows: list[dict] = []
    for spec in MASTER_ROOT_SPECS:
        tree_key = spec["key"]
        master = get_master_root_user(db, organization_id, tree_key)
        node = None
        if master:
            node = db.scalar(
                select(NetworkNode).where(
                    NetworkNode.organization_id == organization_id,
                    NetworkNode.user_id == master.id,
                    NetworkNode.tree_type == "SALES",
                )
            )
        rows.append(
            {
                "tree_key": tree_key,
                "label": MASTER_TREE_LABELS.get(tree_key, tree_key),
                "master_user_id": master.id if master else None,
                "master_email": master.email if master else _master_email(tree_key),
                "referral_code": node.referral_code if node else None,
                "active": master is not None,
            }
        )
    return rows
