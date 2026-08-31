"""sefaz fields on fiscal evidences

Revision ID: k5e6f7a8b9c0
Revises: j4d5e6f7a8b9
"""
from alembic import op
import sqlalchemy as sa

revision = "k5e6f7a8b9c0"
down_revision = "j4d5e6f7a8b9"
branch_labels = None
depends_on = None


def upgrade():
    op.add_column("fiscal_evidences", sa.Column("access_key", sa.String(44), nullable=True))
    op.add_column("fiscal_evidences", sa.Column("sefaz_status", sa.String(30), nullable=True))
    op.add_column("fiscal_evidences", sa.Column("gross_amount", sa.Numeric(15, 2), nullable=True))
    op.add_column("fiscal_evidences", sa.Column("detail_json", sa.Text(), nullable=False, server_default="{}"))
    op.create_index(op.f("ix_fiscal_evidences_access_key"), "fiscal_evidences", ["access_key"], unique=False)


def downgrade():
    op.drop_index(op.f("ix_fiscal_evidences_access_key"), table_name="fiscal_evidences")
    op.drop_column("fiscal_evidences", "detail_json")
    op.drop_column("fiscal_evidences", "gross_amount")
    op.drop_column("fiscal_evidences", "sefaz_status")
    op.drop_column("fiscal_evidences", "access_key")
