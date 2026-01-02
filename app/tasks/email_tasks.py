"""
Celery tasks for email operations.

Handles asynchronous email sending with retry logic.
"""

import logging
from typing import Optional
from celery import shared_task
from app.services.email_service import email_service

logger = logging.getLogger(__name__)


@shared_task(
    bind=True,
    name="send_verification_email_task",
    max_retries=3,
    default_retry_delay=60,  # Retry after 60 seconds
    autoretry_for=(Exception,),
    retry_backoff=True,
    retry_backoff_max=600,  # Max 10 minutes between retries
    retry_jitter=True
)
def send_verification_email_task(
    self,
    to_email: str,
    verification_code: str,
    user_name: Optional[str] = None
):
    """
    Celery task to send verification email asynchronously.

    Features:
    - Automatic retry on failure (up to 3 attempts)
    - Exponential backoff with jitter
    - Detailed logging

    Args:
        to_email: Recipient email address
        verification_code: 6-digit verification code
        user_name: Optional user's full name

    Raises:
        Exception: If email sending fails after all retries
    """
    try:
        logger.info(f"Sending verification email to {to_email} (attempt {self.request.retries + 1})")

        success = email_service.send_verification_email(
            to_email=to_email,
            verification_code=verification_code,
            user_name=user_name
        )

        if not success:
            raise Exception(f"Failed to send verification email to {to_email}")

        logger.info(f"Verification email sent successfully to {to_email}")
        return {"status": "success", "email": to_email}

    except Exception as e:
        logger.error(f"Error sending verification email to {to_email}: {str(e)}")

        # If we've exhausted retries, log final failure
        if self.request.retries >= self.max_retries:
            logger.error(f"All retry attempts exhausted for {to_email}")

        raise  # Re-raise to trigger Celery retry


@shared_task(name="cleanup_expired_verification_codes")
def cleanup_expired_verification_codes_task():
    """
    Periodic task to clean up expired verification codes.

    Should be configured in Celery Beat to run daily.

    Example celerybeat schedule:
    ```python
    beat_schedule = {
        'cleanup-expired-codes': {
            'task': 'cleanup_expired_verification_codes',
            'schedule': crontab(hour=2, minute=0),  # Run at 2 AM daily
        },
    }
    ```
    """
    from app.core.database import SessionLocal
    from app.core.verification import cleanup_expired_codes

    db = SessionLocal()
    try:
        deleted_count = cleanup_expired_codes(db)
        logger.info(f"Cleaned up {deleted_count} expired verification codes")
        return {"status": "success", "deleted_count": deleted_count}
    except Exception as e:
        logger.error(f"Error cleaning up verification codes: {str(e)}")
        raise
    finally:
        db.close()
