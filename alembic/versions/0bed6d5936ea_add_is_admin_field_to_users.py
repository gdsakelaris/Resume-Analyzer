"""add_is_admin_field_to_users

Revision ID: 0bed6d5936ea
Revises: f501dbe6b31e
Create Date: 2026-01-02 21:46:54.978178

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '0bed6d5936ea'
down_revision: Union[str, Sequence[str], None] = 'f501dbe6b31e'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    # Add is_admin column to users table
    op.add_column('users', sa.Column('is_admin', sa.Boolean(), nullable=False, server_default=sa.false()))


def downgrade() -> None:
    """Downgrade schema."""
    # Remove is_admin column from users table
    op.drop_column('users', 'is_admin')
