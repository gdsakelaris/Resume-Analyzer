"""
External Job Posting model for tracking job postings to external platforms.

Tracks the lifecycle of job postings to LinkedIn, Indeed, ZipRecruiter, etc.
"""

import enum
import uuid
from sqlalchemy import Column, String, Integer, DateTime, Enum, ForeignKey, Index, func
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship
from app.core.database import Base
from app.models.oauth_connection import OAuthProvider


class PostingStatus(str, enum.Enum):
    """
    Lifecycle status of an external job posting.

    - PENDING: Queued for posting but not yet started
    - POSTING: Currently being posted to external platform
    - ACTIVE: Successfully posted and live on external platform
    - FAILED: Posting failed (permanent or after all retries)
    - CLOSED: Job closed on external platform (manual action)
    - EXPIRED: Posting expired on external platform
    """
    PENDING = "pending"
    POSTING = "posting"
    ACTIVE = "active"
    FAILED = "failed"
    CLOSED = "closed"
    EXPIRED = "expired"


class ExternalJobPosting(Base):
    """
    Tracks job postings to external job boards (LinkedIn, Indeed, etc.).

    Provides:
    - Status tracking (pending → posting → active/failed)
    - Error logging for failed postings
    - Retry counter for automatic retries
    - External job ID and URL for reference
    - Graceful degradation (job creation succeeds even if posting fails)

    Relationships:
    - Belongs to a Job (CASCADE delete when job is deleted)
    - Scoped by tenant_id for multi-tenancy
    """
    __tablename__ = "external_job_postings"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4, index=True)
    job_id = Column(Integer, ForeignKey("jobs.id", ondelete="CASCADE"), nullable=False, index=True)
    tenant_id = Column(UUID(as_uuid=True), ForeignKey("users.tenant_id"), nullable=False, index=True)

    # Platform details
    provider = Column(Enum(OAuthProvider, values_callable=lambda x: [e.value for e in x]), nullable=False, index=True)
    external_job_id = Column(String, nullable=True)  # LinkedIn's job ID
    external_url = Column(String, nullable=True)  # Link to job on LinkedIn

    # Status tracking
    status = Column(Enum(PostingStatus, values_callable=lambda x: [e.value for e in x]), default=PostingStatus.PENDING, nullable=False, index=True)
    error_message = Column(String, nullable=True)  # Error details if status=FAILED
    retry_count = Column(Integer, default=0, nullable=False)  # Number of retry attempts

    # Timestamps
    posted_at = Column(DateTime(timezone=True), nullable=True)  # When successfully posted
    closed_at = Column(DateTime(timezone=True), nullable=True)  # When closed on platform
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())

    # Relationships
    job = relationship("Job", back_populates="external_postings")

    # Indexes
    __table_args__ = (
        Index('ix_external_postings_job_provider', 'job_id', 'provider'),
        Index('ix_external_postings_status', 'status'),
    )

    def __repr__(self):
        return f"<ExternalJobPosting(job_id={self.job_id}, provider={self.provider.value}, status={self.status.value})>"
