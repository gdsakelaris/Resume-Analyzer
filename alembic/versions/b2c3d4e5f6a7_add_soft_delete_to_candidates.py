"""Add soft delete to candidates

Revision ID: b2c3d4e5f6a7
Revises: a1b2c3d4e5f6
Create Date: 2026-01-02 14:00:00.000000

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = 'b2c3d4e5f6a7'
down_revision = 'a1b2c3d4e5f6'
branch_labels = None
depends_on = None


def upgrade():
    # Add soft delete columns to candidates table
    op.add_column('candidates', sa.Column('is_deleted', sa.Boolean(), nullable=False, server_default='false'))
    op.add_column('candidates', sa.Column('deleted_at', sa.DateTime(timezone=True), nullable=True))
    op.add_column('candidates', sa.Column('deleted_by_user_id', sa.Integer(), nullable=True))
    op.add_column('candidates', sa.Column('retention_until', sa.DateTime(timezone=True), nullable=True))

    # Create indexes for efficient querying
    op.create_index(op.f('ix_candidates_is_deleted'), 'candidates', ['is_deleted'], unique=False)

    # Add foreign key for deleted_by_user_id
    op.create_foreign_key(
        'candidates_deleted_by_user_id_fkey',
        'candidates',
        'users',
        ['deleted_by_user_id'],
        ['id']
    )


def downgrade():
    # Drop foreign key
    op.drop_constraint('candidates_deleted_by_user_id_fkey', 'candidates', type_='foreignkey')

    # Drop index
    op.drop_index(op.f('ix_candidates_is_deleted'), table_name='candidates')

    # Drop columns
    op.drop_column('candidates', 'retention_until')
    op.drop_column('candidates', 'deleted_by_user_id')
    op.drop_column('candidates', 'deleted_at')
    op.drop_column('candidates', 'is_deleted')
