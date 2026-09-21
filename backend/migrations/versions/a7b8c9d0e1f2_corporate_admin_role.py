"""Restore PLATFORM_ADMIN on corporate login e-mail.

Revision ID: a7b8c9d0e1f2
Revises: z6a7b8c9d0e1
Create Date: 2026-09-21
"""

from alembic import op

revision = "a7b8c9d0e1f2"
down_revision = "z6a7b8c9d0e1"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute(
        """
        UPDATE users
        SET role = 'PLATFORM_ADMIN', master_tree_key = NULL
        WHERE lower(email) = 'comercial@letter.app.br'
          AND role = 'MASTER_FRANCHISEE'
        """
    )


def downgrade() -> None:
    pass
