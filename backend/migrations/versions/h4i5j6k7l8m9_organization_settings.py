"""Organization settings key-value (legacy x_settings).

Revision ID: h4i5j6k7l8m9
Revises: g3h4i5j6k7l8
Create Date: 2026-09-30
"""

from alembic import op
import sqlalchemy as sa

revision = "h4i5j6k7l8m9"
down_revision = "g3h4i5j6k7l8"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "organization_settings",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("organization_id", sa.String(length=36), nullable=False),
        sa.Column("field_key", sa.String(length=80), nullable=False),
        sa.Column("value", sa.Text(), nullable=False, server_default=""),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["organization_id"], ["organizations.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("organization_id", "field_key", name="uq_org_setting_key"),
    )
    op.create_index("ix_organization_settings_organization_id", "organization_settings", ["organization_id"])
    op.create_index("ix_organization_settings_field_key", "organization_settings", ["field_key"])


def downgrade() -> None:
    op.drop_index("ix_organization_settings_field_key", table_name="organization_settings")
    op.drop_index("ix_organization_settings_organization_id", table_name="organization_settings")
    op.drop_table("organization_settings")
