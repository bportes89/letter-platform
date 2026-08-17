"""lease equity pautas tapaf rwa tokenization v1

Revision ID: d8e9f0a1b2c3
Revises: c7d8e9f0a1b2
"""
from alembic import op
import sqlalchemy as sa

revision = "d8e9f0a1b2c3"
down_revision = "c7d8e9f0a1b2"
branch_labels = None
depends_on = None


def upgrade():
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    if "lease_equity_pautas" in inspector.get_table_names():
        return
    op.create_table(
        "lease_equity_pautas",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("organization_id", sa.String(36), sa.ForeignKey("organizations.id"), nullable=False),
        sa.Column("proposal_id", sa.String(36), sa.ForeignKey("proposals.id"), nullable=False),
        sa.Column("owner_user_id", sa.String(36), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("pauta_code", sa.String(80), nullable=False),
        sa.Column("status", sa.String(50), nullable=False, server_default="AGUARDANDO_TAPAF"),
        sa.Column("property_type", sa.String(40), nullable=False),
        sa.Column("appraisal_value", sa.Numeric(15, 2), nullable=False),
        sa.Column("registry_number", sa.String(80), nullable=False),
        sa.Column("registry_office", sa.String(180), nullable=False),
        sa.Column("tapaf_payment_reference", sa.String(120)),
        sa.Column("tapaf_paid_at", sa.DateTime(timezone=True)),
        sa.Column("compliance_dossier_uri", sa.String(500)),
        sa.Column("compliance_blockers_json", sa.Text()),
        sa.Column("inspection_photos_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("inspection_metadata_json", sa.Text()),
        sa.Column("gravame_certificate_uri", sa.String(500)),
        sa.Column("funding_target_amount", sa.Numeric(15, 2), nullable=False),
        sa.Column("funding_captured_amount", sa.Numeric(15, 2), nullable=False, server_default="0"),
        sa.Column("activation_at", sa.DateTime(timezone=True)),
        sa.Column("activated_manually", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("months_in_force", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("anticipation_unlock_at", sa.DateTime(timezone=True)),
        sa.Column("tokenization_json", sa.Text()),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.UniqueConstraint("organization_id", "proposal_id"),
    )
    for name in ("organization_id", "proposal_id", "status", "pauta_code"):
        op.create_index(f"ix_lease_equity_pautas_{name}", "lease_equity_pautas", [name])
    op.create_table(
        "lease_equity_status_logs",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("organization_id", sa.String(36), sa.ForeignKey("organizations.id"), nullable=False),
        sa.Column("pauta_id", sa.String(36), sa.ForeignKey("lease_equity_pautas.id"), nullable=False),
        sa.Column("from_status", sa.String(50), nullable=False),
        sa.Column("to_status", sa.String(50), nullable=False),
        sa.Column("actor_id", sa.String(36), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("note", sa.String(500), nullable=False, server_default=""),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
    )
    for name in ("organization_id", "pauta_id", "to_status", "created_at"):
        op.create_index(f"ix_lease_equity_status_logs_{name}", "lease_equity_status_logs", [name])


def downgrade():
    op.drop_table("lease_equity_status_logs")
    op.drop_table("lease_equity_pautas")
