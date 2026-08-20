"""quitcon operational service fee at process start

Revision ID: h2b3c4d5e6f7
Revises: g1a2b3c4d5e6
"""
from alembic import op
import sqlalchemy as sa

revision = "h2b3c4d5e6f7"
down_revision = "g1a2b3c4d5e6"
branch_labels = None
depends_on = None


def upgrade():
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    if "operacoes_quitcon" not in inspector.get_table_names():
        return
    cols = {c["name"] for c in inspector.get_columns("operacoes_quitcon")}
    if "operational_service_fee_amount" not in cols:
        op.add_column("operacoes_quitcon", sa.Column("operational_service_fee_amount", sa.Numeric(15, 2)))
    if "operational_service_paid_at" not in cols:
        op.add_column("operacoes_quitcon", sa.Column("operational_service_paid_at", sa.DateTime(timezone=True)))


def downgrade():
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    if "operacoes_quitcon" not in inspector.get_table_names():
        return
    cols = {c["name"] for c in inspector.get_columns("operacoes_quitcon")}
    if "operational_service_paid_at" in cols:
        op.drop_column("operacoes_quitcon", "operational_service_paid_at")
    if "operational_service_fee_amount" in cols:
        op.drop_column("operacoes_quitcon", "operational_service_fee_amount")
