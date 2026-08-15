"""finops simulator settlement quotes and domain events

Revision ID: 94e5f6a7b8c9
Revises: 83d4e5f6a7b8
"""
from alembic import op
import sqlalchemy as sa

revision="94e5f6a7b8c9";down_revision="83d4e5f6a7b8";branch_labels=None;depends_on=None

def upgrade():
    op.create_table("early_settlement_quotes",
      sa.Column("id",sa.String(36),primary_key=True),sa.Column("organization_id",sa.String(36),sa.ForeignKey("organizations.id"),nullable=False),sa.Column("contract_id",sa.String(36),sa.ForeignKey("contracts.id"),nullable=False),sa.Column("requested_by_id",sa.String(36),sa.ForeignKey("users.id"),nullable=False),sa.Column("installment_number",sa.Integer(),nullable=False),sa.Column("track",sa.String(30),nullable=False),sa.Column("balloon",sa.Boolean(),nullable=False),sa.Column("principal",sa.Numeric(15,2),nullable=False),sa.Column("settlement_amount",sa.Numeric(15,2),nullable=False),sa.Column("future_interest_discount",sa.Numeric(15,2),nullable=False),sa.Column("calculation_hash",sa.String(64),nullable=False,unique=True),sa.Column("status",sa.String(50),nullable=False),sa.Column("expires_at",sa.DateTime(timezone=True),nullable=False),sa.Column("created_at",sa.DateTime(timezone=True),nullable=False),sa.Column("updated_at",sa.DateTime(timezone=True),nullable=False))
    for name in ("organization_id","contract_id","status","expires_at"):op.create_index(f"ix_early_settlement_quotes_{name}","early_settlement_quotes",[name])
    op.create_table("finops_domain_events",
      sa.Column("id",sa.String(36),primary_key=True),sa.Column("organization_id",sa.String(36),sa.ForeignKey("organizations.id"),nullable=False),sa.Column("event_id",sa.String(120),nullable=False),sa.Column("event_type",sa.String(80),nullable=False),sa.Column("aggregate_id",sa.String(120),nullable=False),sa.Column("payload_json",sa.Text(),nullable=False),sa.Column("payload_hash",sa.String(64),nullable=False),sa.Column("signature_valid",sa.Boolean(),nullable=False),sa.Column("decision",sa.String(80),nullable=False),sa.Column("execution_mode",sa.String(30),nullable=False),sa.Column("received_at",sa.DateTime(timezone=True),nullable=False),sa.Column("created_at",sa.DateTime(timezone=True),nullable=False),sa.Column("updated_at",sa.DateTime(timezone=True),nullable=False),sa.UniqueConstraint("organization_id","event_id"))
    for name in ("organization_id","event_id","event_type","aggregate_id","decision"):op.create_index(f"ix_finops_domain_events_{name}","finops_domain_events",[name])

def downgrade():
    op.drop_table("finops_domain_events");op.drop_table("early_settlement_quotes")
