"""Platform admin login e-mail corporativo.

Revision ID: z6a7b8c9d0e1
Revises: y5z6a7b8c9d0
Create Date: 2026-09-21
"""

from alembic import op

revision = "z6a7b8c9d0e1"
down_revision = "y5z6a7b8c9d0"
branch_labels = None
depends_on = None

TARGET = "comercial@letter.app.br"
LEGACY = "admin@letter.com.br"


def upgrade() -> None:
    op.execute(
        f"""
        UPDATE users AS u
        SET email = 'relocated-' || substr(u.id, 1, 8) || '@letter.com.br'
        WHERE lower(u.email) = '{TARGET}'
          AND u.role <> 'PLATFORM_ADMIN'
          AND EXISTS (
            SELECT 1 FROM users a
            WHERE lower(a.email) = '{LEGACY}' AND a.role = 'PLATFORM_ADMIN'
          )
        """
    )
    op.execute(
        f"""
        UPDATE users
        SET email = '{TARGET}'
        WHERE lower(email) = '{LEGACY}'
          AND role = 'PLATFORM_ADMIN'
          AND NOT EXISTS (
            SELECT 1 FROM users o WHERE lower(o.email) = '{TARGET}'
          )
        """
    )


def downgrade() -> None:
    op.execute(
        f"""
        UPDATE users
        SET email = '{LEGACY}'
        WHERE lower(email) = '{TARGET}'
          AND role = 'PLATFORM_ADMIN'
          AND NOT EXISTS (
            SELECT 1 FROM users o WHERE lower(o.email) = '{LEGACY}'
          )
        """
    )
