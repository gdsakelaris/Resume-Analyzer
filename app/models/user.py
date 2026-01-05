"""
User model for authentication and multi-tenancy.

Each User represents an authenticated account with a unique tenant_id.
All resources (jobs, candidates, evaluations) are scoped to the tenant_id.
"""

import uuid
from sqlalchemy import Column, String, Boolean, DateTime, func
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship
from app.core.database import Base


class User(Base):
    """
    User account for SaaS multi-tenancy.

    Each user has a unique tenant_id that isolates their data.
    Multiple users can share the same tenant_id for team access (future feature).
    """
    __tablename__ = "users"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4, index=True)

    # tenant_id is the isolation boundary for all resources
    # All queries must filter by tenant_id to prevent cross-tenant data access
    tenant_id = Column(UUID(as_uuid=True), nullable=False, default=uuid.uuid4, index=True)

    # Authentication credentials
    email = Column(String, unique=True, nullable=False, index=True)
    hashed_password = Column(String, nullable=False)

    # User profile
    full_name = Column(String, nullable=True)
    company_name = Column(String, nullable=True)

    # Account status
    is_active = Column(Boolean, default=True, nullable=False)
    is_verified = Column(Boolean, default=False, nullable=False)  # Email verification
    is_admin = Column(Boolean, default=False, nullable=False)  # Admin role for protected endpoints

    # Timestamps
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())
    last_login_at = Column(DateTime(timezone=True), nullable=True)

    # Relationships
    subscription = relationship("Subscription", back_populates="user", uselist=False, cascade="all, delete-orphan")
    oauth_connections = relationship("OAuthConnection", back_populates="user", foreign_keys="[OAuthConnection.user_id]", cascade="all, delete-orphan")

    def __repr__(self):
        return f"<User(id={self.id}, email='{self.email}', tenant_id={self.tenant_id})>"
