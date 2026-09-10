"""Flash Capital commercial solicitations desk.

Revision ID: j0e1f2g3h4i5
Revises: i9d0e1f2g3h4
Create Date: 2026-09-10
"""

from alembic import op
import sqlalchemy as sa

revision = "j0e1f2g3h4i5"
down_revision = "i9d0e1f2g3h4"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "flash_solicitations",
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
        sa.Column("asset_category", sa.String(20), nullable=False, server_default="REAL_ESTATE", index=True),
        sa.Column("asset_value", sa.Numeric(15, 2), nullable=False),
        sa.Column("asset_year", sa.Integer(), nullable=True),
        sa.Column("asset_paid_off", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("asset_has_lien", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("docs_complete", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("capital_source", sa.String(20), nullable=False, server_default="RETAIL"),
        sa.Column("term_months", sa.Integer(), nullable=False, server_default="36"),
        sa.Column("principal", sa.Numeric(15, 2), nullable=False, server_default="0"),
        sa.Column("ltv_percent", sa.Numeric(8, 4), nullable=False, server_default="0"),
        sa.Column("platform_fee", sa.Numeric(15, 2), nullable=False, server_default="0"),
        sa.Column("itbi_provision", sa.Numeric(15, 2), nullable=False, server_default="0"),
        sa.Column("net_payout", sa.Numeric(15, 2), nullable=False, server_default="0"),
        sa.Column("installment_estimated", sa.Numeric(15, 2), nullable=False, server_default="0"),
        sa.Column("interest_rate_monthly", sa.Numeric(8, 4), nullable=False, server_default="0"),
        sa.Column("evaluation_json", sa.Text(), nullable=False, server_default="{}"),
        sa.Column("parties_json", sa.Text(), nullable=False, server_default="{}"),
        sa.Column("proposal_id", sa.String(36), sa.ForeignKey("proposals.id"), nullable=True, index=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_table(
        "flash_solicitation_documents",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("organization_id", sa.String(36), sa.ForeignKey("organizations.id"), nullable=False, index=True),
        sa.Column("solicitation_id", sa.String(36), sa.ForeignKey("flash_solicitations.id"), nullable=False, index=True),
        sa.Column("document_id", sa.String(36), sa.ForeignKey("documents.id"), nullable=False, index=True),
        sa.Column("doc_type", sa.String(80), nullable=False, server_default="FLASH_SUPPORT"),
        sa.Column("comment", sa.Text(), nullable=True),
        sa.Column("uploaded_by_id", sa.String(36), sa.ForeignKey("users.id"), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
    )


def downgrade() -> None:
    op.drop_table("flash_solicitation_documents")
    op.drop_table("flash_solicitations")
