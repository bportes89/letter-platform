"""escrow billing cycles for monthly platform fee

Revision ID: s3t4u5v6w7x8
Revises: r2s3t4u5v6w7
"""
from alembic import op
import sqlalchemy as sa

revision = "s3t4u5v6w7x8"
down_revision = "r2s3t4u5v6w7"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "escrow_billing_cycles",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("organization_id", sa.String(36), sa.ForeignKey("organizations.id"), nullable=False, index=True),
        sa.Column("escrow_account_id", sa.String(36), sa.ForeignKey("escrow_accounts.id"), nullable=False, unique=True),
        sa.Column("monthly_amount", sa.Numeric(15, 2), nullable=False, server_default="499.90"),
        sa.Column("next_billing_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("last_billed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("status", sa.String(30), nullable=False, server_default="ACTIVE"),
        sa.Column("outstanding_amount", sa.Numeric(15, 2), nullable=False, server_default="0"),
        sa.Column("billing_blocked", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("delinquent_since", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
    )


def downgrade():
    op.drop_table("escrow_billing_cycles")
