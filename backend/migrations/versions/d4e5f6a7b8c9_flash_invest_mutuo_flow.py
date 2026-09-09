"""Flash Invest mútuo contracts lifecycle.

Revision ID: d4e5f6a7b8c9
Revises: c3d4e5f6a7b8
Create Date: 2026-09-09
"""

from alembic import op
import sqlalchemy as sa

revision = "d4e5f6a7b8c9"
down_revision = "c3d4e5f6a7b8"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "mutuo_contracts",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("organization_id", sa.String(36), sa.ForeignKey("organizations.id"), nullable=False, index=True),
        sa.Column("investor_id", sa.String(36), sa.ForeignKey("users.id"), nullable=False, index=True),
        sa.Column("opportunity_id", sa.String(36), sa.ForeignKey("funding_opportunities.id"), nullable=True, index=True),
        sa.Column("position_id", sa.String(36), sa.ForeignKey("investment_positions.id"), nullable=True, index=True),
        sa.Column("principal", sa.Numeric(15, 2), nullable=False),
        sa.Column("monthly_rate", sa.Numeric(8, 4), nullable=False, server_default="0.016"),
        sa.Column("term_months", sa.Integer(), nullable=False, server_default="36"),
        sa.Column("settlement_option", sa.String(1), nullable=False),
        sa.Column("status", sa.String(40), nullable=False, server_default="DRAFT", index=True),
        sa.Column("locality", sa.String(120), nullable=True),
        sa.Column("contract_date", sa.String(40), nullable=True),
        sa.Column("acceptance_hash", sa.String(64), nullable=True),
        sa.Column("signature_provider", sa.String(40), nullable=True),
        sa.Column("signature_external_id", sa.String(120), nullable=True),
        sa.Column("signature_url", sa.String(500), nullable=True),
        sa.Column("signature_status", sa.String(30), nullable=True),
        sa.Column("signed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("settled_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("maturity_at", sa.DateTime(timezone=True), nullable=True, index=True),
        sa.Column("accrued_interest", sa.Numeric(15, 2), nullable=False, server_default="0"),
        sa.Column("paid_interest_total", sa.Numeric(15, 2), nullable=False, server_default="0"),
        sa.Column("interest_months_posted", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("last_interest_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("redemption_requested_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("equity_unlock_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("redeemed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("redemption_amount", sa.Numeric(15, 2), nullable=True),
        sa.Column("equity_conversion_requested_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("equity_converted_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("notes", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_table(
        "mutuo_interest_events",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("organization_id", sa.String(36), sa.ForeignKey("organizations.id"), nullable=False, index=True),
        sa.Column("mutuo_contract_id", sa.String(36), sa.ForeignKey("mutuo_contracts.id"), nullable=False, index=True),
        sa.Column("investor_id", sa.String(36), sa.ForeignKey("users.id"), nullable=False, index=True),
        sa.Column("kind", sa.String(20), nullable=False),
        sa.Column("reference_month", sa.String(7), nullable=False, index=True),
        sa.Column("amount", sa.Numeric(15, 2), nullable=False),
        sa.Column("status", sa.String(30), nullable=False, server_default="POSTED"),
        sa.Column("notes", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.UniqueConstraint("mutuo_contract_id", "reference_month", "kind", name="uq_mutuo_interest_month_kind"),
    )


def downgrade() -> None:
    op.drop_table("mutuo_interest_events")
    op.drop_table("mutuo_contracts")
