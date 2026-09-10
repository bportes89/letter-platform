"""QuitCon commercial solicitations desk.

Revision ID: k1f2g3h4i5j6
Revises: j0e1f2g3h4i5
Create Date: 2026-09-10
"""

from alembic import op
import sqlalchemy as sa

revision = "k1f2g3h4i5j6"
down_revision = "j0e1f2g3h4i5"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "quitcon_solicitations",
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
        sa.Column("outstanding_balance", sa.Numeric(15, 2), nullable=False),
        sa.Column("meses_restantes", sa.Integer(), nullable=False, server_default="48"),
        sa.Column("registry_number", sa.String(80), nullable=False),
        sa.Column("registry_office", sa.String(180), nullable=False),
        sa.Column("property_type", sa.String(40), nullable=False, server_default="CONSORCIO"),
        sa.Column("appraisal_value", sa.Numeric(15, 2), nullable=False, server_default="0"),
        sa.Column("operational_service", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("contemplada", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("bem_faturado", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("parcelas_em_dia", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("docs_complete", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("quitacao_vp_amount", sa.Numeric(15, 2), nullable=False, server_default="0"),
        sa.Column("evaluation_json", sa.Text(), nullable=False, server_default="{}"),
        sa.Column("proposal_id", sa.String(36), sa.ForeignKey("proposals.id"), nullable=True, index=True),
        sa.Column("quitcon_operacao_id", sa.String(36), sa.ForeignKey("operacoes_quitcon.id"), nullable=True, index=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_table(
        "quitcon_solicitation_documents",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("organization_id", sa.String(36), sa.ForeignKey("organizations.id"), nullable=False, index=True),
        sa.Column("solicitation_id", sa.String(36), sa.ForeignKey("quitcon_solicitations.id"), nullable=False, index=True),
        sa.Column("document_id", sa.String(36), sa.ForeignKey("documents.id"), nullable=False, index=True),
        sa.Column("doc_type", sa.String(80), nullable=False, server_default="QUITCON_SUPPORT"),
        sa.Column("comment", sa.Text(), nullable=True),
        sa.Column("uploaded_by_id", sa.String(36), sa.ForeignKey("users.id"), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
    )


def downgrade() -> None:
    op.drop_table("quitcon_solicitation_documents")
    op.drop_table("quitcon_solicitations")
