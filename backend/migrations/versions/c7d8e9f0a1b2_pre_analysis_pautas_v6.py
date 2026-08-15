"""pre analysis pautas ocr tapaf engine v6

Revision ID: c7d8e9f0a1b2
Revises: b6c7d8e9f0a1
"""
from alembic import op
import sqlalchemy as sa

revision = "c7d8e9f0a1b2"
down_revision = "b6c7d8e9f0a1"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "pre_analysis_pautas",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("organization_id", sa.String(36), sa.ForeignKey("organizations.id"), nullable=False),
        sa.Column("proposal_id", sa.String(36), sa.ForeignKey("proposals.id"), nullable=False),
        sa.Column("pauta_code", sa.String(80), nullable=False),
        sa.Column("status", sa.String(50), nullable=False, server_default="PENDING_DOCUMENTS"),
        sa.Column("documents_json", sa.Text(), nullable=False, server_default="[]"),
        sa.Column("tapaf_scroll_completed", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("tapaf_checkbox_1", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("tapaf_checkbox_2", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("tapaf_payment_reference", sa.String(120)),
        sa.Column("tapaf_paid_at", sa.DateTime(timezone=True)),
        sa.Column("engine_result_json", sa.Text()),
        sa.Column("client_result_json", sa.Text()),
        sa.Column("valid_stamp_hash", sa.String(128)),
        sa.Column("vault_s3_uri", sa.String(500)),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.UniqueConstraint("organization_id", "proposal_id"),
    )
    op.create_index("ix_pre_analysis_pautas_organization_id", "pre_analysis_pautas", ["organization_id"])
    op.create_index("ix_pre_analysis_pautas_proposal_id", "pre_analysis_pautas", ["proposal_id"])
    op.create_index("ix_pre_analysis_pautas_pauta_code", "pre_analysis_pautas", ["pauta_code"])
    op.create_index("ix_pre_analysis_pautas_status", "pre_analysis_pautas", ["status"])


def downgrade():
    op.drop_table("pre_analysis_pautas")
