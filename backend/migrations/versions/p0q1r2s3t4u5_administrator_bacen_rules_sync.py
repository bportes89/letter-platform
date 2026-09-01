"""administrator bacen rules sync timestamp

Revision ID: p0q1r2s3t4u5
Revises: o9i0j1k2l3m4
"""
from alembic import op
import sqlalchemy as sa

revision = "p0q1r2s3t4u5"
down_revision = "o9i0j1k2l3m4"
branch_labels = None
depends_on = None


def upgrade():
    op.add_column(
        "administrators",
        sa.Column("bacen_rules_synced_at", sa.DateTime(timezone=True), nullable=True),
    )


def downgrade():
    op.drop_column("administrators", "bacen_rules_synced_at")
