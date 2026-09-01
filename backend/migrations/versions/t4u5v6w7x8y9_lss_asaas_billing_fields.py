"""LSS Asaas billing fields on saas_subscriptions

Revision ID: t4u5v6w7x8y9
Revises: s3t4u5v6w7x8
"""
from alembic import op
import sqlalchemy as sa

revision = "t4u5v6w7x8y9"
down_revision = "s3t4u5v6w7x8"
branch_labels = None
depends_on = None


def upgrade():
    op.add_column("saas_subscriptions", sa.Column("asaas_customer_id", sa.String(80), nullable=True))
    op.add_column("saas_subscriptions", sa.Column("asaas_subscription_id", sa.String(80), nullable=True))
    op.add_column("saas_subscriptions", sa.Column("billing_type", sa.String(30), nullable=True))
    op.add_column("saas_subscriptions", sa.Column("subscriber_email", sa.String(255), nullable=True))
    op.add_column("saas_subscriptions", sa.Column("last_payment_id", sa.String(80), nullable=True))
    op.add_column("saas_subscriptions", sa.Column("last_payment_status", sa.String(40), nullable=True))
    op.add_column("saas_subscriptions", sa.Column("payment_checkout_url", sa.String(500), nullable=True))
    op.create_index("ix_saas_subscriptions_asaas_subscription_id", "saas_subscriptions", ["asaas_subscription_id"])


def downgrade():
    op.drop_index("ix_saas_subscriptions_asaas_subscription_id", table_name="saas_subscriptions")
    op.drop_column("saas_subscriptions", "payment_checkout_url")
    op.drop_column("saas_subscriptions", "last_payment_status")
    op.drop_column("saas_subscriptions", "last_payment_id")
    op.drop_column("saas_subscriptions", "subscriber_email")
    op.drop_column("saas_subscriptions", "billing_type")
    op.drop_column("saas_subscriptions", "asaas_subscription_id")
    op.drop_column("saas_subscriptions", "asaas_customer_id")
