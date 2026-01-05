"""
CRUD operations for OAuth connections.

Handles LinkedIn, Indeed, and other job board OAuth integrations.
"""

from typing import Optional
from uuid import UUID
from datetime import datetime, timedelta
from sqlalchemy.orm import Session
from app.models.oauth_connection import OAuthConnection, OAuthProvider


def create_or_update_connection(
    db: Session,
    user_id: UUID,
    tenant_id: UUID,
    provider: str,
    access_token: str,
    refresh_token: Optional[str] = None,
    expires_in: Optional[int] = None,
    provider_data: Optional[dict] = None
) -> OAuthConnection:
    """
    Create new OAuth connection or update existing one.

    Args:
        db: Database session
        user_id: User UUID
        tenant_id: Tenant UUID (for multi-tenancy)
        provider: OAuth provider name (e.g., "linkedin", "indeed")
        access_token: OAuth access token (will be encrypted before storage)
        refresh_token: OAuth refresh token (optional, will be encrypted)
        expires_in: Token expiry in seconds (from OAuth provider)
        provider_data: Provider-specific metadata (e.g., LinkedIn organization URN)

    Returns:
        OAuthConnection: Created or updated connection
    """
    # Check for existing connection
    existing = db.query(OAuthConnection).filter(
        OAuthConnection.user_id == user_id,
        OAuthConnection.provider == provider
    ).first()

    if existing:
        # Update existing connection
        # TODO: Encrypt tokens before storing (will be added in encryption module)
        existing.access_token = access_token
        existing.refresh_token = refresh_token
        existing.is_active = True
        existing.last_refresh_at = datetime.utcnow()

        if expires_in:
            existing.token_expires_at = datetime.utcnow() + timedelta(seconds=expires_in)

        if provider_data:
            existing.provider_data = provider_data

        db.commit()
        db.refresh(existing)
        return existing

    # Create new connection
    token_expires_at = None
    if expires_in:
        token_expires_at = datetime.utcnow() + timedelta(seconds=expires_in)

    # TODO: Encrypt tokens before storing (will be added in encryption module)
    connection = OAuthConnection(
        user_id=user_id,
        tenant_id=tenant_id,
        provider=provider,
        access_token=access_token,
        refresh_token=refresh_token,
        token_expires_at=token_expires_at,
        provider_data=provider_data or {},
        is_active=True
    )

    db.add(connection)
    db.commit()
    db.refresh(connection)
    return connection


def get_connection(db: Session, user_id: UUID, provider: str) -> Optional[OAuthConnection]:
    """
    Get OAuth connection for user and provider.

    Args:
        db: Database session
        user_id: User UUID
        provider: OAuth provider name (e.g., "linkedin")

    Returns:
        OAuthConnection or None if not found or inactive
    """
    return db.query(OAuthConnection).filter(
        OAuthConnection.user_id == user_id,
        OAuthConnection.provider == provider,
        OAuthConnection.is_active == True
    ).first()


def get_connection_by_tenant(db: Session, tenant_id: UUID, provider: str) -> Optional[OAuthConnection]:
    """
    Get OAuth connection by tenant ID.

    This is useful for multi-user teams where multiple users share a tenant.
    Currently returns the first active connection found.

    Args:
        db: Database session
        tenant_id: Tenant UUID
        provider: OAuth provider name (e.g., "linkedin")

    Returns:
        OAuthConnection or None if not found or inactive
    """
    return db.query(OAuthConnection).filter(
        OAuthConnection.tenant_id == tenant_id,
        OAuthConnection.provider == provider,
        OAuthConnection.is_active == True
    ).first()


def delete_connection(db: Session, user_id: UUID, provider: str) -> bool:
    """
    Soft-delete OAuth connection (marks as inactive).

    Args:
        db: Database session
        user_id: User UUID
        provider: OAuth provider name (e.g., "linkedin")

    Returns:
        bool: True if connection was found and deleted, False otherwise
    """
    connection = get_connection(db, user_id, provider)
    if not connection:
        return False

    connection.is_active = False
    db.commit()
    return True


def update_token(
    db: Session,
    connection_id: UUID,
    access_token: str,
    refresh_token: Optional[str] = None,
    expires_in: Optional[int] = None
) -> Optional[OAuthConnection]:
    """
    Update OAuth tokens (used after token refresh).

    Args:
        db: Database session
        connection_id: Connection UUID
        access_token: New access token
        refresh_token: New refresh token (optional)
        expires_in: Token expiry in seconds

    Returns:
        Updated OAuthConnection or None if not found
    """
    connection = db.query(OAuthConnection).filter(
        OAuthConnection.id == connection_id
    ).first()

    if not connection:
        return None

    # TODO: Encrypt tokens before storing (will be added in encryption module)
    connection.access_token = access_token
    if refresh_token:
        connection.refresh_token = refresh_token

    if expires_in:
        connection.token_expires_at = datetime.utcnow() + timedelta(seconds=expires_in)

    connection.last_refresh_at = datetime.utcnow()

    db.commit()
    db.refresh(connection)
    return connection
