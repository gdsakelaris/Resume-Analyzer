"""
Celery application configuration.

This module configures Celery to use Redis as both the message broker and result backend.
The worker process will use this configuration to connect to Redis and process tasks.
"""

from celery import Celery
from app.core.config import settings

# Create Celery instance
celery_app = Celery(
    "resume_analyzer_worker",
    broker=settings.REDIS_URL,
    backend=settings.REDIS_URL
)

# Configure Celery
celery_app.conf.update(
    # Serialization
    task_serializer="json",
    accept_content=["json"],
    result_serializer="json",

    # Timezone
    timezone="UTC",
    enable_utc=True,

    # Task behavior
    task_track_started=True,  # Track when tasks start (for monitoring)
    task_time_limit=300,  # 5 minutes max per task
    task_soft_time_limit=240,  # Warn at 4 minutes

    # Result backend
    result_expires=3600,  # Results expire after 1 hour

    # Worker behavior
    worker_prefetch_multiplier=1,  # Only fetch 1 task at a time
    worker_max_tasks_per_child=50,  # Restart worker after 50 tasks (prevent memory leaks)
)

# Auto-discover tasks from app.tasks module
celery_app.autodiscover_tasks(['app'])
