"""add_small_business_plan

Revision ID: 7c0d41691735
Revises: 8157046e0b70
Create Date: 2026-01-01 02:44:04.164581

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '7c0d41691735'
down_revision: Union[str, Sequence[str], None] = '8157046e0b70'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """
    Add SMALL_BUSINESS to the subscriptionplan enum.

    This adds a new tier between STARTER and PROFESSIONAL
    for small businesses ($199/mo, 100 candidates).
    """
    # Add the new enum value to the subscriptionplan type
    op.execute("ALTER TYPE subscriptionplan ADD VALUE IF NOT EXISTS 'small_business'")


def downgrade() -> None:
    """
    Note: PostgreSQL does not support removing enum values.

    To fully downgrade, you would need to:
    1. Update all 'small_business' subscriptions to 'professional'
    2. Recreate the enum type without 'small_business'

    For simplicity, we'll just update the subscriptions.
    """
    # Update any small_business subscriptions to professional
    op.execute(
        """
        UPDATE subscriptions
        SET plan = 'professional'
        WHERE plan = 'small_business'
        """
    )
