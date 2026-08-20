"""quitcon doc253 product fields escrow cedente

Revision ID: g1a2b3c4d5e6
Revises: f0a1b2c3d4e5
"""
from alembic import op
import sqlalchemy as sa

revision = "g1a2b3c4d5e6"
down_revision = "f0a1b2c3d4e5"
branch_labels = None
depends_on = None


def upgrade():
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    if "operacoes_quitcon" not in inspector.get_table_names():
        return
    cols = {c["name"] for c in inspector.get_columns("operacoes_quitcon")}
    additions = [
        ("meses_restantes", sa.Column("meses_restantes", sa.Integer(), server_default="48")),
        ("quitacao_vp_amount", sa.Column("quitacao_vp_amount", sa.Numeric(15, 2))),
        ("operational_service_enabled", sa.Column("operational_service_enabled", sa.Boolean(), server_default=sa.false())),
        ("success_fee_escrow_paid_at", sa.Column("success_fee_escrow_paid_at", sa.DateTime(timezone=True))),
        ("success_fee_escrow_reference", sa.Column("success_fee_escrow_reference", sa.String(120))),
        ("success_fee_refunded", sa.Column("success_fee_refunded", sa.Boolean(), server_default=sa.false())),
        ("cedente_payment_amount", sa.Column("cedente_payment_amount", sa.Numeric(15, 2))),
        ("cedente_payment_due_at", sa.Column("cedente_payment_due_at", sa.DateTime(timezone=True))),
        ("cedente_payment_escrow_reference", sa.Column("cedente_payment_escrow_reference", sa.String(120))),
        ("product_snapshot_json", sa.Column("product_snapshot_json", sa.Text())),
    ]
    for name, col in additions:
        if name not in cols:
            op.add_column("operacoes_quitcon", col)


def downgrade():
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    if "operacoes_quitcon" not in inspector.get_table_names():
        return
    for name in (
        "product_snapshot_json", "cedente_payment_escrow_reference", "cedente_payment_due_at",
        "cedente_payment_amount", "success_fee_refunded", "success_fee_escrow_reference",
        "success_fee_escrow_paid_at", "operational_service_enabled", "quitacao_vp_amount", "meses_restantes",
    ):
        cols = {c["name"] for c in inspector.get_columns("operacoes_quitcon")}
        if name in cols:
            op.drop_column("operacoes_quitcon", name)
