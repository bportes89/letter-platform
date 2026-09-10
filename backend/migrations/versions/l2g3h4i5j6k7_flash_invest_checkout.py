"""Flash Invest reservation checkout fields.

Revision ID: l2g3h4i5j6k7
Revises: k1f2g3h4i5j6
Create Date: 2026-09-10
"""

from alembic import op
import sqlalchemy as sa

revision = "l2g3h4i5j6k7"
down_revision = "k1f2g3h4i5j6"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("investment_reservations", sa.Column("asaas_payment_id", sa.String(80), nullable=True))
    op.add_column("investment_reservations", sa.Column("external_reference", sa.String(120), nullable=True))
    op.add_column("investment_reservations", sa.Column("checkout_url", sa.Text(), nullable=True))
    op.add_column("investment_reservations", sa.Column("pix_copy_paste", sa.Text(), nullable=True))
    op.add_column("investment_reservations", sa.Column("pix_qr_code", sa.Text(), nullable=True))
    op.add_column("investment_reservations", sa.Column("checkout_status", sa.String(40), nullable=True))
    op.add_column("investment_reservations", sa.Column("checkout_mode", sa.String(20), nullable=True))
    op.create_index("ix_investment_reservations_asaas_payment_id", "investment_reservations", ["asaas_payment_id"])
    op.create_index("ix_investment_reservations_external_reference", "investment_reservations", ["external_reference"])


def downgrade() -> None:
    op.drop_index("ix_investment_reservations_external_reference", table_name="investment_reservations")
    op.drop_index("ix_investment_reservations_asaas_payment_id", table_name="investment_reservations")
    op.drop_column("investment_reservations", "checkout_mode")
    op.drop_column("investment_reservations", "checkout_status")
    op.drop_column("investment_reservations", "pix_qr_code")
    op.drop_column("investment_reservations", "pix_copy_paste")
    op.drop_column("investment_reservations", "checkout_url")
    op.drop_column("investment_reservations", "external_reference")
    op.drop_column("investment_reservations", "asaas_payment_id")
