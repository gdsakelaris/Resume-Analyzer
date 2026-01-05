"""
OAuth Connection model for external integrations.

Stores OAuth tokens for job board integrations (LinkedIn, Indeed, etc.).
Tokens are encrypted at rest for security.
"""

import enum
import uuid
from sqlalchemy import Column, String, Boolean, DateTime, Enum, ForeignKey, Index, func
from sqlalchemy.dialects.postgresql import UUID, JSONB
from sqlalchemy.orm import relationship
from app.core.database import Base


class OAuthProvider(str, enum.Enum):
    """
    Supported OAuth providers for job board integrations.

    - LINKEDIN: LinkedIn Job Posting API
    - INDEED: Indeed job posting (future)
    - ZIPRECRUITER: ZipRecruiter job posting (future)
    """
    LINKEDIN = "linkedin"
    INDEED = "indeed"
    ZIPRECRUITER = "ziprecruiter"


class OAuthConnection(Base):
    """
    OAuth connection for external job board integrations.

    Stores encrypted OAuth tokens and provider-specific metadata.
    Supports multi-tenancy with tenant_id scoping.

    Security features:
    - Tokens encrypted at rest (via encryption module)
    - State parameter for CSRF protection (stored in Redis)
    - Token expiry tracking for automatic refresh
    """
    __tablename__ = "oauth_connections"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4, index=True)
    user_id = Column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    tenant_id = Column(UUID(as_uuid=True), ForeignKey("users.tenant_id"), nullable=False, index=True)

    # Provider information
    provider = Column(Enum(OAuthProvider, values_callable=lambda x: [e.value for e in x]), nullable=False, index=True)

    # OAuth tokens (stored encrypted)
    access_token = Column(String, nullable=False)  # Encrypted
    refresh_token = Column(String, nullable=True)  # Encrypted
    token_expires_at = Column(DateTime(timezone=True), nullable=True)

    # Provider-specific metadata (e.g., LinkedIn organization URN)
    provider_data = Column(JSONB, nullable=True, default=dict)

    # Status tracking
    is_active = Column(Boolean, default=True, nullable=False, index=True)
    last_refresh_at = Column(DateTime(timezone=True), nullable=True)

    # Timestamps
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())

    # Relationships
    user = relationship("User", back_populates="oauth_connections")

    # Indexes and constraints
    __table_args__ = (
        # Unique constraint: one active connection per user per provider
        Index('ix_oauth_user_provider', 'user_id', 'provider', unique=True),
    )

    def __repr__(self):
        return f"<OAuthConnection(user_id={self.user_id}, provider={self.provider.value}, is_active={self.is_active})>"
