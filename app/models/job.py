import enum
from sqlalchemy import Column, Integer, String, Boolean, DateTime, Enum, func
from sqlalchemy.orm import relationship
from sqlalchemy.dialects.postgresql import JSONB
from app.core.database import Base


class JobStatus(str, enum.Enum):
    """
    Job processing status enum.

    - PENDING: Job created, AI generation not started
    - PROCESSING: AI generation in progress
    - COMPLETED: AI generation completed successfully
    - FAILED: AI generation failed after retries
    """
    PENDING = "PENDING"
    PROCESSING = "PROCESSING"
    COMPLETED = "COMPLETED"
    FAILED = "FAILED"


class Job(Base):
    """
    Job model representing a job posting in the system.
    Stores both raw job data and AI-generated configuration.
    """
    __tablename__ = "jobs"

    id = Column(Integer, primary_key=True, index=True)
    title = Column(String, nullable=False, index=True)
    description = Column(String, nullable=False)
    location = Column(String, nullable=True)
    work_authorization_required = Column(Boolean, default=False)

    # Processing status tracking
    status = Column(Enum(JobStatus), default=JobStatus.PENDING, nullable=False, index=True)
    error_message = Column(String, nullable=True)

    # AI-generated job configuration stored as JSONB
    # Structure matches JobConfigSchema from ai_job_config.py
    job_config = Column(JSONB, nullable=True)

    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())

    # Relationships
    candidates = relationship("Candidate", back_populates="job", cascade="all, delete-orphan")

    def __repr__(self):
        return f"<Job(id={self.id}, title='{self.title}', status={self.status.value})>"
