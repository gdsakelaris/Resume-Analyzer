"""Add cascade delete for evaluations

Revision ID: a1b2c3d4e5f6
Revises: f93f4b3e658f
Create Date: 2026-01-02 12:00:00.000000

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = 'a1b2c3d4e5f6'
down_revision = 'f93f4b3e658f'
branch_labels = None
depends_on = None


def upgrade():
    # Drop the existing foreign key constraint
    op.drop_constraint('evaluations_candidate_id_fkey', 'evaluations', type_='foreignkey')

    # Recreate it with CASCADE delete
    op.create_foreign_key(
        'evaluations_candidate_id_fkey',
        'evaluations',
        'candidates',
        ['candidate_id'],
        ['id'],
        ondelete='CASCADE'
    )


def downgrade():
    # Drop the CASCADE constraint
    op.drop_constraint('evaluations_candidate_id_fkey', 'evaluations', type_='foreignkey')

    # Recreate without CASCADE
    op.create_foreign_key(
        'evaluations_candidate_id_fkey',
        'evaluations',
        'candidates',
        ['candidate_id'],
        ['id']
    )
