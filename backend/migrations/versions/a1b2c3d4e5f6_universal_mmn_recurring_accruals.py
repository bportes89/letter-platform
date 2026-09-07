"""Grade universal MMN e apuração recorrente SaaS/taxas bancárias."""

from alembic import op
import sqlalchemy as sa

revision = "a1b2c3d4e5f6"
down_revision = "z0a1b2c3d4e5"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "recurring_commission_accruals",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("organization_id", sa.String(36), sa.ForeignKey("organizations.id"), nullable=False),
        sa.Column("accrual_period", sa.String(7), nullable=False),
        sa.Column("source_type", sa.String(40), nullable=False),
        sa.Column("source_reference", sa.String(120), nullable=False),
        sa.Column("originator_id", sa.String(36), sa.ForeignKey("users.id"), nullable=True),
        sa.Column("gross_amount", sa.Numeric(15, 2), nullable=False),
        sa.Column("network_pool_amount", sa.Numeric(15, 2), nullable=False),
        sa.Column("status", sa.String(30), nullable=False, server_default="ACCRUED"),
        sa.Column("settled_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("settlement_reference", sa.String(120), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.UniqueConstraint(
            "organization_id",
            "source_type",
            "source_reference",
            "accrual_period",
            name="uq_recurring_commission_accrual_source_period",
        ),
    )
    op.create_index(
        "ix_recurring_commission_accruals_period",
        "recurring_commission_accruals",
        ["organization_id", "accrual_period"],
    )


def downgrade() -> None:
    op.drop_index("ix_recurring_commission_accruals_period", table_name="recurring_commission_accruals")
    op.drop_table("recurring_commission_accruals")
