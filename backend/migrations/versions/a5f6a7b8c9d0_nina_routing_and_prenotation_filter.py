"""nina routing and prenotation filter

Revision ID: a5f6a7b8c9d0
Revises: 94e5f6a7b8c9
"""
from alembic import op
import sqlalchemy as sa
revision="a5f6a7b8c9d0";down_revision="94e5f6a7b8c9";branch_labels=None;depends_on=None

def upgrade():
    op.create_table("nina_routing_policies",sa.Column("id",sa.String(36),primary_key=True),sa.Column("organization_id",sa.String(36),sa.ForeignKey("organizations.id"),nullable=False),sa.Column("version",sa.Integer(),nullable=False),sa.Column("population_threshold",sa.Integer(),nullable=False),sa.Column("income_per_capita_threshold",sa.Numeric(15,2),nullable=False),sa.Column("tapaf_amount",sa.Numeric(15,2),nullable=False),sa.Column("accepted_encumbrances_json",sa.Text(),nullable=False),sa.Column("rejected_encumbrances_json",sa.Text(),nullable=False),sa.Column("status",sa.String(30),nullable=False),sa.Column("approved_by_id",sa.String(36),sa.ForeignKey("users.id")),sa.Column("approved_at",sa.DateTime(timezone=True)),sa.Column("created_at",sa.DateTime(timezone=True),nullable=False),sa.Column("updated_at",sa.DateTime(timezone=True),nullable=False),sa.UniqueConstraint("organization_id","version"))
    op.create_index("ix_nina_routing_policies_organization_id","nina_routing_policies",["organization_id"]);op.create_index("ix_nina_routing_policies_status","nina_routing_policies",["status"])
    op.create_table("nina_routing_assessments",sa.Column("id",sa.String(36),primary_key=True),sa.Column("organization_id",sa.String(36),sa.ForeignKey("organizations.id"),nullable=False),sa.Column("proposal_id",sa.String(36),sa.ForeignKey("proposals.id"),nullable=False),sa.Column("policy_id",sa.String(36),sa.ForeignKey("nina_routing_policies.id"),nullable=False),sa.Column("version",sa.Integer(),nullable=False),sa.Column("asset_type",sa.String(30),nullable=False),sa.Column("municipality_code",sa.String(20),nullable=False),sa.Column("population",sa.Integer(),nullable=False),sa.Column("income_per_capita",sa.Numeric(15,2),nullable=False),sa.Column("encumbrances_json",sa.Text(),nullable=False),sa.Column("risk_flags_json",sa.Text(),nullable=False),sa.Column("tapaf_evidence_reference",sa.String(200)),sa.Column("physical_appraisal_required",sa.Boolean(),nullable=False),sa.Column("product_route",sa.String(50),nullable=False),sa.Column("capital_route",sa.String(30)),sa.Column("status",sa.String(50),nullable=False),sa.Column("blockers_json",sa.Text(),nullable=False),sa.Column("evidence_hash",sa.String(64),nullable=False,unique=True),sa.Column("approved_by_id",sa.String(36),sa.ForeignKey("users.id")),sa.Column("approved_at",sa.DateTime(timezone=True)),sa.Column("created_at",sa.DateTime(timezone=True),nullable=False),sa.Column("updated_at",sa.DateTime(timezone=True),nullable=False),sa.UniqueConstraint("proposal_id","version"))
    for n in ("organization_id","proposal_id","product_route","capital_route","status"):op.create_index(f"ix_nina_routing_assessments_{n}","nina_routing_assessments",[n])

def downgrade():
    op.drop_table("nina_routing_assessments");op.drop_table("nina_routing_policies")
