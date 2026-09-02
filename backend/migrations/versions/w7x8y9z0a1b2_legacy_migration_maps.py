"""Legacy migration id map and run audit tables

Revision ID: w7x8y9z0a1b2
Revises: v6w7x8y9z0a1
"""
from alembic import op
import sqlalchemy as sa

revision = "w7x8y9z0a1b2"
down_revision = "v6w7x8y9z0a1"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "legacy_migration_runs",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("organization_id", sa.String(36), sa.ForeignKey("organizations.id"), nullable=False, index=True),
        sa.Column("legacy_source", sa.String(80), nullable=False, index=True),
        sa.Column("mode", sa.String(20), nullable=False),
        sa.Column("status", sa.String(30), nullable=False, index=True),
        sa.Column("summary_json", sa.Text(), nullable=False, server_default="{}"),
        sa.Column("error_message", sa.String(500)),
        sa.Column("started_by_id", sa.String(36), sa.ForeignKey("users.id")),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("finished_at", sa.DateTime(timezone=True)),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_table(
        "legacy_id_maps",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("organization_id", sa.String(36), sa.ForeignKey("organizations.id"), nullable=False, index=True),
        sa.Column("migration_run_id", sa.String(36), sa.ForeignKey("legacy_migration_runs.id"), index=True),
        sa.Column("legacy_source", sa.String(80), nullable=False, index=True),
        sa.Column("entity_type", sa.String(60), nullable=False, index=True),
        sa.Column("legacy_id", sa.String(120), nullable=False),
        sa.Column("new_id", sa.String(36), nullable=False, index=True),
        sa.Column("payload_json", sa.Text()),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.UniqueConstraint(
            "organization_id",
            "legacy_source",
            "entity_type",
            "legacy_id",
            name="uq_legacy_id_map_source_entity",
        ),
    )


def downgrade():
    op.drop_table("legacy_id_maps")
    op.drop_table("legacy_migration_runs")
