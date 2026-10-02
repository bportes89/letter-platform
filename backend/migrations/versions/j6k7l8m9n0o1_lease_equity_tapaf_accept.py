"""Lease Equity TAPAF checkout accept (alinhado QuitCon / pré-análise).

Revision ID: j6k7l8m9n0o1
Revises: i5j6k7l8m9n0
Create Date: 2026-10-01
"""

from alembic import op
import sqlalchemy as sa

revision = "j6k7l8m9n0o1"
down_revision = "i5j6k7l8m9n0"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "lease_equity_pautas",
        sa.Column("tapaf_scroll_completed", sa.Boolean(), nullable=False, server_default=sa.false()),
    )
    op.add_column(
        "lease_equity_pautas",
        sa.Column("tapaf_checkbox_1", sa.Boolean(), nullable=False, server_default=sa.false()),
    )
    op.add_column(
        "lease_equity_pautas",
        sa.Column("tapaf_checkbox_2", sa.Boolean(), nullable=False, server_default=sa.false()),
    )


def downgrade() -> None:
    op.drop_column("lease_equity_pautas", "tapaf_checkbox_2")
    op.drop_column("lease_equity_pautas", "tapaf_checkbox_1")
    op.drop_column("lease_equity_pautas", "tapaf_scroll_completed")
