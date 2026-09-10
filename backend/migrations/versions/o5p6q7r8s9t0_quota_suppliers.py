"""Esteira 2 robot fields on quotas.

Revision ID: o5p6q7r8s9t0
Revises: n4o5p6q7r8s9
Create Date: 2026-09-10
"""

from alembic import op
import sqlalchemy as sa

revision = "o5p6q7r8s9t0"
down_revision = "n4o5p6q7r8s9"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "quota_suppliers",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("organization_id", sa.String(length=36), nullable=False),
        sa.Column("active", sa.Boolean(), nullable=False, server_default=sa.text("1")),
        sa.Column("person_type", sa.String(length=2), nullable=False, server_default="PJ"),
        sa.Column("name", sa.String(length=180), nullable=False),
        sa.Column("trade_name", sa.String(length=180), nullable=True),
        sa.Column("document", sa.String(length=20), nullable=False),
        sa.Column("email", sa.String(length=180), nullable=True),
        sa.Column("phone", sa.String(length=40), nullable=True),
        sa.Column("source_key", sa.String(length=80), nullable=False),
        sa.Column("markup_percent", sa.Numeric(8, 2), nullable=False, server_default="0"),
        sa.Column("quem_paga_comissao", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("platform_fee_percent", sa.Numeric(8, 2), nullable=False, server_default="0"),
        sa.Column("bank_name", sa.String(length=120), nullable=True),
        sa.Column("bank_agency", sa.String(length=40), nullable=True),
        sa.Column("bank_account", sa.String(length=40), nullable=True),
        sa.Column("pix_key", sa.String(length=180), nullable=True),
        sa.Column("notes", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["organization_id"], ["organizations.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("organization_id", "source_key"),
    )
    op.create_index("ix_quota_suppliers_organization_id", "quota_suppliers", ["organization_id"])
    op.create_index("ix_quota_suppliers_document", "quota_suppliers", ["document"])
    op.create_index("ix_quota_suppliers_source_key", "quota_suppliers", ["source_key"])


def downgrade() -> None:
    op.drop_index("ix_quota_suppliers_source_key", table_name="quota_suppliers")
    op.drop_index("ix_quota_suppliers_document", table_name="quota_suppliers")
    op.drop_index("ix_quota_suppliers_organization_id", table_name="quota_suppliers")
    op.drop_table("quota_suppliers")
