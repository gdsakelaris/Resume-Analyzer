"""
CRUD operations for external job postings.

Tracks job postings to LinkedIn, Indeed, ZipRecruiter, etc.
"""

from typing import List, Optional
from uuid import UUID
from datetime import datetime
from sqlalchemy.orm import Session
from app.models.external_job_posting import ExternalJobPosting, PostingStatus


def create(
    db: Session,
    job_id: int,
    tenant_id: UUID,
    provider: str,
    status: PostingStatus = PostingStatus.PENDING,
    error_message: Optional[str] = None
) -> ExternalJobPosting:
    """
    Create new external job posting record.

    Args:
        db: Database session
        job_id: Job ID
        tenant_id: Tenant UUID (for multi-tenancy)
        provider: OAuth provider name (e.g., "linkedin")
        status: Initial posting status (default: PENDING)
        error_message: Error message if status is FAILED

    Returns:
        ExternalJobPosting: Created posting record
    """
    posting = ExternalJobPosting(
        job_id=job_id,
        tenant_id=tenant_id,
        provider=provider,
        status=status,
        error_message=error_message
    )

    db.add(posting)
    db.commit()
    db.refresh(posting)
    return posting


def update_status(
    db: Session,
    posting_id: UUID,
    status: PostingStatus,
    error_message: Optional[str] = None,
    increment_retry: bool = False
) -> Optional[ExternalJobPosting]:
    """
    Update posting status.

    Args:
        db: Database session
        posting_id: Posting UUID
        status: New status
        error_message: Error message if status is FAILED
        increment_retry: Whether to increment retry counter

    Returns:
        Updated ExternalJobPosting or None if not found
    """
    posting = db.query(ExternalJobPosting).filter(
        ExternalJobPosting.id == posting_id
    ).first()

    if not posting:
        return None

    posting.status = status
    posting.error_message = error_message

    if increment_retry:
        posting.retry_count += 1

    if status == PostingStatus.ACTIVE:
        posting.posted_at = datetime.utcnow()
    elif status == PostingStatus.CLOSED:
        posting.closed_at = datetime.utcnow()

    db.commit()
    db.refresh(posting)
    return posting


def update_success(
    db: Session,
    posting_id: UUID,
    external_job_id: str,
    external_url: str,
    status: PostingStatus = PostingStatus.ACTIVE
) -> Optional[ExternalJobPosting]:
    """
    Update posting with successful posting data.

    Args:
        db: Database session
        posting_id: Posting UUID
        external_job_id: Job ID from external platform (e.g., LinkedIn job ID)
        external_url: URL to job on external platform
        status: New status (default: ACTIVE)

    Returns:
        Updated ExternalJobPosting or None if not found
    """
    posting = db.query(ExternalJobPosting).filter(
        ExternalJobPosting.id == posting_id
    ).first()

    if not posting:
        return None

    posting.status = status
    posting.external_job_id = external_job_id
    posting.external_url = external_url
    posting.posted_at = datetime.utcnow()
    posting.error_message = None  # Clear any previous errors

    db.commit()
    db.refresh(posting)
    return posting


def get_by_job_id(db: Session, job_id: int, provider: Optional[str] = None) -> List[ExternalJobPosting]:
    """
    Get all postings for a job.

    Args:
        db: Database session
        job_id: Job ID
        provider: Optional provider filter (e.g., "linkedin")

    Returns:
        List of ExternalJobPosting records
    """
    query = db.query(ExternalJobPosting).filter(ExternalJobPosting.job_id == job_id)

    if provider:
        query = query.filter(ExternalJobPosting.provider == provider)

    return query.all()


def get_by_id(db: Session, posting_id: UUID) -> Optional[ExternalJobPosting]:
    """
    Get posting by ID.

    Args:
        db: Database session
        posting_id: Posting UUID

    Returns:
        ExternalJobPosting or None if not found
    """
    return db.query(ExternalJobPosting).filter(
        ExternalJobPosting.id == posting_id
    ).first()


def delete(db: Session, posting_id: UUID) -> bool:
    """
    Delete posting record.

    Args:
        db: Database session
        posting_id: Posting UUID

    Returns:
        bool: True if deleted, False if not found
    """
    posting = get_by_id(db, posting_id)
    if not posting:
        return False

    db.delete(posting)
    db.commit()
    return True
