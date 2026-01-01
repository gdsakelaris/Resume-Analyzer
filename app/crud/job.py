"""
CRUD operations for Job model.

Implements the Repository pattern to encapsulate all database operations
for jobs, providing a clean interface for the API layer.

MULTI-TENANCY: All operations MUST filter by tenant_id to enforce row-level security.
"""

from typing import List, Optional
from uuid import UUID
from sqlalchemy.orm import Session
from app.models.job import Job, JobStatus
from app.schemas.job import JobCreateRequest, JobUpdateRequest


def create(db: Session, job_data: JobCreateRequest, tenant_id: UUID) -> Job:
    """
    Create a new job in the database (tenant-scoped).

    Args:
        db: Database session
        job_data: Validated job creation data
        tenant_id: Tenant ID for multi-tenancy isolation

    Returns:
        Created Job instance with id
    """
    db_job = Job(
        tenant_id=tenant_id,
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


def get_by_id(db: Session, job_id: int, tenant_id: Optional[UUID] = None) -> Optional[Job]:
    """
    Retrieve a job by its ID (tenant-scoped when tenant_id provided).

    Args:
        db: Database session
        job_id: Job ID to retrieve
        tenant_id: Optional tenant ID for multi-tenancy isolation

    Returns:
        Job instance if found, None otherwise
    """
    query = db.query(Job).filter(Job.id == job_id)

    if tenant_id:
        query = query.filter(Job.tenant_id == tenant_id)

    return query.first()


def get_multi(
    db: Session,
    skip: int = 0,
    limit: int = 100,
    status: Optional[JobStatus] = None,
    tenant_id: Optional[UUID] = None
) -> List[Job]:
    """
    Retrieve multiple jobs with pagination and optional filtering (tenant-scoped).

    Args:
        db: Database session
        skip: Number of records to skip (offset)
        limit: Maximum number of records to return
        status: Optional status filter
        tenant_id: Optional tenant ID for multi-tenancy isolation

    Returns:
        List of Job instances
    """
    query = db.query(Job)

    # CRITICAL: Apply tenant filter first to enforce row-level security
    if tenant_id:
        query = query.filter(Job.tenant_id == tenant_id)

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


def update(db: Session, job_id: int, job_data: JobUpdateRequest, tenant_id: Optional[UUID] = None) -> Optional[Job]:
    """
    Update a job's basic information (title, description, location, etc) - tenant-scoped.

    Args:
        db: Database session
        job_id: Job ID to update
        job_data: Updated job data
        tenant_id: Optional tenant ID for multi-tenancy isolation

    Returns:
        Updated Job instance if found, None otherwise
    """
    job = get_by_id(db, job_id, tenant_id=tenant_id)
    if not job:
        return None

    # Update only provided fields
    if job_data.title is not None:
        job.title = job_data.title
    if job_data.description is not None:
        job.description = job_data.description
    if job_data.location is not None:
        job.location = job_data.location
    if job_data.work_authorization_required is not None:
        job.work_authorization_required = job_data.work_authorization_required

    db.commit()
    db.refresh(job)

    return job


def delete(db: Session, job_id: int, tenant_id: Optional[UUID] = None) -> bool:
    """
    Delete a job by ID (tenant-scoped).

    Args:
        db: Database session
        job_id: Job ID to delete
        tenant_id: Optional tenant ID for multi-tenancy isolation

    Returns:
        True if deleted, False if not found
    """
    job = get_by_id(db, job_id, tenant_id=tenant_id)
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
