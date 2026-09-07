"""platform contract acceptances and master tree keys

Revision ID: z0a1b2c3d4e5
Revises: x8y9z0a1b2c3
"""
from alembic import op
import sqlalchemy as sa

revision = "z0a1b2c3d4e5"
down_revision = "x8y9z0a1b2c3"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "user_contract_acceptances",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("organization_id", sa.String(36), sa.ForeignKey("organizations.id"), nullable=False),
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
        sa.UniqueConstraint("user_id", "template_slug", name="uq_user_contract_acceptance"),
    )
    op.create_index("ix_user_contract_acceptances_user_id", "user_contract_acceptances", ["user_id"])
    op.create_index("ix_user_contract_acceptances_org_id", "user_contract_acceptances", ["organization_id"])

    op.add_column("users", sa.Column("master_tree_key", sa.String(40), nullable=True))
    op.create_index("ix_users_master_tree_key", "users", ["master_tree_key"])

    op.add_column("network_nodes", sa.Column("master_tree_key", sa.String(40), nullable=True))
    op.create_index("ix_network_nodes_master_tree_key", "network_nodes", ["master_tree_key"])


def downgrade():
    op.drop_index("ix_network_nodes_master_tree_key", table_name="network_nodes")
    op.drop_column("network_nodes", "master_tree_key")
    op.drop_index("ix_users_master_tree_key", table_name="users")
    op.drop_column("users", "master_tree_key")
    op.drop_index("ix_user_contract_acceptances_org_id", table_name="user_contract_acceptances")
    op.drop_index("ix_user_contract_acceptances_user_id", table_name="user_contract_acceptances")
    op.drop_table("user_contract_acceptances")
