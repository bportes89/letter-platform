"""escrow asaas subaccount metadata

Revision ID: j4d5e6f7a8b9
Revises: i3c4d5e6f7a8
"""
from alembic import op
import sqlalchemy as sa

revision = "j4d5e6f7a8b9"
down_revision = "i3c4d5e6f7a8"
branch_labels = None
depends_on = None


def upgrade():
    op.add_column("escrow_accounts", sa.Column("asaas_account_id", sa.String(120), nullable=True))
    op.add_column("escrow_accounts", sa.Column("subaccount_name", sa.String(180), nullable=True))
    op.create_index(op.f("ix_escrow_accounts_asaas_account_id"), "escrow_accounts", ["asaas_account_id"], unique=False)


def downgrade():
    op.drop_index(op.f("ix_escrow_accounts_asaas_account_id"), table_name="escrow_accounts")
    op.drop_column("escrow_accounts", "subaccount_name")
    op.drop_column("escrow_accounts", "asaas_account_id")
