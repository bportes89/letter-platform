"""quota installment due date and nina scan fields

Revision ID: m7g8h9i0j1k2
Revises: l6f7a8b9c0d1
"""
from alembic import op
import sqlalchemy as sa

revision = "m7g8h9i0j1k2"
down_revision = "l6f7a8b9c0d1"
branch_labels = None
depends_on = None


def upgrade():
    op.add_column("quotas", sa.Column("installment_due_date", sa.Date(), nullable=True))
    op.add_column("quotas", sa.Column("nina_scan_status", sa.String(30), nullable=True))
    op.add_column("quotas", sa.Column("nina_scanned_at", sa.DateTime(timezone=True), nullable=True))
    op.add_column("quotas", sa.Column("nina_scan_detail_json", sa.Text(), nullable=False, server_default="{}"))


def downgrade():
    op.drop_column("quotas", "nina_scan_detail_json")
    op.drop_column("quotas", "nina_scanned_at")
    op.drop_column("quotas", "nina_scan_status")
    op.drop_column("quotas", "installment_due_date")
