"""Sale commission attribution on proposals and client leads

Revision ID: x8y9z0a1b2c3
Revises: w7x8y9z0a1b2
"""
from alembic import op
import sqlalchemy as sa

revision = "x8y9z0a1b2c3"
down_revision = "w7x8y9z0a1b2"
branch_labels = None
depends_on = None


def upgrade():
    op.add_column("leads", sa.Column("client_user_id", sa.String(36), nullable=True))
    op.create_index("ix_leads_client_user_id", "leads", ["client_user_id"])
    op.create_foreign_key(
        "fk_leads_client_user_id",
        "leads",
        "users",
        ["client_user_id"],
        ["id"],
    )

    op.add_column("proposals", sa.Column("client_user_id", sa.String(36), nullable=True))
    op.add_column("proposals", sa.Column("sale_channel", sa.String(30), nullable=False, server_default="PARTNER_OFFICE"))
    op.add_column("proposals", sa.Column("served_by_user_id", sa.String(36), nullable=True))
    op.add_column("proposals", sa.Column("commission_originator_id", sa.String(36), nullable=True))
    op.add_column("proposals", sa.Column("created_by_user_id", sa.String(36), nullable=True))

    op.create_index("ix_proposals_client_user_id", "proposals", ["client_user_id"])
    op.create_index("ix_proposals_commission_originator_id", "proposals", ["commission_originator_id"])
    op.create_foreign_key("fk_proposals_client_user_id", "proposals", "users", ["client_user_id"], ["id"])
    op.create_foreign_key("fk_proposals_served_by_user_id", "proposals", "users", ["served_by_user_id"], ["id"])
    op.create_foreign_key("fk_proposals_commission_originator_id", "proposals", "users", ["commission_originator_id"], ["id"])
    op.create_foreign_key("fk_proposals_created_by_user_id", "proposals", "users", ["created_by_user_id"], ["id"])


def downgrade():
    op.drop_constraint("fk_proposals_created_by_user_id", "proposals", type_="foreignkey")
    op.drop_constraint("fk_proposals_commission_originator_id", "proposals", type_="foreignkey")
    op.drop_constraint("fk_proposals_served_by_user_id", "proposals", type_="foreignkey")
    op.drop_constraint("fk_proposals_client_user_id", "proposals", type_="foreignkey")
    op.drop_index("ix_proposals_commission_originator_id", table_name="proposals")
    op.drop_index("ix_proposals_client_user_id", table_name="proposals")
    op.drop_column("proposals", "created_by_user_id")
    op.drop_column("proposals", "commission_originator_id")
    op.drop_column("proposals", "served_by_user_id")
    op.drop_column("proposals", "sale_channel")
    op.drop_column("proposals", "client_user_id")

    op.drop_constraint("fk_leads_client_user_id", "leads", type_="foreignkey")
    op.drop_index("ix_leads_client_user_id", table_name="leads")
    op.drop_column("leads", "client_user_id")
