"""SDC commercial solicitations desk.

Revision ID: i9d0e1f2g3h4
Revises: h8c9d0e1f2g3
Create Date: 2026-09-10
"""

from alembic import op
import sqlalchemy as sa

revision = "i9d0e1f2g3h4"
down_revision = "h8c9d0e1f2g3"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "sdc_solicitations",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("organization_id", sa.String(36), sa.ForeignKey("organizations.id"), nullable=False, index=True),
        sa.Column("partner_user_id", sa.String(36), sa.ForeignKey("users.id"), nullable=True, index=True),
        sa.Column("created_by_id", sa.String(36), sa.ForeignKey("users.id"), nullable=True),
        sa.Column("status", sa.String(40), nullable=False, server_default="AWAITING_DOCS", index=True),
        sa.Column("status_notes", sa.Text(), nullable=True),
        sa.Column("contact_name", sa.String(180), nullable=False),
        sa.Column("contact_email", sa.String(180), nullable=False, index=True),
        sa.Column("contact_phone", sa.String(40), nullable=False, server_default=""),
        sa.Column("document", sa.String(20), nullable=True),
        sa.Column("person_type", sa.String(10), nullable=False, server_default="PF"),
        sa.Column("address", sa.Text(), nullable=True),
        sa.Column("occupation", sa.String(180), nullable=True),
        sa.Column("income_value", sa.Numeric(15, 2), nullable=False, server_default="0"),
        sa.Column("asset_type", sa.String(40), nullable=False, index=True),
        sa.Column("asset_value", sa.Numeric(15, 2), nullable=False),
        sa.Column("asset_year", sa.Integer(), nullable=True),
        sa.Column("asset_paid_off", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("asset_has_lien", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("docs_complete", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("credit_estimated", sa.Numeric(15, 2), nullable=False, server_default="0"),
        sa.Column("installment_estimated", sa.Numeric(15, 2), nullable=False, server_default="0"),
        sa.Column("term_months", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("interest_rate_monthly", sa.Numeric(8, 4), nullable=False, server_default="0"),
        sa.Column("evaluation_json", sa.Text(), nullable=False, server_default="{}"),
        sa.Column("proposal_id", sa.String(36), sa.ForeignKey("proposals.id"), nullable=True, index=True),
        sa.Column("quota_id", sa.String(36), sa.ForeignKey("quotas.id"), nullable=True, index=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_table(
        "sdc_solicitation_documents",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("organization_id", sa.String(36), sa.ForeignKey("organizations.id"), nullable=False, index=True),
        sa.Column("solicitation_id", sa.String(36), sa.ForeignKey("sdc_solicitations.id"), nullable=False, index=True),
        sa.Column("document_id", sa.String(36), sa.ForeignKey("documents.id"), nullable=False, index=True),
        sa.Column("doc_type", sa.String(80), nullable=False, server_default="SDC_SUPPORT"),
        sa.Column("comment", sa.Text(), nullable=True),
        sa.Column("uploaded_by_id", sa.String(36), sa.ForeignKey("users.id"), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
    )


def downgrade() -> None:
    op.drop_table("sdc_solicitation_documents")
    op.drop_table("sdc_solicitations")
