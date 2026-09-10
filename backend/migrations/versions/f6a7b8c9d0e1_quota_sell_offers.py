"""Quota sell offer ranges and public offers (Vender minha cota).

Revision ID: f6a7b8c9d0e1
Revises: e5f6a7b8c9d0
Create Date: 2026-09-09
"""

from alembic import op
import sqlalchemy as sa

revision = "f6a7b8c9d0e1"
down_revision = "e5f6a7b8c9d0"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "quota_offer_ranges",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("organization_id", sa.String(36), sa.ForeignKey("organizations.id"), nullable=False, index=True),
        sa.Column("active", sa.Boolean(), nullable=False, server_default=sa.text("1")),
        sa.Column("name", sa.String(180), nullable=False),
        sa.Column("sort_order", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("tipo", sa.String(20), nullable=False, index=True),
        sa.Column("prazo_init", sa.Integer(), nullable=False),
        sa.Column("prazo_final", sa.Integer(), nullable=False),
        sa.Column("pago_init", sa.Numeric(8, 2), nullable=False, server_default="0"),
        sa.Column("pago_final", sa.Numeric(8, 2), nullable=False),
        sa.Column("porc", sa.Numeric(8, 2), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_table(
        "quota_sell_offers",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("organization_id", sa.String(36), sa.ForeignKey("organizations.id"), nullable=False, index=True),
        sa.Column("administrator_id", sa.String(36), sa.ForeignKey("administrators.id"), nullable=True, index=True),
        sa.Column("partner_referral_code", sa.String(80), nullable=True),
        sa.Column("status", sa.String(40), nullable=False, server_default="AWAITING_STATEMENT", index=True),
        sa.Column("contact_name", sa.String(180), nullable=False),
        sa.Column("contact_email", sa.String(180), nullable=False, index=True),
        sa.Column("contact_phone", sa.String(40), nullable=False),
        sa.Column("document", sa.String(20), nullable=True),
        sa.Column("person_type", sa.String(10), nullable=False, server_default="PF"),
        sa.Column("tipo_consorcio", sa.String(30), nullable=False),
        sa.Column("credit_value", sa.Numeric(15, 2), nullable=False),
        sa.Column("paid_value", sa.Numeric(15, 2), nullable=False, server_default="0"),
        sa.Column("outstanding_balance", sa.Numeric(15, 2), nullable=False, server_default="0"),
        sa.Column("term_months", sa.Integer(), nullable=False),
        sa.Column("contemplated", sa.Boolean(), nullable=False, server_default=sa.text("0")),
        sa.Column("paid_percent", sa.Numeric(8, 2), nullable=False, server_default="0"),
        sa.Column("offer_percent", sa.Numeric(8, 2), nullable=False, server_default="0"),
        sa.Column("offer_value", sa.Numeric(15, 2), nullable=False, server_default="0"),
        sa.Column("notes", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
    )


def downgrade() -> None:
    op.drop_table("quota_sell_offers")
    op.drop_table("quota_offer_ranges")
