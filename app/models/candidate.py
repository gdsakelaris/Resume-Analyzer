"""
Candidate database model.

Represents a job candidate who has submitted a resume for a specific job posting.
Tracks the resume processing pipeline from upload through parsing to scoring.
"""

from sqlalchemy import Column, Integer, String, ForeignKey, Enum, Text, DateTime, Boolean, func
from sqlalchemy.orm import relationship
from sqlalchemy.dialects.postgresql import JSONB, UUID
import enum
from app.core.database import Base


class CandidateStatus(str, enum.Enum):
    """
    Candidate processing status lifecycle:

    UPLOADED -> PROCESSING -> PARSED -> SCORED
                     ↓
                  FAILED
    """
    UPLOADED = "UPLOADED"      # File uploaded, not yet processed
    PROCESSING = "PROCESSING"  # Extracting text from PDF
    PARSED = "PARSED"         # Text extracted, ready for AI scoring
    SCORED = "SCORED"         # AI evaluation complete
    FAILED = "FAILED"         # Processing failed at any stage


class Candidate(Base):
    """
    A candidate who applied for a job posting.

    This model follows the same status-tracking pattern as the Job model,
    enabling visibility into each stage of the resume processing pipeline.
    """
    __tablename__ = "candidates"

    id = Column(Integer, primary_key=True, index=True)

    # Multi-tenancy: Inherited from job, but denormalized for query performance
    tenant_id = Column(UUID(as_uuid=True), ForeignKey("users.tenant_id"), nullable=False, index=True)

    job_id = Column(Integer, ForeignKey("jobs.id"), nullable=False, index=True)

    # Candidate Metadata (optional - can be null for blind screening)
    first_name = Column(String, nullable=True)
    last_name = Column(String, nullable=True)
    email = Column(String, nullable=True)
    phone = Column(String, nullable=True)
    location = Column(String, nullable=True)

    # Web Presence URLs
    linkedin_url = Column(String, nullable=True)
    github_url = Column(String, nullable=True)
    portfolio_url = Column(String, nullable=True)
    other_urls = Column(JSONB, nullable=True)  # Catch-all for any other URLs

    # File Storage
    file_path = Column(String, nullable=False)  # S3 key or local path
    original_filename = Column(String, nullable=False)

    # AI Processing Pipeline
    resume_text = Column(Text, nullable=True)  # Raw extracted text
    anonymized_text = Column(Text, nullable=True)  # PII-redacted text for blind screening

    # Status Tracking (mirrors Job model pattern)
    status = Column(
        Enum(CandidateStatus),
        default=CandidateStatus.UPLOADED,
        nullable=False,
        index=True
    )
    error_message = Column(Text, nullable=True)

    # Soft Delete & Retention Policy (EEOC/OFCCP Compliance)
    # Federal law requires keeping employment records for 1-3 years
    is_deleted = Column(Boolean, default=False, nullable=False, index=True)
    deleted_at = Column(DateTime(timezone=True), nullable=True)
    deleted_by_user_id = Column(Integer, ForeignKey("users.id"), nullable=True)
    retention_until = Column(DateTime(timezone=True), nullable=True)  # Auto-calculated: deleted_at + retention_period

    # Timestamps
    created_at = Column(DateTime(timezone=True), server_default=func.now())

    # Relationships
    job = relationship("Job", back_populates="candidates")
    evaluation = relationship("Evaluation", back_populates="candidate", uselist=False, cascade="all, delete-orphan")
