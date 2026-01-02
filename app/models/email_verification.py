"""
Email verification model for 6-digit verification codes.

Each verification code is single-use, time-limited (15 minutes),
and rate-limited to prevent brute force attacks.
"""

import uuid
from datetime import datetime
from sqlalchemy import Column, String, Boolean, DateTime, Integer, ForeignKey, Index
from sqlalchemy.dialects.postgresql import UUID
from app.core.database import Base


class EmailVerification(Base):
    """
    Email verification codes for user account verification.

    Features:
    - 6-digit numeric codes
    - 15-minute expiration
    - Single-use enforcement
    - Attempt tracking for brute force protection
    - Cascade delete with user
    """
    __tablename__ = "email_verifications"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4, index=True)
    user_id = Column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)

    # 6-digit verification code
    code = Column(String(6), nullable=False)

    # Expiration timestamp (15 minutes from creation)
    expires_at = Column(DateTime(timezone=True), nullable=False)

    # Creation timestamp
    created_at = Column(DateTime(timezone=True), nullable=False, default=datetime.utcnow)

    # Security features
    attempts = Column(Integer, nullable=False, default=0)  # Track verification attempts
    is_used = Column(Boolean, nullable=False, default=False)  # Single-use enforcement

    # Composite index for efficient code lookups
    __table_args__ = (
        Index('ix_email_verifications_code_expires', 'code', 'expires_at'),
        Index('ix_email_verifications_created_at', 'created_at'),
    )

    def __repr__(self):
        return f"<EmailVerification(user_id={self.user_id}, code={self.code}, expires_at={self.expires_at})>"
