"""merge_migration_heads

Revision ID: f501dbe6b31e
Revises: 112b54f286c6, b2c3d4e5f6a7
Create Date: 2026-01-02 21:46:49.510795

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'f501dbe6b31e'
down_revision: Union[str, Sequence[str], None] = ('112b54f286c6', 'b2c3d4e5f6a7')
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    pass


def downgrade() -> None:
    """Downgrade schema."""
    pass
