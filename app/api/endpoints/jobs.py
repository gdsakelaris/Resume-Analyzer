import logging
from typing import Optional
from uuid import UUID
from fastapi import APIRouter, HTTPException, Depends
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.deps import get_tenant_id, get_current_active_subscription
from app.models.subscription import Subscription, SubscriptionPlan
from app.crud import job as job_crud
from app.crud import oauth_connection as oauth_crud
from app.models.job import JobStatus
from app.schemas.job import JobCreateRequest, JobUpdateRequest, JobResponse, JobCreateResponse, JobStatusEnum
from app.tasks import job_tasks

router = APIRouter(prefix="/jobs", tags=["Starscreen Jobs"])
logger = logging.getLogger(__name__)


@router.post("/", status_code=201, response_model=JobCreateResponse)
def create_job(
    request: JobCreateRequest,
    db: Session = Depends(get_db),
    subscription: Subscription = Depends(get_current_active_subscription)
):
    """
    Create a new job posting and queue AI config generation via Celery.

    **Requires active subscription** (FREE, STARTER, PROFESSIONAL, or ENTERPRISE).

    The job is created immediately with status=PENDING, and processing
    happens asynchronously in a Celery worker via Redis.

    Flow:
    1. Job saved to DB with status=PENDING (via CRUD layer)
    2. Task sent to Redis queue
    3. Celery worker picks up task
    4. Worker sets status=PROCESSING
    5. Worker generates config and sets status=COMPLETED or FAILED

    Use GET /jobs/{job_id} to check status and get results.
    """
    try:
        # Derive tenant_id from the verified subscription
        tenant_id = subscription.user.tenant_id

        # Validate LinkedIn posting requirements if requested
        if request.post_to_linkedin:
            # Check subscription tier (FREE tier not allowed)
            if subscription.plan == SubscriptionPlan.FREE:
                raise HTTPException(
                    status_code=403,
                    detail="LinkedIn posting requires a paid subscription. Upgrade to Recruiter ($20/mo) or higher."
                )

            # Check if LinkedIn is connected
            oauth_conn = oauth_crud.get_connection(db, subscription.user_id, "linkedin")
            if not oauth_conn or not oauth_conn.is_active:
                raise HTTPException(
                    status_code=400,
                    detail="LinkedIn account not connected. Please connect LinkedIn in Settings before posting jobs."
                )

        # Create job using CRUD layer (with tenant_id)
        new_job = job_crud.create(db, request, tenant_id=tenant_id)

        # Queue task to Celery worker via Redis
        # .delay() sends task to Redis and returns immediately
        # Pass post_to_linkedin flag via kwargs for task chaining
        task = job_tasks.generate_job_config_task.apply_async(
            args=[new_job.id, new_job.title, new_job.description],
            kwargs={
                "post_to_linkedin": request.post_to_linkedin,
                "tenant_id": str(tenant_id)
            }
        )

        logger.info(
            f"Created job {new_job.id}: {new_job.title} | Celery task {task.id} queued | "
            f"LinkedIn posting: {request.post_to_linkedin}"
        )

        return JobCreateResponse(
            job_id=new_job.id,
            status=JobStatusEnum.PENDING,
            message=f"Job created successfully. Task {task.id} queued to Celery worker via Redis."
        )

    except HTTPException:
        db.rollback()
        raise  # Re-raise HTTP exceptions as-is
    except Exception as e:
        db.rollback()
        logger.error(f"Error creating job: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to create job: {str(e)}")


@router.get("/{job_id}", response_model=JobResponse)
def get_job(
    job_id: int,
    db: Session = Depends(get_db),
    tenant_id: UUID = Depends(get_tenant_id)
):
    """
    Retrieve a job by ID (tenant-scoped).

    Check the `status` field to see the processing state:
    - PENDING: Job created, AI generation not yet started
    - PROCESSING: AI generation in progress
    - COMPLETED: AI generation complete, check job_config field
    - FAILED: AI generation failed, check error_message field
    """
    job = job_crud.get_by_id(db, job_id, tenant_id=tenant_id)

    if not job:
        raise HTTPException(status_code=404, detail="Job not found")

    return job


@router.get("/", response_model=list[JobResponse])
def list_jobs(
    skip: int = 0,
    limit: int = 100,
    status: Optional[JobStatusEnum] = None,
    db: Session = Depends(get_db),
    tenant_id: UUID = Depends(get_tenant_id)
):
    """
    List all jobs for current tenant with pagination and optional status filtering.

    Args:
        skip: Number of records to skip (default: 0)
        limit: Maximum number of records to return (default: 100, max: 100)
        status: Optional filter by job status (PENDING, PROCESSING, COMPLETED, FAILED)
    """
    if limit > 100:
        limit = 100

    # Convert enum to JobStatus if provided
    status_filter = JobStatus[status.value] if status else None

    jobs = job_crud.get_multi(db, skip=skip, limit=limit, status=status_filter, tenant_id=tenant_id)
    return jobs


@router.put("/{job_id}", response_model=JobResponse)
def update_job(
    job_id: int,
    request: JobUpdateRequest,
    db: Session = Depends(get_db),
    tenant_id: UUID = Depends(get_tenant_id)
):
    """
    Update a job's basic information (title, description, location, etc).

    Only the fields provided in the request will be updated.
    Other fields will remain unchanged. Tenant-scoped.
    """
    updated_job = job_crud.update(db, job_id, request, tenant_id=tenant_id)

    if not updated_job:
        raise HTTPException(status_code=404, detail="Job not found")

    logger.info(f"Updated job {job_id}")
    return updated_job


@router.delete("/{job_id}", status_code=204)
def delete_job(
    job_id: int,
    db: Session = Depends(get_db),
    tenant_id: UUID = Depends(get_tenant_id)
):
    """
    Delete a job by ID (tenant-scoped).
    """
    deleted = job_crud.delete(db, job_id, tenant_id=tenant_id)

    if not deleted:
        raise HTTPException(status_code=404, detail="Job not found")

    logger.info(f"Deleted job {job_id}")
    return None
