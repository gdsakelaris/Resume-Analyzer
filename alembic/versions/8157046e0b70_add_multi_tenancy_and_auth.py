"""add_multi_tenancy_and_auth

Adds User, Subscription tables and tenant_id to all resource tables.

This migration implements:
1. User authentication (email/password)
2. Subscription billing (Stripe integration)
3. Multi-tenancy isolation (tenant_id on all resources)

BREAKING CHANGE: Existing data will be assigned a default tenant_id.

Revision ID: 8157046e0b70
Revises: d895320e817f
Create Date: 2026-01-01 01:01:53.144579

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql
import uuid


# revision identifiers, used by Alembic.
revision: str = '8157046e0b70'
down_revision: Union[str, Sequence[str], None] = 'd895320e817f'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema to add multi-tenancy and authentication."""

    # 1. Create users table (indexes auto-created by SQLAlchemy from Column definitions)
    op.create_table(
        'users',
        sa.Column('id', postgresql.UUID(as_uuid=True), primary_key=True, nullable=False, index=True),
        sa.Column('tenant_id', postgresql.UUID(as_uuid=True), nullable=False, unique=True, index=True),
        sa.Column('email', sa.String(), nullable=False, unique=True, index=True),
        sa.Column('hashed_password', sa.String(), nullable=False),
        sa.Column('full_name', sa.String(), nullable=True),
        sa.Column('company_name', sa.String(), nullable=True),
        sa.Column('is_active', sa.Boolean(), nullable=False, server_default='true'),
        sa.Column('is_verified', sa.Boolean(), nullable=False, server_default='false'),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), onupdate=sa.func.now()),
        sa.Column('last_login_at', sa.DateTime(timezone=True), nullable=True),
    )

    # 2. Create subscriptions table (indexes auto-created by SQLAlchemy from Column definitions)
    op.create_table(
        'subscriptions',
        sa.Column('id', postgresql.UUID(as_uuid=True), primary_key=True, nullable=False),
        sa.Column('user_id', postgresql.UUID(as_uuid=True), nullable=False, unique=True, index=True),
        sa.Column('stripe_customer_id', sa.String(), nullable=True, unique=True, index=True),
        sa.Column('stripe_subscription_id', sa.String(), nullable=True, unique=True, index=True),
        sa.Column('plan', sa.Enum('free', 'starter', 'professional', 'enterprise', name='subscriptionplan'), nullable=False, server_default='free'),
        sa.Column('status', sa.Enum('trialing', 'active', 'past_due', 'canceled', 'unpaid', name='subscriptionstatus'), nullable=False, server_default='trialing', index=True),
        sa.Column('monthly_candidate_limit', sa.Integer(), nullable=False, server_default='5'),
        sa.Column('candidates_used_this_month', sa.Integer(), nullable=False, server_default='0'),
        sa.Column('current_period_start', sa.DateTime(timezone=True), nullable=True),
        sa.Column('current_period_end', sa.DateTime(timezone=True), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), onupdate=sa.func.now()),
        sa.ForeignKeyConstraint(['user_id'], ['users.id'], ondelete='CASCADE'),
    )

    # 3. Add tenant_id to jobs table
    # First add as nullable to allow migration
    op.add_column('jobs', sa.Column('tenant_id', postgresql.UUID(as_uuid=True), nullable=True))

    # Create a default tenant for existing data (pre-launch, so this is safe)
    default_tenant_id = uuid.uuid4()
    default_user_id = uuid.uuid4()

    # Insert a dummy user for existing jobs
    op.execute(f"""
        INSERT INTO users (id, tenant_id, email, hashed_password, is_active, is_verified)
        VALUES ('{default_user_id}', '{default_tenant_id}', 'legacy@starscreen.internal', 'legacy_hash', true, false)
    """)

    # Update existing jobs with the default tenant_id
    op.execute(f"UPDATE jobs SET tenant_id = '{default_tenant_id}' WHERE tenant_id IS NULL")

    # Make tenant_id non-nullable and add foreign key
    op.alter_column('jobs', 'tenant_id', nullable=False)
    op.create_index('ix_jobs_tenant_id', 'jobs', ['tenant_id'])
    op.create_foreign_key('fk_jobs_tenant_id', 'jobs', 'users', ['tenant_id'], ['tenant_id'], ondelete='CASCADE')

    # 4. Add tenant_id to candidates table
    op.add_column('candidates', sa.Column('tenant_id', postgresql.UUID(as_uuid=True), nullable=True))
    op.execute(f"UPDATE candidates SET tenant_id = '{default_tenant_id}' WHERE tenant_id IS NULL")
    op.alter_column('candidates', 'tenant_id', nullable=False)
    op.create_index('ix_candidates_tenant_id', 'candidates', ['tenant_id'])
    op.create_foreign_key('fk_candidates_tenant_id', 'candidates', 'users', ['tenant_id'], ['tenant_id'], ondelete='CASCADE')

    # 5. Add tenant_id to evaluations table
    op.add_column('evaluations', sa.Column('tenant_id', postgresql.UUID(as_uuid=True), nullable=True))
    op.execute(f"UPDATE evaluations SET tenant_id = '{default_tenant_id}' WHERE tenant_id IS NULL")
    op.alter_column('evaluations', 'tenant_id', nullable=False)
    op.create_index('ix_evaluations_tenant_id', 'evaluations', ['tenant_id'])
    op.create_foreign_key('fk_evaluations_tenant_id', 'evaluations', 'users', ['tenant_id'], ['tenant_id'], ondelete='CASCADE')


def downgrade() -> None:
    """Downgrade schema to remove multi-tenancy."""

    # Remove foreign keys and tenant_id columns (reverse order)
    op.drop_constraint('fk_evaluations_tenant_id', 'evaluations', type_='foreignkey')
    op.drop_index('ix_evaluations_tenant_id', 'evaluations')
    op.drop_column('evaluations', 'tenant_id')

    op.drop_constraint('fk_candidates_tenant_id', 'candidates', type_='foreignkey')
    op.drop_index('ix_candidates_tenant_id', 'candidates')
    op.drop_column('candidates', 'tenant_id')

    op.drop_constraint('fk_jobs_tenant_id', 'jobs', type_='foreignkey')
    op.drop_index('ix_jobs_tenant_id', 'jobs')
    op.drop_column('jobs', 'tenant_id')

    # Drop subscriptions table (will cascade delete all subscription records)
    op.drop_table('subscriptions')

    # Drop users table (will cascade delete all user records)
    op.drop_table('users')

    # Drop enums
    op.execute('DROP TYPE IF EXISTS subscriptionstatus')
    op.execute('DROP TYPE IF EXISTS subscriptionplan')
