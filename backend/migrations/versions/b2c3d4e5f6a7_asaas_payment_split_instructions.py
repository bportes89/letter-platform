"""Instruções de split nativo Asaas (MMN na fonte)."""

from alembic import op
import sqlalchemy as sa

revision = "b2c3d4e5f6a7"
down_revision = "a1b2c3d4e5f6"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "payment_split_instructions",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("organization_id", sa.String(36), sa.ForeignKey("organizations.id"), nullable=False),
        sa.Column("reference", sa.String(120), nullable=False),
        sa.Column("asaas_payment_id", sa.String(80)),
        sa.Column("beneficiary_id", sa.String(36), sa.ForeignKey("users.id")),
        sa.Column("commission_entry_id", sa.String(36), sa.ForeignKey("commission_entries.id")),
        sa.Column("layer_name", sa.String(30), nullable=False),
        sa.Column("level", sa.Integer(), nullable=False),
        sa.Column("wallet_id", sa.String(120)),
        sa.Column("amount", sa.Numeric(15, 2), nullable=False),
        sa.Column("asaas_split_id", sa.String(80)),
        sa.Column("status", sa.String(30), nullable=False, server_default="PLANNED"),
        sa.Column("detail_json", sa.Text(), nullable=False, server_default="{}"),
        sa.Column("settled_at", sa.DateTime(timezone=True)),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.UniqueConstraint("reference", "level", "beneficiary_id", name="uq_payment_split_reference_level_beneficiary"),
    )
    op.create_index("ix_payment_split_instructions_reference", "payment_split_instructions", ["reference"])
    op.create_index("ix_payment_split_instructions_asaas_payment_id", "payment_split_instructions", ["asaas_payment_id"])
    op.create_index("ix_payment_split_instructions_asaas_split_id", "payment_split_instructions", ["asaas_split_id"])
    op.create_index("ix_payment_split_instructions_status", "payment_split_instructions", ["status"])


def downgrade() -> None:
    op.drop_index("ix_payment_split_instructions_status", table_name="payment_split_instructions")
    op.drop_index("ix_payment_split_instructions_asaas_split_id", table_name="payment_split_instructions")
    op.drop_index("ix_payment_split_instructions_asaas_payment_id", table_name="payment_split_instructions")
    op.drop_index("ix_payment_split_instructions_reference", table_name="payment_split_instructions")
    op.drop_table("payment_split_instructions")
