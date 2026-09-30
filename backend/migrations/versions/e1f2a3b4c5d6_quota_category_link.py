"""Link quotas to quota_categories.

Revision ID: e1f2a3b4c5d6
Revises: d0e1f2a3b4c5
Create Date: 2026-09-30
"""

from alembic import op
import sqlalchemy as sa

revision = "e1f2a3b4c5d6"
down_revision = "d0e1f2a3b4c5"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("quotas", sa.Column("quota_category_id", sa.String(length=36), nullable=True))
    op.create_foreign_key(
        "fk_quotas_quota_category_id",
        "quotas",
        "quota_categories",
        ["quota_category_id"],
        ["id"],
    )
    op.create_index("ix_quotas_quota_category_id", "quotas", ["quota_category_id"])


def downgrade() -> None:
    op.drop_index("ix_quotas_quota_category_id", table_name="quotas")
    op.drop_constraint("fk_quotas_quota_category_id", "quotas", type_="foreignkey")
    op.drop_column("quotas", "quota_category_id")
