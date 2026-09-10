"""Quota supplier portal token fields.

Revision ID: q7r8s9t0u1v2
Revises: p6q7r8s9t0u1
Create Date: 2026-09-10
"""

from alembic import op
import sqlalchemy as sa

revision = "q7r8s9t0u1v2"
down_revision = "p6q7r8s9t0u1"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("quota_suppliers", sa.Column("portal_token_hash", sa.String(length=64), nullable=True))
    op.add_column("quota_suppliers", sa.Column("portal_token_created_at", sa.DateTime(timezone=True), nullable=True))
    op.create_index("ix_quota_suppliers_portal_token_hash", "quota_suppliers", ["portal_token_hash"])


def downgrade() -> None:
    op.drop_index("ix_quota_suppliers_portal_token_hash", table_name="quota_suppliers")
    op.drop_column("quota_suppliers", "portal_token_created_at")
    op.drop_column("quota_suppliers", "portal_token_hash")
