"""
Celery utility functions for reliable task queueing.

Provides helper functions to ensure Celery tasks are queued successfully
even when called from FastAPI endpoints.
"""

import logging
from concurrent.futures import ThreadPoolExecutor
from typing import Tuple
from celery import Task
from kombu import Connection

logger = logging.getLogger(__name__)

# Thread pool for queueing tasks from async contexts
# This avoids conflicts with FastAPI's uvicorn async event loop
_executor = ThreadPoolExecutor(max_workers=4, thread_name_prefix="celery_queue")


def _queue_task_sync(task: Task, args: tuple, kwargs: dict) -> Tuple[bool, str, str]:
    """
    Internal function to queue task synchronously in a thread.

    This avoids conflicts with FastAPI's async event loop.

    Returns:
        Tuple[bool, str, str]: (success, task_id, error_message)
    """
    try:
        # Use a fresh Kombu connection to avoid stale connection pool issues
        # This is more reliable than using the celery_app's cached connection
        from app.core.config import settings

        with Connection(settings.REDIS_URL) as conn:
            # Send task using the fresh connection
            result = task.apply_async(
                args=args,
                kwargs=kwargs,
                connection=conn,
                retry=True,
                retry_policy={
                    'max_retries': 3,
                    'interval_start': 0,
                    'interval_step': 0.2,
                    'interval_max': 0.2,
                }
            )
            return (True, result.id, "")
    except Exception as e:
        return (False, "", str(e))


def queue_task_safely(task: Task, *args, **kwargs) -> bool:
    """
    Safely queue a Celery task with connection retry logic.

    This function ensures the Celery broker connection is fresh and handles
    connection errors gracefully. Works correctly from both sync and async
    FastAPI endpoints by running the actual queueing in a thread pool.

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
    # Queue task in a separate thread to avoid async event loop conflicts
    # This is necessary because FastAPI/uvicorn's async event loop can
    # interfere with Celery's connection pool management
    future = _executor.submit(_queue_task_sync, task, args, kwargs)
    success, task_id, error = future.result(timeout=5)

    if success:
        logger.info(f"Task {task.name} queued successfully: {task_id}")
        return True
    else:
        logger.error(f"Failed to queue task {task.name}: {error}")
        return False
