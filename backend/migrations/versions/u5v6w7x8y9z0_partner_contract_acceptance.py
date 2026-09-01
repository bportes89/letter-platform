"""Partner contract acceptance on network invite onboarding

Revision ID: u5v6w7x8y9z0
Revises: t4u5v6w7x8y9
"""
from alembic import op
import sqlalchemy as sa

revision = "u5v6w7x8y9z0"
down_revision = "t4u5v6w7x8y9"
branch_labels = None
depends_on = None


def upgrade():
    op.add_column(
        "user_invitations",
        sa.Column("partner_contract_required", sa.Boolean(), nullable=False, server_default=sa.false()),
    )
    op.create_table(
        "partner_contract_acceptances",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("organization_id", sa.String(36), sa.ForeignKey("organizations.id"), nullable=False),
        sa.Column("invitation_id", sa.String(36), sa.ForeignKey("user_invitations.id"), nullable=False),
        sa.Column("user_id", sa.String(36), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("template_slug", sa.String(80), nullable=False),
        sa.Column("template_version", sa.String(120), nullable=False),
        sa.Column("storage_key", sa.String(500), nullable=False),
        sa.Column("document_sha256", sa.String(64), nullable=False),
        sa.Column("evidence_json", sa.Text(), nullable=False),
        sa.Column("evidence_hash", sa.String(64), nullable=False),
        sa.Column("ip_address", sa.String(64), nullable=True),
        sa.Column("user_agent", sa.String(500), nullable=True),
        sa.Column("accepted_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.UniqueConstraint("user_id"),
    )
    op.create_index("ix_partner_contract_acceptances_organization_id", "partner_contract_acceptances", ["organization_id"])
    op.create_index("ix_partner_contract_acceptances_invitation_id", "partner_contract_acceptances", ["invitation_id"])
    op.create_index("ix_partner_contract_acceptances_user_id", "partner_contract_acceptances", ["user_id"])


def downgrade():
    op.drop_index("ix_partner_contract_acceptances_user_id", table_name="partner_contract_acceptances")
    op.drop_index("ix_partner_contract_acceptances_invitation_id", table_name="partner_contract_acceptances")
    op.drop_index("ix_partner_contract_acceptances_organization_id", table_name="partner_contract_acceptances")
    op.drop_table("partner_contract_acceptances")
    op.drop_column("user_invitations", "partner_contract_required")
