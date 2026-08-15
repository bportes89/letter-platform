"""seller evidence and structured properties

Revision ID: 72c3d4e5f6a7
Revises: 61b2c3d4e5f6
"""
from alembic import op
import sqlalchemy as sa

revision='72c3d4e5f6a7';down_revision='61b2c3d4e5f6';branch_labels=None;depends_on=None

def upgrade():
    op.create_table('seller_evidence_audits',
      sa.Column('id',sa.String(36),primary_key=True),sa.Column('organization_id',sa.String(36),sa.ForeignKey('organizations.id'),nullable=False),sa.Column('contract_id',sa.String(36),sa.ForeignKey('contracts.id'),nullable=False),
      sa.Column('status',sa.String(40),nullable=False),sa.Column('buyer_document_masked',sa.String(30),nullable=False),sa.Column('seller_document_masked',sa.String(30),nullable=False),
      sa.Column('statement_document_id',sa.String(36),sa.ForeignKey('documents.id'),nullable=False),sa.Column('protocol_document_id',sa.String(36),sa.ForeignKey('documents.id'),nullable=False),sa.Column('assignment_document_id',sa.String(36),sa.ForeignKey('documents.id'),nullable=False),
      sa.Column('statement_contemplated',sa.Boolean(),nullable=False),sa.Column('administrator_protocol',sa.String(100)),sa.Column('parties_matched',sa.Boolean(),nullable=False),sa.Column('signature_evidence_detected',sa.Boolean(),nullable=False),
      sa.Column('manual_review_status',sa.String(30),nullable=False),sa.Column('rejection_reason',sa.String(1000)),sa.Column('evidence_hash',sa.String(64),nullable=False),sa.Column('reviewed_by_id',sa.String(36),sa.ForeignKey('users.id')),sa.Column('reviewed_at',sa.DateTime(timezone=True)),
      sa.Column('created_at',sa.DateTime(timezone=True),nullable=False),sa.Column('updated_at',sa.DateTime(timezone=True),nullable=False),sa.UniqueConstraint('contract_id'))
    op.create_index('ix_seller_evidence_audits_organization_id','seller_evidence_audits',['organization_id']);op.create_index('ix_seller_evidence_audits_contract_id','seller_evidence_audits',['contract_id']);op.create_index('ix_seller_evidence_audits_status','seller_evidence_audits',['status'])
    op.create_table('structured_property_cases',
      sa.Column('id',sa.String(36),primary_key=True),sa.Column('organization_id',sa.String(36),sa.ForeignKey('organizations.id'),nullable=False),sa.Column('operation_id',sa.String(36),sa.ForeignKey('operations.id')),
      sa.Column('case_reference',sa.String(60),nullable=False),sa.Column('buyer_document_masked',sa.String(30),nullable=False),sa.Column('seller_document_masked',sa.String(30),nullable=False),sa.Column('has_lien_debt',sa.Boolean(),nullable=False),sa.Column('unregistered_construction',sa.Boolean(),nullable=False),sa.Column('route',sa.String(40),nullable=False),
      sa.Column('land_appraisal_value',sa.Numeric(15,2),nullable=False),sa.Column('future_appraisal_value',sa.Numeric(15,2),nullable=False),sa.Column('gross_payout',sa.Numeric(15,2),nullable=False),sa.Column('estimated_debt',sa.Numeric(15,2),nullable=False),sa.Column('phase1_amount',sa.Numeric(15,2),nullable=False),sa.Column('phase2_amount',sa.Numeric(15,2),nullable=False),
      sa.Column('iq_status',sa.String(40),nullable=False),sa.Column('phase_status',sa.String(40),nullable=False),sa.Column('iq_document_id',sa.String(36),sa.ForeignKey('documents.id')),sa.Column('registered_property_document_id',sa.String(36),sa.ForeignKey('documents.id')),sa.Column('registration_deadline_at',sa.DateTime(timezone=True)),sa.Column('legal_hold',sa.Boolean(),nullable=False),sa.Column('evidence_hash',sa.String(64),nullable=False),
      sa.Column('created_at',sa.DateTime(timezone=True),nullable=False),sa.Column('updated_at',sa.DateTime(timezone=True),nullable=False),sa.UniqueConstraint('operation_id'),sa.UniqueConstraint('case_reference'))
    for name,cols,unique in [('organization_id',['organization_id'],False),('operation_id',['operation_id'],True),('case_reference',['case_reference'],True),('route',['route'],False),('iq_status',['iq_status'],False),('phase_status',['phase_status'],False),('registration_deadline_at',['registration_deadline_at'],False)]:op.create_index(f'ix_structured_property_cases_{name}','structured_property_cases',cols,unique=unique)
    op.create_table('structured_property_events',
      sa.Column('id',sa.String(36),primary_key=True),sa.Column('organization_id',sa.String(36),sa.ForeignKey('organizations.id'),nullable=False),sa.Column('case_id',sa.String(36),sa.ForeignKey('structured_property_cases.id'),nullable=False),sa.Column('event_key',sa.String(120),nullable=False),sa.Column('event_type',sa.String(60),nullable=False),sa.Column('status',sa.String(30),nullable=False),sa.Column('payload_json',sa.Text(),nullable=False),sa.Column('evidence_hash',sa.String(64),nullable=False),sa.Column('actor_id',sa.String(36),sa.ForeignKey('users.id')),sa.Column('occurred_at',sa.DateTime(timezone=True),nullable=False),sa.UniqueConstraint('case_id','event_key'),sa.UniqueConstraint('evidence_hash'))
    for name in ('organization_id','case_id','event_key','event_type','status','evidence_hash','occurred_at'):op.create_index(f'ix_structured_property_events_{name}','structured_property_events',[name],unique=name=='evidence_hash')

def downgrade():
    op.drop_table('structured_property_events');op.drop_table('structured_property_cases');op.drop_table('seller_evidence_audits')
