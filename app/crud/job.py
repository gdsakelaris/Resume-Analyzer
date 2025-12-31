"""
CRUD operations for Job model.

Implements the Repository pattern to encapsulate all database operations
for jobs, providing a clean interface for the API layer.
"""

from typing import List, Optional
from sqlalchemy.orm import Session
from app.models.job import Job, JobStatus
from app.schemas.job import JobCreateRequest


def create(db: Session, job_data: JobCreateRequest) -> Job:
    """
    Create a new job in the database.

    Args:
        db: Database session
        job_data: Validated job creation data

    Returns:
        Created Job instance with id
    """
    db_job = Job(
        title=job_data.title,
        description=job_data.description,
        location=job_data.location,
        work_authorization_required=job_data.work_authorization_required,
        status=JobStatus.PENDING
    )

    db.add(db_job)
    db.commit()
    db.refresh(db_job)

    return db_job


def get_by_id(db: Session, job_id: int) -> Optional[Job]:
    """
    Retrieve a job by its ID.

    Args:
        db: Database session
        job_id: Job ID to retrieve

    Returns:
        Job instance if found, None otherwise
    """
    return db.query(Job).filter(Job.id == job_id).first()


def get_multi(
    db: Session,
    skip: int = 0,
    limit: int = 100,
    status: Optional[JobStatus] = None
) -> List[Job]:
    """
    Retrieve multiple jobs with pagination and optional filtering.

    Args:
        db: Database session
        skip: Number of records to skip (offset)
        limit: Maximum number of records to return
        status: Optional status filter

    Returns:
        List of Job instances
    """
    query = db.query(Job)

    # Apply status filter if provided
    if status:
        query = query.filter(Job.status == status)

    return query.offset(skip).limit(limit).all()


def update_status(
    db: Session,
    job_id: int,
    status: JobStatus,
    error_message: Optional[str] = None
) -> Optional[Job]:
    """
    Update job status and optionally set error message.

    Args:
        db: Database session
        job_id: Job ID to update
        status: New status
        error_message: Optional error message (cleared if None)

    Returns:
        Updated Job instance if found, None otherwise
    """
    job = get_by_id(db, job_id)
    if not job:
        return None

    job.status = status
    if error_message is not None:
        job.error_message = error_message
    elif status == JobStatus.COMPLETED:
        # Clear error message on success
        job.error_message = None

    db.commit()
    db.refresh(job)

    return job


def update_config(
    db: Session,
    job_id: int,
    config: dict
) -> Optional[Job]:
    """
    Update job with AI-generated configuration.

    Args:
        db: Database session
        job_id: Job ID to update
        config: AI-generated configuration dictionary

    Returns:
        Updated Job instance if found, None otherwise
    """
    job = get_by_id(db, job_id)
    if not job:
        return None

    job.job_config = config
    job.status = JobStatus.COMPLETED
    job.error_message = None

    db.commit()
    db.refresh(job)

    return job


def delete(db: Session, job_id: int) -> bool:
    """
    Delete a job by ID.

    Args:
        db: Database session
        job_id: Job ID to delete

    Returns:
        True if deleted, False if not found
    """
    job = get_by_id(db, job_id)
    if not job:
        return False

    db.delete(job)
    db.commit()

    return True


def count_by_status(db: Session, status: JobStatus) -> int:
    """
    Count jobs by status.

    Args:
        db: Database session
        status: Status to count

    Returns:
        Number of jobs with given status
    """
    return db.query(Job).filter(Job.status == status).count()


def get_stuck_jobs(db: Session, minutes: int = 10) -> List[Job]:
    """
    Find jobs stuck in PROCESSING status for too long.

    Args:
        db: Database session
        minutes: Number of minutes to consider "stuck"

    Returns:
        List of stuck jobs
    """
    from datetime import datetime, timedelta
    cutoff = datetime.utcnow() - timedelta(minutes=minutes)

    return db.query(Job).filter(
        Job.status == JobStatus.PROCESSING,
        Job.updated_at < cutoff
    ).all()
