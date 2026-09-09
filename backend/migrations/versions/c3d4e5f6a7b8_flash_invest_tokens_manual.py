"""Flash Invest tokens + manual investment/rentability.

Revision ID: c3d4e5f6a7b8
Revises: b2c3d4e5f6a7
Create Date: 2026-09-09
"""

from alembic import op
import sqlalchemy as sa

revision = "c3d4e5f6a7b8"
down_revision = "b2c3d4e5f6a7"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("funding_opportunities", sa.Column("instrument_type", sa.String(20), nullable=False, server_default="TOKEN"))
    op.add_column("funding_opportunities", sa.Column("token_unit_price", sa.Numeric(15, 2), nullable=False, server_default="100"))
    op.add_column("funding_opportunities", sa.Column("monthly_return_rate", sa.Numeric(8, 4), nullable=False, server_default="0.016"))
    op.add_column("funding_opportunities", sa.Column("property_ref", sa.String(180), nullable=True))
    op.create_index("ix_funding_opportunities_instrument_type", "funding_opportunities", ["instrument_type"])

    op.add_column("investment_reservations", sa.Column("instrument_type", sa.String(20), nullable=False, server_default="TOKEN"))

    op.add_column("investment_positions", sa.Column("instrument_type", sa.String(20), nullable=False, server_default="TOKEN"))
    op.add_column("investment_positions", sa.Column("source", sa.String(20), nullable=False, server_default="PLATFORM"))
    op.add_column("investment_positions", sa.Column("tokens_qty", sa.Integer(), nullable=True))
    op.add_column("investment_positions", sa.Column("property_ref", sa.String(180), nullable=True))
    op.add_column("investment_positions", sa.Column("notes", sa.Text(), nullable=True))
    op.add_column("investment_positions", sa.Column("recorded_by_user_id", sa.String(36), nullable=True))
    op.create_index("ix_investment_positions_recorded_by_user_id", "investment_positions", ["recorded_by_user_id"])
    op.create_foreign_key(
        "fk_investment_positions_recorded_by_user_id",
        "investment_positions",
        "users",
        ["recorded_by_user_id"],
        ["id"],
    )

    op.create_table(
        "rentability_credits",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("organization_id", sa.String(36), sa.ForeignKey("organizations.id"), nullable=False, index=True),
        sa.Column("position_id", sa.String(36), sa.ForeignKey("investment_positions.id"), nullable=False, index=True),
        sa.Column("investor_id", sa.String(36), sa.ForeignKey("users.id"), nullable=False, index=True),
        sa.Column("amount", sa.Numeric(15, 2), nullable=False),
        sa.Column("reference_month", sa.String(7), nullable=False, index=True),
        sa.Column("source", sa.String(20), nullable=False, server_default="MANUAL"),
        sa.Column("status", sa.String(30), nullable=False, server_default="POSTED", index=True),
        sa.Column("notes", sa.Text(), nullable=True),
        sa.Column("recorded_by_user_id", sa.String(36), sa.ForeignKey("users.id"), nullable=True, index=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
    )


def downgrade() -> None:
    op.drop_table("rentability_credits")
    op.drop_constraint("fk_investment_positions_recorded_by_user_id", "investment_positions", type_="foreignkey")
    op.drop_index("ix_investment_positions_recorded_by_user_id", "investment_positions")
    op.drop_column("investment_positions", "recorded_by_user_id")
    op.drop_column("investment_positions", "notes")
    op.drop_column("investment_positions", "property_ref")
    op.drop_column("investment_positions", "tokens_qty")
    op.drop_column("investment_positions", "source")
    op.drop_column("investment_positions", "instrument_type")
    op.drop_column("investment_reservations", "instrument_type")
    op.drop_index("ix_funding_opportunities_instrument_type", "funding_opportunities")
    op.drop_column("funding_opportunities", "property_ref")
    op.drop_column("funding_opportunities", "monthly_return_rate")
    op.drop_column("funding_opportunities", "token_unit_price")
    op.drop_column("funding_opportunities", "instrument_type")
