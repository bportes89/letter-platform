"""User commission percent fields for marketplace bolo rachado.

Revision ID: w3x4y5z6a7b8
Revises: v2w3x4y5z6a7
Create Date: 2026-09-11
"""

from alembic import op
import sqlalchemy as sa

revision = "w3x4y5z6a7b8"
down_revision = "v2w3x4y5z6a7"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("users", sa.Column("porc", sa.Numeric(8, 2), nullable=False, server_default="0"))
    op.add_column("users", sa.Column("porc_capital_giro", sa.Numeric(8, 2), nullable=False, server_default="0"))


def downgrade() -> None:
    op.drop_column("users", "porc_capital_giro")
    op.drop_column("users", "porc")
