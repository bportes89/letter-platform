"""User granular admin permissions.

Revision ID: x4y5z6a7b8c9
Revises: w3x4y5z6a7b8
Create Date: 2026-09-16
"""

from alembic import op
import sqlalchemy as sa

revision = "x4y5z6a7b8c9"
down_revision = "w3x4y5z6a7b8"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("users", sa.Column("access_all", sa.Boolean(), nullable=False, server_default="0"))
    op.add_column("users", sa.Column("permissions_json", sa.Text(), nullable=True))
    op.execute("UPDATE users SET access_all = 1 WHERE role = 'PLATFORM_ADMIN'")


def downgrade() -> None:
    op.drop_column("users", "permissions_json")
    op.drop_column("users", "access_all")
