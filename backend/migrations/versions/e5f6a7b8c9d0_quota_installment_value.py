"""Add installment_value to quotas for marketplace income filter.

Revision ID: e5f6a7b8c9d0
Revises: d4e5f6a7b8c9
Create Date: 2026-09-09
"""

from alembic import op
import sqlalchemy as sa

revision = "e5f6a7b8c9d0"
down_revision = "d4e5f6a7b8c9"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "quotas",
        sa.Column("installment_value", sa.Numeric(15, 2), nullable=False, server_default="0"),
    )


def downgrade() -> None:
    op.drop_column("quotas", "installment_value")
