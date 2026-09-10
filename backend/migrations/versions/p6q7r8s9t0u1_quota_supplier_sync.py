"""Quota supplier sync fields + quota external_ref.

Revision ID: p6q7r8s9t0u1
Revises: o5p6q7r8s9t0
Create Date: 2026-09-10
"""

from alembic import op
import sqlalchemy as sa

revision = "p6q7r8s9t0u1"
down_revision = "o5p6q7r8s9t0"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("quota_suppliers", sa.Column("sync_mode", sa.String(length=20), nullable=False, server_default="NONE"))
    op.add_column("quota_suppliers", sa.Column("api_url", sa.String(length=500), nullable=True))
    op.add_column("quota_suppliers", sa.Column("last_sync_at", sa.DateTime(timezone=True), nullable=True))
    op.add_column("quota_suppliers", sa.Column("last_sync_status", sa.String(length=40), nullable=True))
    op.add_column("quota_suppliers", sa.Column("last_sync_detail_json", sa.Text(), nullable=False, server_default="{}"))

    op.add_column("quotas", sa.Column("external_ref", sa.String(length=120), nullable=True))
    op.add_column("quotas", sa.Column("sync_origin", sa.String(length=20), nullable=False, server_default="MANUAL"))
    op.add_column("quotas", sa.Column("synced_at", sa.DateTime(timezone=True), nullable=True))
    op.add_column("quotas", sa.Column("administrator_name_txt", sa.String(length=180), nullable=True))
    op.create_index("ix_quotas_external_ref", "quotas", ["external_ref"])
    op.create_index("ix_quotas_sync_origin", "quotas", ["sync_origin"])


def downgrade() -> None:
    op.drop_index("ix_quotas_sync_origin", table_name="quotas")
    op.drop_index("ix_quotas_external_ref", table_name="quotas")
    op.drop_column("quotas", "administrator_name_txt")
    op.drop_column("quotas", "synced_at")
    op.drop_column("quotas", "sync_origin")
    op.drop_column("quotas", "external_ref")
    op.drop_column("quota_suppliers", "last_sync_detail_json")
    op.drop_column("quota_suppliers", "last_sync_status")
    op.drop_column("quota_suppliers", "last_sync_at")
    op.drop_column("quota_suppliers", "api_url")
    op.drop_column("quota_suppliers", "sync_mode")
