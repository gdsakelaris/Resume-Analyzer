"""
Candidate database model.

Represents a job candidate who has submitted a resume for a specific job posting.
Tracks the resume processing pipeline from upload through parsing to scoring.
"""

from sqlalchemy import Column, Integer, String, ForeignKey, Enum, Text, DateTime, func
from sqlalchemy.orm import relationship
from sqlalchemy.dialects.postgresql import JSONB
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
    job_id = Column(Integer, ForeignKey("jobs.id"), nullable=False, index=True)

    # Candidate Metadata (optional - can be null for blind screening)
    first_name = Column(String, nullable=True)
    last_name = Column(String, nullable=True)
    email = Column(String, nullable=True)

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

    # Timestamps
    created_at = Column(DateTime(timezone=True), server_default=func.now())

    # Relationships
    job = relationship("Job", back_populates="candidates")
    evaluation = relationship("Evaluation", back_populates="candidate", uselist=False, cascade="all, delete-orphan")
