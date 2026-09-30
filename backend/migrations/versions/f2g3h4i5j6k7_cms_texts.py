"""CMS texts (legacy texts + z_text editor).

Revision ID: f2g3h4i5j6k7
Revises: e1f2a3b4c5d6
Create Date: 2026-09-30
"""

from alembic import op
import sqlalchemy as sa

revision = "f2g3h4i5j6k7"
down_revision = "e1f2a3b4c5d6"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "cms_texts",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("organization_id", sa.String(length=36), nullable=False),
        sa.Column("legacy_id", sa.Integer(), nullable=True),
        sa.Column("active", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("kind", sa.String(length=20), nullable=False, server_default="PAGE"),
        sa.Column("name_main", sa.String(length=255), nullable=False),
        sa.Column("subject", sa.Text(), nullable=True),
        sa.Column("slug", sa.String(length=80), nullable=True),
        sa.Column("body_html", sa.Text(), nullable=False, server_default=""),
        sa.Column("whatsapp", sa.Text(), nullable=True),
        sa.Column("sms", sa.Text(), nullable=True),
        sa.Column("footer_place", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("sort_order", sa.Integer(), nullable=False, server_default="999"),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["organization_id"], ["organizations.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("organization_id", "legacy_id", name="uq_cms_text_org_legacy"),
        sa.UniqueConstraint("organization_id", "slug", name="uq_cms_text_org_slug"),
    )
    op.create_index("ix_cms_texts_organization_id", "cms_texts", ["organization_id"])
    op.create_index("ix_cms_texts_kind", "cms_texts", ["kind"])


def downgrade() -> None:
    op.drop_index("ix_cms_texts_kind", table_name="cms_texts")
    op.drop_index("ix_cms_texts_organization_id", table_name="cms_texts")
    op.drop_table("cms_texts")
