"""client self-registration phone and referrer

Revision ID: n8h9i0j1k2l3
Revises: m7g8h9i0j1k2
"""
from alembic import op
import sqlalchemy as sa

revision = "n8h9i0j1k2l3"
down_revision = "m7g8h9i0j1k2"
branch_labels = None
depends_on = None


def upgrade():
    op.add_column("users", sa.Column("phone", sa.String(30), nullable=True))
    op.add_column("users", sa.Column("referred_by_user_id", sa.String(36), nullable=True))
    op.create_index("ix_users_referred_by_user_id", "users", ["referred_by_user_id"])
    op.create_foreign_key(
        "fk_users_referred_by_user_id",
        "users",
        "users",
        ["referred_by_user_id"],
        ["id"],
    )


def downgrade():
    op.drop_constraint("fk_users_referred_by_user_id", "users", type_="foreignkey")
    op.drop_index("ix_users_referred_by_user_id", table_name="users")
    op.drop_column("users", "referred_by_user_id")
    op.drop_column("users", "phone")
