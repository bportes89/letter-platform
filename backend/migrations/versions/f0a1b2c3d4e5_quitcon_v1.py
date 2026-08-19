"""quitcon operacoes tapaf multas sla v1

Revision ID: f0a1b2c3d4e5
Revises: e9f0a1b2c3d4
"""
from alembic import op
import sqlalchemy as sa

revision = "f0a1b2c3d4e5"
down_revision = "e9f0a1b2c3d4"
branch_labels = None
depends_on = None


def upgrade():
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    if "operacoes_quitcon" not in inspector.get_table_names():
        op.create_table(
            "operacoes_quitcon",
            sa.Column("id", sa.String(36), primary_key=True),
            sa.Column("organization_id", sa.String(36), sa.ForeignKey("organizations.id"), nullable=False),
            sa.Column("proposal_id", sa.String(36), sa.ForeignKey("proposals.id"), nullable=False),
            sa.Column("quota_id", sa.String(36), sa.ForeignKey("quotas.id")),
            sa.Column("owner_user_id", sa.String(36), sa.ForeignKey("users.id"), nullable=False),
            sa.Column("operacao_code", sa.String(80), nullable=False),
            sa.Column("status", sa.String(50), nullable=False, server_default="AGUARDANDO_TAPAF"),
            sa.Column("property_type", sa.String(40), nullable=False),
            sa.Column("appraisal_value", sa.Numeric(15, 2), nullable=False),
            sa.Column("outstanding_balance", sa.Numeric(15, 2), nullable=False),
            sa.Column("registry_number", sa.String(80), nullable=False),
            sa.Column("registry_office", sa.String(180), nullable=False),
            sa.Column("tapaf_payment_reference", sa.String(120)),
            sa.Column("tapaf_paid_at", sa.DateTime(timezone=True)),
            sa.Column("compliance_dossier_uri", sa.String(500)),
            sa.Column("compliance_blockers_json", sa.Text()),
            sa.Column("inspection_photos_count", sa.Integer(), nullable=False, server_default="0"),
            sa.Column("inspection_metadata_json", sa.Text()),
            sa.Column("inspection_cost_amount", sa.Numeric(15, 2), nullable=False, server_default="0"),
            sa.Column("gravame_certificate_uri", sa.String(500)),
            sa.Column("administrator_approved_at", sa.DateTime(timezone=True)),
            sa.Column("sla_estimated_completion_at", sa.DateTime(timezone=True)),
            sa.Column("success_fee_escrow_amount", sa.Numeric(15, 2), nullable=False),
            sa.Column("funding_target_amount", sa.Numeric(15, 2), nullable=False),
            sa.Column("funding_captured_amount", sa.Numeric(15, 2), nullable=False, server_default="0"),
            sa.Column("activation_at", sa.DateTime(timezone=True)),
            sa.Column("activated_manually", sa.Boolean(), nullable=False, server_default=sa.false()),
            sa.Column("months_in_force", sa.Integer(), nullable=False, server_default="0"),
            sa.Column("anticipation_unlock_at", sa.DateTime(timezone=True)),
            sa.Column("cancellation_reason", sa.String(80)),
            sa.Column("penalty_amount", sa.Numeric(15, 2)),
            sa.Column("penalty_detail_json", sa.Text()),
            sa.Column("tokenization_json", sa.Text()),
            sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
            sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
            sa.UniqueConstraint("organization_id", "proposal_id"),
        )
        for name in ("organization_id", "proposal_id", "status", "operacao_code"):
            op.create_index(f"ix_operacoes_quitcon_{name}", "operacoes_quitcon", [name])
        op.create_table(
            "quitcon_status_logs",
            sa.Column("id", sa.String(36), primary_key=True),
            sa.Column("organization_id", sa.String(36), sa.ForeignKey("organizations.id"), nullable=False),
            sa.Column("operacao_id", sa.String(36), sa.ForeignKey("operacoes_quitcon.id"), nullable=False),
            sa.Column("from_status", sa.String(50), nullable=False),
            sa.Column("to_status", sa.String(50), nullable=False),
            sa.Column("actor_id", sa.String(36), sa.ForeignKey("users.id"), nullable=False),
            sa.Column("note", sa.String(500), nullable=False, server_default=""),
            sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        )
        for name in ("organization_id", "operacao_id", "to_status", "created_at"):
            op.create_index(f"ix_quitcon_status_logs_{name}", "quitcon_status_logs", [name])
    cols = {c["name"] for c in inspector.get_columns("collateral_native_inspections")}
    if "quitcon_operacao_id" not in cols:
        op.add_column(
            "collateral_native_inspections",
            sa.Column("quitcon_operacao_id", sa.String(36), sa.ForeignKey("operacoes_quitcon.id")),
        )
        op.create_index(
            "ix_collateral_native_inspections_quitcon_operacao_id",
            "collateral_native_inspections",
            ["quitcon_operacao_id"],
        )


def downgrade():
    op.drop_index("ix_collateral_native_inspections_quitcon_operacao_id", table_name="collateral_native_inspections")
    op.drop_column("collateral_native_inspections", "quitcon_operacao_id")
    op.drop_table("quitcon_status_logs")
    op.drop_table("operacoes_quitcon")
