"""Add LinkedIn integration tables

Revision ID: 9a1b2c3d4e5f
Revises: 4410ace826e3
Create Date: 2026-01-05 10:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = '9a1b2c3d4e5f'
down_revision: Union[str, Sequence[str], None] = '4410ace826e3'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema - Add oauth_connections and external_job_postings tables."""
    conn = op.get_bind()
    inspector = sa.inspect(conn)

    # Create OAuthProvider ENUM
    oauthprovider_enum = postgresql.ENUM(
        'linkedin', 'indeed', 'ziprecruiter',
        name='oauthprovider',
        create_type=True
    )

    # Create PostingStatus ENUM
    postingstatus_enum = postgresql.ENUM(
        'pending', 'posting', 'active', 'failed', 'closed', 'expired',
        name='postingstatus',
        create_type=True
    )

    # Check if ENUMs exist before creating
    result = conn.execute(sa.text(
        "SELECT 1 FROM pg_type WHERE typname = 'oauthprovider'"
    )).fetchone()
    if not result:
        oauthprovider_enum.create(conn)

    result = conn.execute(sa.text(
        "SELECT 1 FROM pg_type WHERE typname = 'postingstatus'"
    )).fetchone()
    if not result:
        postingstatus_enum.create(conn)

    # Create oauth_connections table if it doesn't exist
    if 'oauth_connections' not in inspector.get_table_names():
        op.create_table('oauth_connections',
            sa.Column('id', postgresql.UUID(as_uuid=True), nullable=False),
            sa.Column('user_id', postgresql.UUID(as_uuid=True), nullable=False),
            sa.Column('tenant_id', postgresql.UUID(as_uuid=True), nullable=False),
            sa.Column('provider', postgresql.ENUM('linkedin', 'indeed', 'ziprecruiter', name='oauthprovider', create_type=False), nullable=False),
            sa.Column('access_token', sa.String(), nullable=False),
            sa.Column('refresh_token', sa.String(), nullable=True),
            sa.Column('token_expires_at', sa.DateTime(timezone=True), nullable=True),
            sa.Column('provider_data', postgresql.JSONB(astext_type=sa.Text()), nullable=True),
            sa.Column('is_active', sa.Boolean(), nullable=False, server_default=sa.text('true')),
            sa.Column('last_refresh_at', sa.DateTime(timezone=True), nullable=True),
            sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=True),
            sa.Column('updated_at', sa.DateTime(timezone=True), nullable=True),
            sa.ForeignKeyConstraint(['tenant_id'], ['users.tenant_id'], ),
            sa.ForeignKeyConstraint(['user_id'], ['users.id'], ondelete='CASCADE'),
            sa.PrimaryKeyConstraint('id')
        )
        op.create_index(op.f('ix_oauth_connections_id'), 'oauth_connections', ['id'], unique=False)
        op.create_index(op.f('ix_oauth_connections_user_id'), 'oauth_connections', ['user_id'], unique=False)
        op.create_index(op.f('ix_oauth_connections_tenant_id'), 'oauth_connections', ['tenant_id'], unique=False)
        op.create_index(op.f('ix_oauth_connections_provider'), 'oauth_connections', ['provider'], unique=False)
        op.create_index(op.f('ix_oauth_connections_is_active'), 'oauth_connections', ['is_active'], unique=False)
        op.create_index('ix_oauth_user_provider', 'oauth_connections', ['user_id', 'provider'], unique=True)

    # Create external_job_postings table if it doesn't exist
    if 'external_job_postings' not in inspector.get_table_names():
        op.create_table('external_job_postings',
            sa.Column('id', postgresql.UUID(as_uuid=True), nullable=False),
            sa.Column('job_id', sa.Integer(), nullable=False),
            sa.Column('tenant_id', postgresql.UUID(as_uuid=True), nullable=False),
            sa.Column('provider', postgresql.ENUM('linkedin', 'indeed', 'ziprecruiter', name='oauthprovider', create_type=False), nullable=False),
            sa.Column('external_job_id', sa.String(), nullable=True),
            sa.Column('external_url', sa.String(), nullable=True),
            sa.Column('status', postgresql.ENUM('pending', 'posting', 'active', 'failed', 'closed', 'expired', name='postingstatus', create_type=False), nullable=False, server_default=sa.text("'pending'")),
            sa.Column('error_message', sa.String(), nullable=True),
            sa.Column('retry_count', sa.Integer(), nullable=False, server_default=sa.text('0')),
            sa.Column('posted_at', sa.DateTime(timezone=True), nullable=True),
            sa.Column('closed_at', sa.DateTime(timezone=True), nullable=True),
            sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=True),
            sa.Column('updated_at', sa.DateTime(timezone=True), nullable=True),
            sa.ForeignKeyConstraint(['job_id'], ['jobs.id'], ondelete='CASCADE'),
            sa.ForeignKeyConstraint(['tenant_id'], ['users.tenant_id'], ),
            sa.PrimaryKeyConstraint('id')
        )
        op.create_index(op.f('ix_external_job_postings_id'), 'external_job_postings', ['id'], unique=False)
        op.create_index(op.f('ix_external_job_postings_job_id'), 'external_job_postings', ['job_id'], unique=False)
        op.create_index(op.f('ix_external_job_postings_tenant_id'), 'external_job_postings', ['tenant_id'], unique=False)
        op.create_index(op.f('ix_external_job_postings_provider'), 'external_job_postings', ['provider'], unique=False)
        op.create_index('ix_external_postings_job_provider', 'external_job_postings', ['job_id', 'provider'], unique=False)
        op.create_index('ix_external_postings_status', 'external_job_postings', ['status'], unique=False)


def downgrade() -> None:
    """Downgrade schema - Remove oauth_connections and external_job_postings tables."""
    # Drop indexes
    op.drop_index('ix_external_postings_status', table_name='external_job_postings')
    op.drop_index('ix_external_postings_job_provider', table_name='external_job_postings')
    op.drop_index(op.f('ix_external_job_postings_provider'), table_name='external_job_postings')
    op.drop_index(op.f('ix_external_job_postings_tenant_id'), table_name='external_job_postings')
    op.drop_index(op.f('ix_external_job_postings_job_id'), table_name='external_job_postings')
    op.drop_index(op.f('ix_external_job_postings_id'), table_name='external_job_postings')

    op.drop_index('ix_oauth_user_provider', table_name='oauth_connections')
    op.drop_index(op.f('ix_oauth_connections_is_active'), table_name='oauth_connections')
    op.drop_index(op.f('ix_oauth_connections_provider'), table_name='oauth_connections')
    op.drop_index(op.f('ix_oauth_connections_tenant_id'), table_name='oauth_connections')
    op.drop_index(op.f('ix_oauth_connections_user_id'), table_name='oauth_connections')
    op.drop_index(op.f('ix_oauth_connections_id'), table_name='oauth_connections')

    # Drop tables
    op.drop_table('external_job_postings')
    op.drop_table('oauth_connections')

    # Drop ENUMs
    conn = op.get_bind()
    conn.execute(sa.text("DROP TYPE IF EXISTS postingstatus"))
    conn.execute(sa.text("DROP TYPE IF EXISTS oauthprovider"))
