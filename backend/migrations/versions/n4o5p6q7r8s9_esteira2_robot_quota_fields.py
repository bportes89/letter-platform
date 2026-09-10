"""Esteira 2 robot fields on quotas.

Revision ID: n4o5p6q7r8s9
Revises: m3n4o5p6q7r8
Create Date: 2026-09-10
"""

from alembic import op
import sqlalchemy as sa

revision = "n4o5p6q7r8s9"
down_revision = "m3n4o5p6q7r8"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("quotas", sa.Column("remaining_installments", sa.Integer(), nullable=True))
    op.add_column("quotas", sa.Column("supplier_source", sa.String(80), nullable=True))
    op.create_index("ix_quotas_supplier_source", "quotas", ["supplier_source"])


def downgrade() -> None:
    op.drop_index("ix_quotas_supplier_source", table_name="quotas")
    op.drop_column("quotas", "supplier_source")
    op.drop_column("quotas", "remaining_installments")
