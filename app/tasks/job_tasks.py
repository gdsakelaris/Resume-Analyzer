"""
Celery tasks for job processing.

These tasks handle AI-powered job configuration generation in the background.
"""

import logging
import asyncio
from app.core.celery_app import celery_app
from app.core.database import SessionLocal
from app.crud import job as job_crud
from app.models.job import JobStatus
from app.services.ai_job_config import generate_job_config, JobConfigGenerationError

logger = logging.getLogger(__name__)


@celery_app.task(name="app.tasks.job_tasks.generate_job_config_task", bind=True)
def generate_job_config_task(self, job_id: int, title: str, description: str, post_to_linkedin: bool = False, tenant_id: str = None):
    """
    Celery task to generate AI job configuration.

    This function runs in a separate worker process, not the API server.
    It uses the CRUD layer for all database operations to maintain
    consistency with the rest of the application.

    Args:
        self: Celery task instance (when bind=True)
        job_id: The job ID to process
        title: Job title
        description: Job description
        post_to_linkedin: Whether to post job to LinkedIn after config generation
        tenant_id: Tenant ID for LinkedIn posting (optional)

    Returns:
        dict: The generated job configuration or error details
    """
    logger.info(f"[Task {self.request.id}] Starting AI generation for Job {job_id} | LinkedIn posting: {post_to_linkedin}")

    # Create a new database session for this task
    db = SessionLocal()

    try:
        # Get job and mark as PROCESSING (using CRUD layer)
        job = job_crud.get_by_id(db, job_id)
        if not job:
            logger.error(f"[Task {self.request.id}] Job {job_id} not found")
            return {"status": "error", "message": "Job not found"}

        job_crud.update_status(db, job_id, JobStatus.PROCESSING)
        logger.info(f"[Task {self.request.id}] Job {job_id} status set to PROCESSING")

        # Generate AI configuration (async function, so we need asyncio.run)
        # This is the proper way to call async code from synchronous Celery
        config = asyncio.run(generate_job_config(title, description))

        # Add job_id to the config
        config['job_id'] = job_id

        # Update job with config and mark as COMPLETED (using CRUD layer)
        job_crud.update_config(db, job_id, config)

        logger.info(f"[Task {self.request.id}] Job {job_id} completed successfully")

        # Chain LinkedIn posting task if requested
        if post_to_linkedin and tenant_id:
            from app.tasks.linkedin_tasks import post_job_to_linkedin
            post_job_to_linkedin.delay(job_id, tenant_id)
            logger.info(f"[Task {self.request.id}] Queued LinkedIn posting task for job {job_id}")

        return {"status": "success", "config": config}

    except JobConfigGenerationError as e:
        logger.error(f"[Task {self.request.id}] AI generation failed for Job {job_id}: {e}")
        job_crud.update_status(db, job_id, JobStatus.FAILED, error_message=str(e))
        return {"status": "failed", "error": str(e)}

    except Exception as e:
        logger.error(f"[Task {self.request.id}] Unexpected error processing Job {job_id}: {e}", exc_info=True)
        job_crud.update_status(db, job_id, JobStatus.FAILED, error_message=f"Unexpected error: {str(e)}")
        return {"status": "error", "error": str(e)}

    finally:
        db.close()
        logger.info(f"[Task {self.request.id}] Task completed, database session closed")
