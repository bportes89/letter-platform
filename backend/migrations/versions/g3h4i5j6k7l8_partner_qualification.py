"""Partner qualification tiers and SDC appraisal (legacy affiliates_qualification).

Revision ID: g3h4i5j6k7l8
Revises: f2g3h4i5j6k7
Create Date: 2026-09-30
"""

from alembic import op
import sqlalchemy as sa

revision = "g3h4i5j6k7l8"
down_revision = "f2g3h4i5j6k7"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "partner_qualification_tiers",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("organization_id", sa.String(length=36), nullable=False),
        sa.Column("legacy_id", sa.Integer(), nullable=True),
        sa.Column("active", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("name", sa.String(length=255), nullable=False),
        sa.Column("price_init", sa.Numeric(15, 2), nullable=False, server_default="0"),
        sa.Column("price_final", sa.Numeric(15, 2), nullable=False, server_default="0"),
        sa.Column("price_bonus", sa.Numeric(8, 2), nullable=False, server_default="0"),
        sa.Column("sort_order", sa.Integer(), nullable=False, server_default="999"),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["organization_id"], ["organizations.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("organization_id", "legacy_id", name="uq_partner_qual_tier_org_legacy"),
    )
    op.create_index("ix_partner_qualification_tiers_organization_id", "partner_qualification_tiers", ["organization_id"])

    op.create_table(
        "partner_qualification_appraisal_runs",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("organization_id", sa.String(length=36), nullable=False),
        sa.Column("date_init", sa.Date(), nullable=False),
        sa.Column("date_final", sa.Date(), nullable=False),
        sa.Column("applied_by_id", sa.String(length=36), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["applied_by_id"], ["users.id"]),
        sa.ForeignKeyConstraint(["organization_id"], ["organizations.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "ix_partner_qualification_appraisal_runs_organization_id",
        "partner_qualification_appraisal_runs",
        ["organization_id"],
    )

    op.add_column("users", sa.Column("partner_qualification_tier_id", sa.String(length=36), nullable=True))
    op.add_column(
        "users",
        sa.Column("partner_qualification_appraisal_amount", sa.Numeric(15, 2), nullable=False, server_default="0"),
    )
    op.add_column("users", sa.Column("partner_qualification_appraisal_tier_id", sa.String(length=36), nullable=True))
    op.add_column("users", sa.Column("partner_qualification_appraisal_tier_name", sa.String(length=255), nullable=True))
    op.create_foreign_key(
        "fk_users_partner_qualification_tier",
        "users",
        "partner_qualification_tiers",
        ["partner_qualification_tier_id"],
        ["id"],
    )
    op.create_foreign_key(
        "fk_users_partner_qualification_appraisal_tier",
        "users",
        "partner_qualification_tiers",
        ["partner_qualification_appraisal_tier_id"],
        ["id"],
    )
    op.create_index("ix_users_partner_qualification_tier_id", "users", ["partner_qualification_tier_id"])
    op.create_index("ix_users_partner_qualification_appraisal_tier_id", "users", ["partner_qualification_appraisal_tier_id"])


def downgrade() -> None:
    op.drop_index("ix_users_partner_qualification_appraisal_tier_id", table_name="users")
    op.drop_index("ix_users_partner_qualification_tier_id", table_name="users")
    op.drop_constraint("fk_users_partner_qualification_appraisal_tier", "users", type_="foreignkey")
    op.drop_constraint("fk_users_partner_qualification_tier", "users", type_="foreignkey")
    op.drop_column("users", "partner_qualification_appraisal_tier_name")
    op.drop_column("users", "partner_qualification_appraisal_tier_id")
    op.drop_column("users", "partner_qualification_appraisal_amount")
    op.drop_column("users", "partner_qualification_tier_id")
    op.drop_index("ix_partner_qualification_appraisal_runs_organization_id", table_name="partner_qualification_appraisal_runs")
    op.drop_table("partner_qualification_appraisal_runs")
    op.drop_index("ix_partner_qualification_tiers_organization_id", table_name="partner_qualification_tiers")
    op.drop_table("partner_qualification_tiers")
