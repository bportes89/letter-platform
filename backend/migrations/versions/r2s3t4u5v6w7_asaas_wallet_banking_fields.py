"""asaas wallet banking fields

Revision ID: r2s3t4u5v6w7
Revises: q1r2s3t4u5v6
"""
from alembic import op
import sqlalchemy as sa

revision = "r2s3t4u5v6w7"
down_revision = "q1r2s3t4u5v6"
branch_labels = None
depends_on = None


def upgrade():
    op.add_column("escrow_accounts", sa.Column("asaas_subaccount_api_key", sa.Text(), nullable=True))
    op.add_column("escrow_accounts", sa.Column("bank_code", sa.String(10), nullable=True))
    op.add_column("escrow_accounts", sa.Column("bank_agency", sa.String(20), nullable=True))
    op.add_column("escrow_accounts", sa.Column("bank_account_number", sa.String(40), nullable=True))
    op.add_column("escrow_accounts", sa.Column("pix_key", sa.String(180), nullable=True))
    op.add_column("escrow_accounts", sa.Column("asaas_kyc_status", sa.String(40), nullable=True))
    op.add_column("escrow_accounts", sa.Column("asaas_commercial_status", sa.String(40), nullable=True))
    op.add_column("escrow_accounts", sa.Column("asaas_onboarding_url", sa.Text(), nullable=True))


def downgrade():
    op.drop_column("escrow_accounts", "asaas_onboarding_url")
    op.drop_column("escrow_accounts", "asaas_commercial_status")
    op.drop_column("escrow_accounts", "asaas_kyc_status")
    op.drop_column("escrow_accounts", "pix_key")
    op.drop_column("escrow_accounts", "bank_account_number")
    op.drop_column("escrow_accounts", "bank_agency")
    op.drop_column("escrow_accounts", "bank_code")
    op.drop_column("escrow_accounts", "asaas_subaccount_api_key")
