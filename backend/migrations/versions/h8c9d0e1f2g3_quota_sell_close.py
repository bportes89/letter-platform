"""Add inventory and partner fields to quota_sell_offers.

Revision ID: h8c9d0e1f2g3
Revises: g7b8c9d0e1f2
Create Date: 2026-09-10
"""

from alembic import op
import sqlalchemy as sa

revision = "h8c9d0e1f2g3"
down_revision = "g7b8c9d0e1f2"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "quota_sell_offers",
        sa.Column("partner_user_id", sa.String(36), sa.ForeignKey("users.id"), nullable=True),
    )
    op.add_column(
        "quota_sell_offers",
        sa.Column("inventory_quota_id", sa.String(36), sa.ForeignKey("quotas.id"), nullable=True),
    )
    op.add_column(
        "quota_sell_offers",
        sa.Column("commission_reference", sa.String(120), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("quota_sell_offers", "commission_reference")
    op.drop_column("quota_sell_offers", "inventory_quota_id")
    op.drop_column("quota_sell_offers", "partner_user_id")
