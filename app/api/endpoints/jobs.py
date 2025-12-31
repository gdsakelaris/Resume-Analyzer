import logging
from typing import Optional
from fastapi import APIRouter, HTTPException, Depends
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.crud import job as job_crud
from app.models.job import JobStatus
from app.schemas.job import JobCreateRequest, JobResponse, JobCreateResponse, JobStatusEnum
from app.tasks import job_tasks

router = APIRouter(prefix="/jobs", tags=["Starscreen Jobs"])
logger = logging.getLogger(__name__)


@router.post("/", status_code=201, response_model=JobCreateResponse)
def create_job(
    request: JobCreateRequest,
    db: Session = Depends(get_db)
):
    """
    Create a new job posting and queue AI config generation via Celery.

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
        # Create job using CRUD layer
        new_job = job_crud.create(db, request)

        # Queue task to Celery worker via Redis
        # .delay() sends task to Redis and returns immediately
        task = job_tasks.generate_job_config_task.delay(
            new_job.id,
            new_job.title,
            new_job.description
        )

        logger.info(f"Created job {new_job.id}: {new_job.title} | Celery task {task.id} queued")

        return JobCreateResponse(
            job_id=new_job.id,
            status=JobStatusEnum.PENDING,
            message=f"Job created successfully. Task {task.id} queued to Celery worker via Redis."
        )

    except Exception as e:
        db.rollback()
        logger.error(f"Error creating job: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to create job: {str(e)}")


@router.get("/{job_id}", response_model=JobResponse)
def get_job(job_id: int, db: Session = Depends(get_db)):
    """
    Retrieve a job by ID.

    Check the `status` field to see the processing state:
    - PENDING: Job created, AI generation not yet started
    - PROCESSING: AI generation in progress
    - COMPLETED: AI generation complete, check job_config field
    - FAILED: AI generation failed, check error_message field
    """
    job = job_crud.get_by_id(db, job_id)

    if not job:
        raise HTTPException(status_code=404, detail="Job not found")

    return job


@router.get("/", response_model=list[JobResponse])
def list_jobs(
    skip: int = 0,
    limit: int = 100,
    status: Optional[JobStatusEnum] = None,
    db: Session = Depends(get_db)
):
    """
    List all jobs with pagination and optional status filtering.

    Args:
        skip: Number of records to skip (default: 0)
        limit: Maximum number of records to return (default: 100, max: 100)
        status: Optional filter by job status (PENDING, PROCESSING, COMPLETED, FAILED)
    """
    if limit > 100:
        limit = 100

    # Convert enum to JobStatus if provided
    status_filter = JobStatus[status.value] if status else None

    jobs = job_crud.get_multi(db, skip=skip, limit=limit, status=status_filter)
    return jobs


@router.delete("/{job_id}", status_code=204)
def delete_job(job_id: int, db: Session = Depends(get_db)):
    """
    Delete a job by ID.
    """
    deleted = job_crud.delete(db, job_id)

    if not deleted:
        raise HTTPException(status_code=404, detail="Job not found")

    logger.info(f"Deleted job {job_id}")
    return None
