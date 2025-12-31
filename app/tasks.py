"""
Celery tasks for background processing.

These tasks run in separate worker processes and communicate via Redis.
This allows the API to remain responsive while long-running tasks execute.
"""

import logging
import asyncio
from app.core.celery_app import celery_app
from app.core.database import SessionLocal
from app.models.job import Job, JobStatus
from app.services.ai_job_config import generate_job_config, JobConfigGenerationError

logger = logging.getLogger(__name__)


@celery_app.task(name="app.tasks.generate_job_config_task", bind=True)
def generate_job_config_task(self, job_id: int, title: str, description: str):
    """
    Celery task to generate AI job configuration.

    This function runs in a separate worker process, not the API server.
    It tracks the job status throughout the processing lifecycle.

    Args:
        self: Celery task instance (when bind=True)
        job_id: The job ID to process
        title: Job title
        description: Job description

    Returns:
        dict: The generated job configuration or error details
    """
    logger.info(f"[Task {self.request.id}] Starting AI generation for Job {job_id}")

    # Create a new database session for this task
    db = SessionLocal()
    job = None

    try:
        # Get job and mark as PROCESSING
        job = db.query(Job).filter(Job.id == job_id).first()
        if not job:
            logger.error(f"[Task {self.request.id}] Job {job_id} not found")
            return {"status": "error", "message": "Job not found"}

        job.status = JobStatus.PROCESSING
        db.commit()
        logger.info(f"[Task {self.request.id}] Job {job_id} status set to PROCESSING")

        # Generate AI configuration (async function, so we need asyncio.run)
        # This is the proper way to call async code from synchronous Celery
        config = asyncio.run(generate_job_config(title, description))

        # Add job_id to the config
        config['job_id'] = job_id

        # Update job with config and mark as COMPLETED
        job.job_config = config
        job.status = JobStatus.COMPLETED
        job.error_message = None
        db.commit()

        logger.info(f"[Task {self.request.id}] Job {job_id} completed successfully")
        return {"status": "success", "config": config}

    except JobConfigGenerationError as e:
        logger.error(f"[Task {self.request.id}] AI generation failed for Job {job_id}: {e}")
        if job:
            job.status = JobStatus.FAILED
            job.error_message = str(e)
            db.commit()
        return {"status": "failed", "error": str(e)}

    except Exception as e:
        logger.error(f"[Task {self.request.id}] Unexpected error processing Job {job_id}: {e}", exc_info=True)
        if job:
            job.status = JobStatus.FAILED
            job.error_message = f"Unexpected error: {str(e)}"
            db.commit()
        return {"status": "error", "error": str(e)}

    finally:
        db.close()
        logger.info(f"[Task {self.request.id}] Task completed, database session closed")
