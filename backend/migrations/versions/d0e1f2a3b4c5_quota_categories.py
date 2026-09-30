"""Quota categories and subcategories (legacy quotas_categories).

Revision ID: d0e1f2a3b4c5
Revises: c9d0e1f2a3b4
Create Date: 2026-09-30
"""

from alembic import op
import sqlalchemy as sa

revision = "d0e1f2a3b4c5"
down_revision = "c9d0e1f2a3b4"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "quota_categories",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("organization_id", sa.String(length=36), nullable=False),
        sa.Column("legacy_id", sa.Integer(), nullable=True),
        sa.Column("active", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("name", sa.String(length=255), nullable=False),
        sa.Column("title_sub", sa.String(length=120), nullable=True),
        sa.Column("legacy_type", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("parent_id", sa.String(length=36), nullable=True),
        sa.Column("sort_order", sa.Integer(), nullable=False, server_default="999"),
        sa.Column("asset_class", sa.String(length=30), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["organization_id"], ["organizations.id"]),
        sa.ForeignKeyConstraint(["parent_id"], ["quota_categories.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("organization_id", "legacy_id", name="uq_quota_category_org_legacy"),
    )
    op.create_index("ix_quota_categories_organization_id", "quota_categories", ["organization_id"])
    op.create_index("ix_quota_categories_legacy_id", "quota_categories", ["legacy_id"])
    op.create_index("ix_quota_categories_parent_id", "quota_categories", ["parent_id"])


def downgrade() -> None:
    op.drop_index("ix_quota_categories_parent_id", table_name="quota_categories")
    op.drop_index("ix_quota_categories_legacy_id", table_name="quota_categories")
    op.drop_index("ix_quota_categories_organization_id", table_name="quota_categories")
    op.drop_table("quota_categories")
