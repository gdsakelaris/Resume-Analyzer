"""
Celery utility functions for reliable task queueing.

Provides helper functions to ensure Celery tasks are queued successfully
even when called from FastAPI endpoints.
"""

import logging
from typing import Any, Dict
from celery import Task
from app.core.celery_app import celery_app

logger = logging.getLogger(__name__)


def queue_task_safely(task: Task, *args, **kwargs) -> bool:
    """
    Safely queue a Celery task with connection retry logic.

    This function ensures the Celery broker connection is fresh and handles
    connection errors gracefully. Use this instead of task.delay() when
    queueing from FastAPI endpoints.

    Args:
        task: The Celery task to queue
        *args: Positional arguments for the task
        **kwargs: Keyword arguments for the task

    Returns:
        bool: True if task was queued successfully, False otherwise

    Example:
        from app.tasks.email_tasks import send_verification_email_task
        success = queue_task_safely(
            send_verification_email_task,
            to_email='user@example.com',
            verification_code='123456',
            user_name='John Doe'
        )
    """
    try:
        # Use apply_async with explicit connection
        # This ensures we get a fresh connection from the pool
        result = task.apply_async(args=args, kwargs=kwargs, retry=True)
        logger.info(f"Task {task.name} queued successfully: {result.id}")
        return True
    except Exception as e:
        logger.error(f"Failed to queue task {task.name}: {e}")
        # Try one more time with a fresh connection
        try:
            # Close existing connections in the pool
            celery_app.connection_or_acquire().close()
            # Try again
            result = task.apply_async(args=args, kwargs=kwargs, retry=True)
            logger.info(f"Task {task.name} queued on retry: {result.id}")
            return True
        except Exception as retry_error:
            logger.error(f"Failed to queue task {task.name} on retry: {retry_error}")
            return False
