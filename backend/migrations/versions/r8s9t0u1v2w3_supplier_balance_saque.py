"""Supplier balance, ledger and withdrawals.

Revision ID: r8s9t0u1v2w3
Revises: q7r8s9t0u1v2
Create Date: 2026-09-10
"""

from alembic import op
import sqlalchemy as sa

revision = "r8s9t0u1v2w3"
down_revision = "q7r8s9t0u1v2"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "quota_suppliers",
        sa.Column("balance_available", sa.Numeric(15, 2), nullable=False, server_default="0"),
    )
    op.create_table(
        "supplier_ledger_entries",
        sa.Column("id", sa.String(length=36), primary_key=True),
        sa.Column("organization_id", sa.String(length=36), sa.ForeignKey("organizations.id"), nullable=False, index=True),
        sa.Column("supplier_id", sa.String(length=36), sa.ForeignKey("quota_suppliers.id"), nullable=False, index=True),
        sa.Column("kind", sa.String(length=20), nullable=False, index=True),
        sa.Column("amount", sa.Numeric(15, 2), nullable=False),
        sa.Column("reference", sa.String(length=120), nullable=False, index=True),
        sa.Column("proposal_id", sa.String(length=36), sa.ForeignKey("proposals.id"), nullable=True, index=True),
        sa.Column("description", sa.String(length=255), nullable=False, server_default=""),
        sa.Column("meta_json", sa.Text(), nullable=False, server_default="{}"),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.UniqueConstraint("supplier_id", "reference", "kind", name="uq_supplier_ledger_ref_kind"),
    )
    op.create_table(
        "supplier_withdrawals",
        sa.Column("id", sa.String(length=36), primary_key=True),
        sa.Column("organization_id", sa.String(length=36), sa.ForeignKey("organizations.id"), nullable=False, index=True),
        sa.Column("supplier_id", sa.String(length=36), sa.ForeignKey("quota_suppliers.id"), nullable=False, index=True),
        sa.Column("amount", sa.Numeric(15, 2), nullable=False),
        sa.Column("status", sa.String(length=20), nullable=False, server_default="PENDING", index=True),
        sa.Column("pix_key", sa.String(length=180), nullable=False),
        sa.Column("notes", sa.Text(), nullable=True),
        sa.Column("ledger_entry_id", sa.String(length=36), sa.ForeignKey("supplier_ledger_entries.id"), nullable=True),
        sa.Column("processed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("processed_by_user_id", sa.String(length=36), sa.ForeignKey("users.id"), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
    )


def downgrade() -> None:
    op.drop_table("supplier_withdrawals")
    op.drop_table("supplier_ledger_entries")
    op.drop_column("quota_suppliers", "balance_available")
