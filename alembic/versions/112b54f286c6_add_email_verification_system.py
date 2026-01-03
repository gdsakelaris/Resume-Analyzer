"""add_email_verification_system

Revision ID: 112b54f286c6
Revises: 7c0d41691735
Create Date: 2026-01-02 12:00:42.180210

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '112b54f286c6'
down_revision: Union[str, Sequence[str], None] = '7c0d41691735'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """
    Add email_verifications table for 6-digit verification codes.
    Mark existing users as verified.
    """
    # Check if table exists before creating
    conn = op.get_bind()
    inspector = sa.inspect(conn)

    if 'email_verifications' not in inspector.get_table_names():
        # Create email_verifications table
        op.create_table(
            'email_verifications',
            sa.Column('id', sa.UUID(), nullable=False),
            sa.Column('user_id', sa.UUID(), nullable=False),
            sa.Column('code', sa.String(length=6), nullable=False),
            sa.Column('expires_at', sa.DateTime(timezone=True), nullable=False),
            sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
            sa.Column('attempts', sa.Integer(), server_default='0', nullable=False),
            sa.Column('is_used', sa.Boolean(), server_default='false', nullable=False),
            sa.PrimaryKeyConstraint('id'),
            sa.ForeignKeyConstraint(['user_id'], ['users.id'], ondelete='CASCADE'),
        )

        # Create indexes for performance
        op.create_index('ix_email_verifications_user_id', 'email_verifications', ['user_id'])
        op.create_index('ix_email_verifications_code_expires', 'email_verifications', ['code', 'expires_at'])
        op.create_index('ix_email_verifications_created_at', 'email_verifications', ['created_at'])

    # Mark all existing users as verified (migration safety)
    op.execute("UPDATE users SET is_verified = TRUE WHERE is_verified = FALSE")


def downgrade() -> None:
    """
    Remove email_verifications table.
    """
    op.drop_index('ix_email_verifications_created_at', table_name='email_verifications')
    op.drop_index('ix_email_verifications_code_expires', table_name='email_verifications')
    op.drop_index('ix_email_verifications_user_id', table_name='email_verifications')
    op.drop_table('email_verifications')
