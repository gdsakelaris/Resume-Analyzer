"""rename_starter_to_recruiter

Revision ID: 8558001a8837
Revises: 0bed6d5936ea
Create Date: 2026-01-03 03:02:48.586731

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '8558001a8837'
down_revision: Union[str, Sequence[str], None] = '0bed6d5936ea'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Rename 'starter' enum value to 'recruiter' in subscriptionplan enum."""
    # PostgreSQL doesn't support renaming enum values directly
    # We need to add the new value, update the data, and remove the old value

    # Step 1: Add 'recruiter' to the enum
    op.execute("ALTER TYPE subscriptionplan ADD VALUE 'recruiter'")

    # Step 2: Update all existing 'starter' subscriptions to 'recruiter'
    op.execute("UPDATE subscriptions SET plan = 'recruiter' WHERE plan = 'starter'")

    # Note: We cannot remove 'starter' from the enum in PostgreSQL without recreating it
    # This would require dropping and recreating the enum, which is risky
    # Instead, we leave 'starter' in the enum but it will no longer be used


def downgrade() -> None:
    """Revert 'recruiter' back to 'starter'."""
    # Revert the data back to 'starter'
    op.execute("UPDATE subscriptions SET plan = 'starter' WHERE plan = 'recruiter'")
