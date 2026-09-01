"""Company profile fields on users for PJ partner subaccounts

Revision ID: v6w7x8y9z0a1
Revises: u5v6w7x8y9z0
"""
from alembic import op
import sqlalchemy as sa

revision = "v6w7x8y9z0a1"
down_revision = "u5v6w7x8y9z0"
branch_labels = None
depends_on = None


def upgrade():
    op.add_column("users", sa.Column("company_name", sa.String(180), nullable=True))
    op.add_column("users", sa.Column("company_cnpj", sa.String(20), nullable=True))
    op.add_column("users", sa.Column("company_address", sa.String(240), nullable=True))
    op.add_column("users", sa.Column("company_city", sa.String(120), nullable=True))
    op.add_column("users", sa.Column("company_state", sa.String(2), nullable=True))


def downgrade():
    op.drop_column("users", "company_state")
    op.drop_column("users", "company_city")
    op.drop_column("users", "company_address")
    op.drop_column("users", "company_cnpj")
    op.drop_column("users", "company_name")
