"""add_password_reset_fields_to_users

Revision ID: 977bf5cb92d4
Revises: 9a1b2c3d4e5f
Create Date: 2026-01-05 18:42:29.562473

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '977bf5cb92d4'
down_revision: Union[str, Sequence[str], None] = '9a1b2c3d4e5f'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Add password reset fields to users table."""
    # Add reset_token and reset_token_expires_at columns
    op.add_column('users', sa.Column('reset_token', sa.String(), nullable=True))
    op.add_column('users', sa.Column('reset_token_expires_at', sa.DateTime(timezone=True), nullable=True))

    # Create index on reset_token for faster lookups
    op.create_index('ix_users_reset_token', 'users', ['reset_token'])


def downgrade() -> None:
    """Remove password reset fields from users table."""
    # Drop index first
    op.drop_index('ix_users_reset_token', 'users')

    # Drop columns
    op.drop_column('users', 'reset_token_expires_at')
    op.drop_column('users', 'reset_token')
