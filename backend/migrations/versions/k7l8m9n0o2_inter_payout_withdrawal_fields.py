"""Campos Inter PIX saída em saques parceiro/fornecedor.

Revision ID: k7l8m9n0o2
Revises: j6k7l8m9n0o1
Create Date: 2026-10-01
"""

from alembic import op
import sqlalchemy as sa

revision = "k7l8m9n0o2"
down_revision = "j6k7l8m9n0o1"
branch_labels = None
depends_on = None


def _add_inter_cols(table: str) -> None:
    op.add_column(table, sa.Column("inter_codigo_solicitacao", sa.String(80), nullable=True))
    op.add_column(table, sa.Column("inter_end_to_end_id", sa.String(80), nullable=True))
    op.add_column(table, sa.Column("inter_payment_json", sa.Text(), nullable=True))
    op.add_column(table, sa.Column("payment_error", sa.Text(), nullable=True))
    op.create_index(f"ix_{table}_inter_codigo_solicitacao", table, ["inter_codigo_solicitacao"])
    op.create_index(f"ix_{table}_inter_end_to_end_id", table, ["inter_end_to_end_id"])


def upgrade() -> None:
    _add_inter_cols("partner_withdrawals")
    _add_inter_cols("supplier_withdrawals")


def downgrade() -> None:
    for table in ("supplier_withdrawals", "partner_withdrawals"):
        op.drop_index(f"ix_{table}_inter_end_to_end_id", table_name=table)
        op.drop_index(f"ix_{table}_inter_codigo_solicitacao", table_name=table)
        op.drop_column(table, "payment_error")
        op.drop_column(table, "inter_payment_json")
        op.drop_column(table, "inter_end_to_end_id")
        op.drop_column(table, "inter_codigo_solicitacao")
