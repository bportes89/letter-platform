"""Flash desk: checklist config + operation type.

Revision ID: c9d0e1f2a3b4
Revises: b8c9d0e1f2a3
Create Date: 2026-09-29
"""

from alembic import op
import sqlalchemy as sa

revision = "c9d0e1f2a3b4"
down_revision = "b8c9d0e1f2a3"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("flash_solicitations", sa.Column("operation_type", sa.String(length=30), nullable=True))
    op.create_index("ix_flash_solicitations_operation_type", "flash_solicitations", ["operation_type"])

    op.create_table(
        "flash_checklist_configs",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("organization_id", sa.String(length=36), nullable=False),
        sa.Column("asset_category", sa.String(length=40), nullable=False),
        sa.Column("operation_type", sa.String(length=30), nullable=False),
        sa.Column("items_json", sa.Text(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.ForeignKeyConstraint(["organization_id"], ["organizations.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("organization_id", "asset_category", "operation_type", name="uq_flash_checklist_org_cat_op"),
    )
    op.create_index("ix_flash_checklist_configs_organization_id", "flash_checklist_configs", ["organization_id"])
    op.create_index("ix_flash_checklist_configs_asset_category", "flash_checklist_configs", ["asset_category"])
    op.create_index("ix_flash_checklist_configs_operation_type", "flash_checklist_configs", ["operation_type"])


def downgrade() -> None:
    op.drop_index("ix_flash_checklist_configs_operation_type", table_name="flash_checklist_configs")
    op.drop_index("ix_flash_checklist_configs_asset_category", table_name="flash_checklist_configs")
    op.drop_index("ix_flash_checklist_configs_organization_id", table_name="flash_checklist_configs")
    op.drop_table("flash_checklist_configs")
    op.drop_index("ix_flash_solicitations_operation_type", table_name="flash_solicitations")
    op.drop_column("flash_solicitations", "operation_type")
