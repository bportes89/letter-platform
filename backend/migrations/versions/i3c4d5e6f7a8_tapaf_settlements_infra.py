"""tapaf settlements split and infra inventory

Revision ID: i3c4d5e6f7a8
Revises: h2b3c4d5e6f7
"""
from alembic import op
import sqlalchemy as sa

revision = "i3c4d5e6f7a8"
down_revision = "h2b3c4d5e6f7"
branch_labels = None
depends_on = None


def upgrade():
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    if "tapaf_settlements" in inspector.get_table_names():
        return
    op.create_table(
        "tapaf_settlements",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("organization_id", sa.String(36), sa.ForeignKey("organizations.id"), nullable=False),
        sa.Column("track", sa.String(30), nullable=False),
        sa.Column("entity_type", sa.String(60), nullable=False),
        sa.Column("entity_id", sa.String(36), nullable=False),
        sa.Column("payment_event_id", sa.String(120), nullable=False),
        sa.Column("total_amount", sa.Numeric(15, 2), nullable=False),
        sa.Column("lote_a_amount", sa.Numeric(15, 2), nullable=False),
        sa.Column("lote_b_amount", sa.Numeric(15, 2), nullable=False),
        sa.Column("ledger_reference", sa.String(120), nullable=False),
        sa.Column("inventory_json", sa.Text(), nullable=False, server_default="{}"),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.UniqueConstraint("organization_id", "payment_event_id", name="uq_tapaf_settlement_payment_event"),
    )
    op.create_index("ix_tapaf_settlements_org_entity", "tapaf_settlements", ["organization_id", "entity_type", "entity_id"])


def downgrade():
    op.drop_index("ix_tapaf_settlements_org_entity", table_name="tapaf_settlements")
    op.drop_table("tapaf_settlements")
