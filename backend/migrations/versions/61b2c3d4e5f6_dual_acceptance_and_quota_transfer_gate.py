"""dual acceptance and quota transfer gate

Revision ID: 61b2c3d4e5f6
Revises: 38afc1fa2212
"""
from alembic import op
import sqlalchemy as sa

revision='61b2c3d4e5f6'
down_revision='38afc1fa2212'
branch_labels=None
depends_on=None

def upgrade():
    op.create_table('acceptance_templates',
      sa.Column('id',sa.String(36),primary_key=True),sa.Column('organization_id',sa.String(36),sa.ForeignKey('organizations.id'),nullable=False),
      sa.Column('acceptance_type',sa.String(40),nullable=False),sa.Column('version',sa.Integer(),nullable=False),sa.Column('title',sa.String(200),nullable=False),
      sa.Column('body',sa.Text(),nullable=False),sa.Column('body_hash',sa.String(64),nullable=False),sa.Column('legal_review_status',sa.String(30),nullable=False),
      sa.Column('active',sa.Boolean(),nullable=False),sa.Column('created_by_id',sa.String(36),sa.ForeignKey('users.id'),nullable=False),
      sa.Column('approved_by_id',sa.String(36),sa.ForeignKey('users.id')),sa.Column('approved_at',sa.DateTime(timezone=True)),
      sa.Column('created_at',sa.DateTime(timezone=True),nullable=False),sa.Column('updated_at',sa.DateTime(timezone=True),nullable=False),
      sa.UniqueConstraint('organization_id','acceptance_type','version'))
    op.create_index('ix_acceptance_templates_organization_id','acceptance_templates',['organization_id']);op.create_index('ix_acceptance_templates_acceptance_type','acceptance_templates',['acceptance_type'])
    op.create_table('transaction_acceptances',
      sa.Column('id',sa.String(36),primary_key=True),sa.Column('organization_id',sa.String(36),sa.ForeignKey('organizations.id'),nullable=False),
      sa.Column('contract_id',sa.String(36),sa.ForeignKey('contracts.id'),nullable=False),sa.Column('template_id',sa.String(36),sa.ForeignKey('acceptance_templates.id'),nullable=False),
      sa.Column('acceptance_type',sa.String(40),nullable=False),sa.Column('accepted_by_id',sa.String(36),sa.ForeignKey('users.id'),nullable=False),
      sa.Column('accepted_at',sa.DateTime(timezone=True),nullable=False),sa.Column('evidence_json',sa.Text(),nullable=False),sa.Column('evidence_hash',sa.String(64),nullable=False),
      sa.Column('ip_address',sa.String(64)),sa.Column('user_agent',sa.String(500)),sa.Column('created_at',sa.DateTime(timezone=True),nullable=False),sa.Column('updated_at',sa.DateTime(timezone=True),nullable=False),
      sa.UniqueConstraint('contract_id','acceptance_type'))
    op.create_index('ix_transaction_acceptances_organization_id','transaction_acceptances',['organization_id']);op.create_index('ix_transaction_acceptances_contract_id','transaction_acceptances',['contract_id']);op.create_index('ix_transaction_acceptances_acceptance_type','transaction_acceptances',['acceptance_type'])
    op.create_table('quota_transfer_verifications',
      sa.Column('id',sa.String(36),primary_key=True),sa.Column('organization_id',sa.String(36),sa.ForeignKey('organizations.id'),nullable=False),
      sa.Column('contract_id',sa.String(36),sa.ForeignKey('contracts.id'),nullable=False,unique=True),sa.Column('quota_id',sa.String(36),sa.ForeignKey('quotas.id')),
      sa.Column('status',sa.String(40),nullable=False),sa.Column('administrator_reference',sa.String(200),nullable=False),sa.Column('transfer_reported_at',sa.DateTime(timezone=True)),
      sa.Column('audit_deadline_at',sa.DateTime(timezone=True)),sa.Column('confirmed_at',sa.DateTime(timezone=True)),sa.Column('disputed_at',sa.DateTime(timezone=True)),
      sa.Column('payout_unlocked',sa.Boolean(),nullable=False),sa.Column('evidence_json',sa.Text(),nullable=False),sa.Column('created_at',sa.DateTime(timezone=True),nullable=False),sa.Column('updated_at',sa.DateTime(timezone=True),nullable=False))
    op.create_index('ix_quota_transfer_verifications_organization_id','quota_transfer_verifications',['organization_id']);op.create_index('ix_quota_transfer_verifications_contract_id','quota_transfer_verifications',['contract_id']);op.create_index('ix_quota_transfer_verifications_quota_id','quota_transfer_verifications',['quota_id']);op.create_index('ix_quota_transfer_verifications_status','quota_transfer_verifications',['status']);op.create_index('ix_quota_transfer_verifications_audit_deadline_at','quota_transfer_verifications',['audit_deadline_at'])
    op.add_column('payout_requests',sa.Column('transfer_verification_id',sa.String(36)))
    op.create_index('ix_payout_requests_transfer_verification_id','payout_requests',['transfer_verification_id'])

def downgrade():
    op.drop_index('ix_payout_requests_transfer_verification_id',table_name='payout_requests');op.drop_column('payout_requests','transfer_verification_id')
    op.drop_table('quota_transfer_verifications');op.drop_table('transaction_acceptances');op.drop_table('acceptance_templates')
