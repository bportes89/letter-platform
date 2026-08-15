"""payment receipts finops invoice automation v3

Revision ID: b6c7d8e9f0a1
Revises: a5f6a7b8c9d0
"""
from alembic import op
import sqlalchemy as sa

revision = "b6c7d8e9f0a1"
down_revision = "a5f6a7b8c9d0"
branch_labels = None
depends_on = None


def upgrade():
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    if "payment_receipts" in inspector.get_table_names():
        return
    op.create_table(
        "payment_receipts",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("organization_id", sa.String(36), sa.ForeignKey("organizations.id"), nullable=False),
        sa.Column("invoice_id", sa.String(36), sa.ForeignKey("invoices.id"), nullable=False),
        sa.Column("contract_id", sa.String(36), sa.ForeignKey("contracts.id"), nullable=False),
        sa.Column("payment_event_id", sa.String(36), sa.ForeignKey("payment_events.id")),
        sa.Column("partner_id", sa.String(80), nullable=False),
        sa.Column("reference_month", sa.Integer(), nullable=False),
        sa.Column("filename", sa.String(120), nullable=False),
        sa.Column("total_paid", sa.Numeric(15, 2), nullable=False),
        sa.Column("fruicao_amount", sa.Numeric(15, 2), nullable=False),
        sa.Column("amortizacao_amount", sa.Numeric(15, 2), nullable=False),
        sa.Column("tax_withheld", sa.Numeric(15, 2), nullable=False),
        sa.Column("authenticity_hash", sa.String(64), nullable=False),
        sa.Column("customer_route", sa.String(500), nullable=False),
        sa.Column("vault_s3_uri", sa.String(500), nullable=False),
        sa.Column("document_id", sa.String(36), sa.ForeignKey("documents.id")),
        sa.Column("payload_json", sa.Text(), nullable=False),
        sa.Column("email_status", sa.String(30), nullable=False, server_default="SENT_D+0"),
        sa.Column("push_status", sa.String(30), nullable=False, server_default="ACTIVE"),
        sa.Column("issued_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.UniqueConstraint("invoice_id", "payment_event_id"),
    )
    for name in ("organization_id", "contract_id", "invoice_id", "authenticity_hash", "issued_at"):
        op.create_index(f"ix_payment_receipts_{name}", "payment_receipts", [name])


def downgrade():
    op.drop_table("payment_receipts")
