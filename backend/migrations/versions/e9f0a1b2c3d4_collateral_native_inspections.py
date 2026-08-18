"""collateral native inspections sdc flash lease equity

Revision ID: e9f0a1b2c3d4
Revises: d8e9f0a1b2c3
"""
from alembic import op
import sqlalchemy as sa

revision = "e9f0a1b2c3d4"
down_revision = "d8e9f0a1b2c3"
branch_labels = None
depends_on = None


def upgrade():
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    if "collateral_native_inspections" in inspector.get_table_names():
        return
    op.create_table(
        "collateral_native_inspections",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("organization_id", sa.String(36), sa.ForeignKey("organizations.id"), nullable=False),
        sa.Column("product", sa.String(40), nullable=False),
        sa.Column("proposal_id", sa.String(36), sa.ForeignKey("proposals.id"), nullable=False),
        sa.Column("contract_id", sa.String(36), sa.ForeignKey("contracts.id")),
        sa.Column("lease_equity_pauta_id", sa.String(36), sa.ForeignKey("lease_equity_pautas.id")),
        sa.Column("photos_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("metadata_json", sa.Text(), nullable=False, server_default="[]"),
        sa.Column("vault_s3_uri", sa.String(500), nullable=False),
        sa.Column("auction_evidence_ready", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.UniqueConstraint("organization_id", "proposal_id"),
    )
    for name in ("organization_id", "product", "proposal_id", "contract_id"):
        op.create_index(f"ix_collateral_native_inspections_{name}", "collateral_native_inspections", [name])


def downgrade():
    op.drop_table("collateral_native_inspections")
