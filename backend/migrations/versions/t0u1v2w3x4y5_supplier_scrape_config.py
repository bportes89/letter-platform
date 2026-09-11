"""Quota supplier scrape_config_json for HTML inventory sync.

Revision ID: t0u1v2w3x4y5
Revises: s9t0u1v2w3x4
Create Date: 2026-09-11
"""

from alembic import op
import sqlalchemy as sa

revision = "t0u1v2w3x4y5"
down_revision = "s9t0u1v2w3x4"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "quota_suppliers",
        sa.Column("scrape_config_json", sa.Text(), nullable=False, server_default="{}"),
    )


def downgrade() -> None:
    op.drop_column("quota_suppliers", "scrape_config_json")
