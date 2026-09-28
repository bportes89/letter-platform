"""SDC desk: operation type, checklist config, status log, upload batches.

Revision ID: b8c9d0e1f2a3
Revises: a7b8c9d0e1f2
Create Date: 2026-09-28
"""

from alembic import op
import sqlalchemy as sa

revision = "b8c9d0e1f2a3"
down_revision = "a7b8c9d0e1f2"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("sdc_solicitations", sa.Column("asset_category", sa.String(length=40), nullable=True))
    op.add_column("sdc_solicitations", sa.Column("operation_type", sa.String(length=20), nullable=True))
    op.add_column("sdc_solicitations", sa.Column("partner_observation", sa.Text(), nullable=True))
    op.add_column("sdc_solicitations", sa.Column("status_log_json", sa.Text(), nullable=True))
    op.add_column("sdc_solicitations", sa.Column("pending_doc_codes_json", sa.Text(), nullable=True))
    op.create_index("ix_sdc_solicitations_asset_category", "sdc_solicitations", ["asset_category"])
    op.create_index("ix_sdc_solicitations_operation_type", "sdc_solicitations", ["operation_type"])

    op.add_column(
        "sdc_solicitation_documents",
        sa.Column("upload_batch", sa.String(length=20), nullable=False, server_default="INITIAL"),
    )
    op.create_index("ix_sdc_solicitation_documents_upload_batch", "sdc_solicitation_documents", ["upload_batch"])

    op.create_table(
        "sdc_checklist_configs",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("organization_id", sa.String(length=36), nullable=False),
        sa.Column("asset_category", sa.String(length=40), nullable=False),
        sa.Column("operation_type", sa.String(length=20), nullable=False),
        sa.Column("items_json", sa.Text(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.ForeignKeyConstraint(["organization_id"], ["organizations.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("organization_id", "asset_category", "operation_type", name="uq_sdc_checklist_org_cat_op"),
    )
    op.create_index("ix_sdc_checklist_configs_organization_id", "sdc_checklist_configs", ["organization_id"])
    op.create_index("ix_sdc_checklist_configs_asset_category", "sdc_checklist_configs", ["asset_category"])
    op.create_index("ix_sdc_checklist_configs_operation_type", "sdc_checklist_configs", ["operation_type"])


def downgrade() -> None:
    op.drop_table("sdc_checklist_configs")
    op.drop_index("ix_sdc_solicitation_documents_upload_batch", table_name="sdc_solicitation_documents")
    op.drop_column("sdc_solicitation_documents", "upload_batch")
    op.drop_index("ix_sdc_solicitations_operation_type", table_name="sdc_solicitations")
    op.drop_index("ix_sdc_solicitations_asset_category", table_name="sdc_solicitations")
    op.drop_column("sdc_solicitations", "pending_doc_codes_json")
    op.drop_column("sdc_solicitations", "status_log_json")
    op.drop_column("sdc_solicitations", "partner_observation")
    op.drop_column("sdc_solicitations", "operation_type")
    op.drop_column("sdc_solicitations", "asset_category")
