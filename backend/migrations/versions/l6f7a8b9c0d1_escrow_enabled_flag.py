"""escrow_enabled on escrow accounts

Revision ID: l6f7a8b9c0d1
Revises: k5e6f7a8b9c0
"""
from alembic import op
import sqlalchemy as sa

revision = "l6f7a8b9c0d1"
down_revision = "k5e6f7a8b9c0"
branch_labels = None
depends_on = None


def upgrade():
    op.add_column(
        "escrow_accounts",
        sa.Column("escrow_enabled", sa.Boolean(), nullable=False, server_default=sa.true()),
    )


def downgrade():
    op.drop_column("escrow_accounts", "escrow_enabled")
