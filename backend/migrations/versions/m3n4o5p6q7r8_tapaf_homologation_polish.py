"""TAPAF Asaas checkout + QuitCon acceptance flags.

Revision ID: m3n4o5p6q7r8
Revises: l2g3h4i5j6k7
Create Date: 2026-09-10
"""

from alembic import op
import sqlalchemy as sa

revision = "m3n4o5p6q7r8"
down_revision = "l2g3h4i5j6k7"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "pre_analysis_pautas",
        sa.Column("asset_type", sa.String(40), nullable=False, server_default="REAL_ESTATE"),
    )
    op.add_column("pre_analysis_pautas", sa.Column("asaas_payment_id", sa.String(80), nullable=True))
    op.add_column("pre_analysis_pautas", sa.Column("external_reference", sa.String(120), nullable=True))
    op.add_column("pre_analysis_pautas", sa.Column("checkout_url", sa.Text(), nullable=True))
    op.add_column("pre_analysis_pautas", sa.Column("pix_copy_paste", sa.Text(), nullable=True))
    op.add_column("pre_analysis_pautas", sa.Column("pix_qr_code", sa.Text(), nullable=True))
    op.add_column("pre_analysis_pautas", sa.Column("checkout_status", sa.String(40), nullable=True))
    op.add_column("pre_analysis_pautas", sa.Column("checkout_mode", sa.String(20), nullable=True))
    op.create_index("ix_pre_analysis_pautas_asaas_payment_id", "pre_analysis_pautas", ["asaas_payment_id"])
    op.create_index("ix_pre_analysis_pautas_external_reference", "pre_analysis_pautas", ["external_reference"])

    op.add_column(
        "operacoes_quitcon",
        sa.Column("tapaf_scroll_completed", sa.Boolean(), nullable=False, server_default=sa.false()),
    )
    op.add_column(
        "operacoes_quitcon",
        sa.Column("tapaf_checkbox_1", sa.Boolean(), nullable=False, server_default=sa.false()),
    )
    op.add_column(
        "operacoes_quitcon",
        sa.Column("tapaf_checkbox_2", sa.Boolean(), nullable=False, server_default=sa.false()),
    )


def downgrade() -> None:
    op.drop_column("operacoes_quitcon", "tapaf_checkbox_2")
    op.drop_column("operacoes_quitcon", "tapaf_checkbox_1")
    op.drop_column("operacoes_quitcon", "tapaf_scroll_completed")

    op.drop_index("ix_pre_analysis_pautas_external_reference", table_name="pre_analysis_pautas")
    op.drop_index("ix_pre_analysis_pautas_asaas_payment_id", table_name="pre_analysis_pautas")
    op.drop_column("pre_analysis_pautas", "checkout_mode")
    op.drop_column("pre_analysis_pautas", "checkout_status")
    op.drop_column("pre_analysis_pautas", "pix_qr_code")
    op.drop_column("pre_analysis_pautas", "pix_copy_paste")
    op.drop_column("pre_analysis_pautas", "checkout_url")
    op.drop_column("pre_analysis_pautas", "external_reference")
    op.drop_column("pre_analysis_pautas", "asaas_payment_id")
    op.drop_column("pre_analysis_pautas", "asset_type")
