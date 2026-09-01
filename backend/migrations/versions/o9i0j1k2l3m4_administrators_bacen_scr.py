"""administrator homologation fields and lead scr consultation

Revision ID: o9i0j1k2l3m4
Revises: n8h9i0j1k2l3
"""
from alembic import op
import sqlalchemy as sa

revision = "o9i0j1k2l3m4"
down_revision = "n8h9i0j1k2l3"
branch_labels = None
depends_on = None


def upgrade():
    op.add_column("administrators", sa.Column("code", sa.String(40), nullable=True))
    op.add_column("administrators", sa.Column("homologated_at", sa.DateTime(timezone=True), nullable=True))
    op.add_column("administrators", sa.Column("homologated_by_id", sa.String(36), nullable=True))
    op.add_column("administrators", sa.Column("bacen_rules_version", sa.Integer(), nullable=False, server_default="1"))
    op.add_column("administrators", sa.Column("homologation_notes", sa.Text(), nullable=True))
    op.create_index("ix_administrators_code", "administrators", ["code"], unique=True)
    op.create_foreign_key(
        "fk_administrators_homologated_by_id",
        "administrators",
        "users",
        ["homologated_by_id"],
        ["id"],
    )

    op.add_column("leads", sa.Column("scr_status", sa.String(40), nullable=True))
    op.add_column("leads", sa.Column("scr_reference", sa.String(80), nullable=True))
    op.add_column("leads", sa.Column("scr_consulted_at", sa.DateTime(timezone=True), nullable=True))
    op.add_column("leads", sa.Column("scr_detail_json", sa.Text(), nullable=False, server_default="{}"))


def downgrade():
    op.drop_column("leads", "scr_detail_json")
    op.drop_column("leads", "scr_consulted_at")
    op.drop_column("leads", "scr_reference")
    op.drop_column("leads", "scr_status")
    op.drop_constraint("fk_administrators_homologated_by_id", "administrators", type_="foreignkey")
    op.drop_index("ix_administrators_code", table_name="administrators")
    op.drop_column("administrators", "homologation_notes")
    op.drop_column("administrators", "bacen_rules_version")
    op.drop_column("administrators", "homologated_by_id")
    op.drop_column("administrators", "homologated_at")
    op.drop_column("administrators", "code")
