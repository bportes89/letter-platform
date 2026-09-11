"""Marketplace chat FAQ admin CRUD.

Revision ID: s9t0u1v2w3x4
Revises: r8s9t0u1v2w3
Create Date: 2026-09-10
"""

from alembic import op
import sqlalchemy as sa

revision = "s9t0u1v2w3x4"
down_revision = "r8s9t0u1v2w3"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "marketplace_chat_faqs",
        sa.Column("id", sa.String(length=36), primary_key=True),
        sa.Column("organization_id", sa.String(length=36), sa.ForeignKey("organizations.id"), nullable=False, index=True),
        sa.Column("legacy_key", sa.String(length=40), nullable=True, index=True),
        sa.Column("name", sa.String(length=255), nullable=False),
        sa.Column("txt", sa.Text(), nullable=False),
        sa.Column("active", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("sort_order", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.UniqueConstraint("organization_id", "legacy_key", name="uq_marketplace_faq_legacy"),
    )


def downgrade() -> None:
    op.drop_table("marketplace_chat_faqs")
