"""
Celery tasks for LinkedIn job posting.

These tasks run asynchronously after AI config generation completes.
"""

import logging
import asyncio
from uuid import UUID
from app.core.celery_app import celery_app
from app.core.database import SessionLocal
from app.crud import job as job_crud
from app.crud import oauth_connection as oauth_crud
from app.crud import external_job_posting as posting_crud
from app.services.linkedin_service import linkedin_service
from app.services.job_board_base import JobPostingError
from app.models.external_job_posting import PostingStatus

logger = logging.getLogger(__name__)


@celery_app.task(
    name="app.tasks.linkedin_tasks.post_job_to_linkedin",
    bind=True,
    max_retries=3,
    autoretry_for=(JobPostingError, ConnectionError),
    retry_backoff=True,
    retry_backoff_max=600,
    retry_jitter=True
)
def post_job_to_linkedin(self, job_id: int, tenant_id: str):
    """
    Post job to LinkedIn after AI config generation completes.

    This task is triggered when job.status becomes COMPLETED.

    Flow:
    1. Check if user has LinkedIn connected
    2. Check if user has paid subscription (verified in job creation)
    3. Create PENDING posting record
    4. Post job to LinkedIn
    5. Update posting record with result

    Args:
        self: Celery task instance (when bind=True)
        job_id: Job ID to post
        tenant_id: Tenant ID for multi-tenancy (string UUID)

    Returns:
        dict: Result with status and details
    """
    logger.info(f"[Task {self.request.id}] Posting job {job_id} to LinkedIn")

    db = SessionLocal()

    try:
        # Convert tenant_id to UUID
        tenant_uuid = UUID(tenant_id)

        # Get job
        job = job_crud.get_by_id(db, job_id)
        if not job:
            logger.error(f"Job {job_id} not found")
            return {"status": "error", "message": "Job not found"}

        # Get user's LinkedIn OAuth connection
        oauth_conn = oauth_crud.get_connection_by_tenant(db, tenant_uuid, "linkedin")
        if not oauth_conn or not oauth_conn.is_active:
            logger.warning(f"No active LinkedIn connection for tenant {tenant_id}")

            # Create FAILED posting record for UI display
            posting_crud.create(
                db=db,
                job_id=job_id,
                tenant_id=tenant_uuid,
                provider="linkedin",
                status=PostingStatus.FAILED,
                error_message="LinkedIn account not connected. Please connect your LinkedIn account in Settings."
            )

            return {
                "status": "skipped",
                "message": "No LinkedIn connection"
            }

        # Check if posting already exists (avoid duplicates)
        existing_postings = posting_crud.get_by_job_id(db, job_id, provider="linkedin")
        if existing_postings:
            logger.info(f"Job {job_id} already has LinkedIn posting")
            return {
                "status": "skipped",
                "message": "Job already posted to LinkedIn"
            }

        # Create PENDING posting record
        posting = posting_crud.create(
            db=db,
            job_id=job_id,
            tenant_id=tenant_uuid,
            provider="linkedin",
            status=PostingStatus.PENDING
        )

        # Update to POSTING status
        posting_crud.update_status(db, posting.id, PostingStatus.POSTING)
        logger.info(f"[Task {self.request.id}] Posting job {job_id} to LinkedIn (posting_id={posting.id})")

        # Post to LinkedIn (async operation)
        # asyncio.run() is used to call async function from sync Celery task
        linkedin_job_id, job_url = asyncio.run(
            linkedin_service.post_job(job, oauth_conn)
        )

        # Update posting record with success
        posting_crud.update_success(
            db=db,
            posting_id=posting.id,
            external_job_id=linkedin_job_id,
            external_url=job_url,
            status=PostingStatus.ACTIVE
        )

        logger.info(
            f"[Task {self.request.id}] Successfully posted job {job_id} to LinkedIn: "
            f"{job_url} (LinkedIn ID: {linkedin_job_id})"
        )

        return {
            "status": "success",
            "linkedin_job_id": linkedin_job_id,
            "job_url": job_url,
            "posting_id": str(posting.id)
        }

    except JobPostingError as e:
        logger.error(f"[Task {self.request.id}] LinkedIn posting failed for job {job_id}: {e}")

        # Update posting record with failure
        if 'posting' in locals():
            posting_crud.update_status(
                db=db,
                posting_id=posting.id,
                status=PostingStatus.FAILED,
                error_message=str(e),
                increment_retry=True
            )

        # Re-raise to trigger Celery retry
        raise

    except Exception as e:
        logger.error(
            f"[Task {self.request.id}] Unexpected error posting job {job_id}: {e}",
            exc_info=True
        )

        # Update posting record with failure (no retry for unexpected errors)
        if 'posting' in locals():
            posting_crud.update_status(
                db=db,
                posting_id=posting.id,
                status=PostingStatus.FAILED,
                error_message=f"Unexpected error: {str(e)}"
            )

        return {
            "status": "error",
            "error": str(e)
        }

    finally:
        db.close()
        logger.info(f"[Task {self.request.id}] Task completed, database session closed")
