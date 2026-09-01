"""escrow account user link for auto plain subaccounts

Revision ID: q1r2s3t4u5v6
Revises: p0q1r2s3t4u5
"""
from alembic import op
import sqlalchemy as sa

revision = "q1r2s3t4u5v6"
down_revision = "p0q1r2s3t4u5"
branch_labels = None
depends_on = None


def upgrade():
    op.add_column("escrow_accounts", sa.Column("user_id", sa.String(36), nullable=True))
    op.create_index("ix_escrow_accounts_user_id", "escrow_accounts", ["user_id"], unique=True)
    op.create_foreign_key(
        "fk_escrow_accounts_user_id",
        "escrow_accounts",
        "users",
        ["user_id"],
        ["id"],
    )


def downgrade():
    op.drop_constraint("fk_escrow_accounts_user_id", "escrow_accounts", type_="foreignkey")
    op.drop_index("ix_escrow_accounts_user_id", table_name="escrow_accounts")
    op.drop_column("escrow_accounts", "user_id")
