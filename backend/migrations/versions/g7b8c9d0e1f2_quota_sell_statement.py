"""Add statement_document_id to quota_sell_offers.

Revision ID: g7b8c9d0e1f2
Revises: f6a7b8c9d0e1
Create Date: 2026-09-10
"""

from alembic import op
import sqlalchemy as sa

revision = "g7b8c9d0e1f2"
down_revision = "f6a7b8c9d0e1"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "quota_sell_offers",
        sa.Column("statement_document_id", sa.String(36), sa.ForeignKey("documents.id"), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("quota_sell_offers", "statement_document_id")
