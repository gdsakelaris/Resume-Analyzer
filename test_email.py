#!/usr/bin/env python3
"""
Test script to diagnose email verification issues.
Run this inside the Docker container to test email sending.
"""

import sys
import os

# Add the app directory to the path
sys.path.insert(0, '/app')

from app.services.email_service import email_service
from app.tasks.email_tasks import send_verification_email_task

def test_direct_email():
    """Test sending email directly without Celery"""
    print("=" * 60)
    print("TEST 1: Direct Email Send (No Celery)")
    print("=" * 60)

    test_email = "gdsakelaris@gmail.com"
    test_code = "123456"

    print(f"Attempting to send verification email to: {test_email}")
    print(f"Verification code: {test_code}")
    print()

    try:
        success = email_service.send_verification_email(
            to_email=test_email,
            verification_code=test_code,
            user_name="Test User"
        )

        if success:
            print("✅ SUCCESS: Email sent successfully!")
            print("Check your inbox at gdsakelaris@gmail.com")
        else:
            print("❌ FAILED: Email sending returned False")
            print("Check the logs above for error details")

    except Exception as e:
        print(f"❌ EXCEPTION: {type(e).__name__}: {str(e)}")
        import traceback
        traceback.print_exc()

    print()

def test_celery_task():
    """Test sending email via Celery task"""
    print("=" * 60)
    print("TEST 2: Celery Task Send")
    print("=" * 60)

    test_email = "gdsakelaris@gmail.com"
    test_code = "654321"

    print(f"Queueing Celery task to send email to: {test_email}")
    print(f"Verification code: {test_code}")
    print()

    try:
        # Queue the task
        result = send_verification_email_task.delay(
            to_email=test_email,
            verification_code=test_code,
            user_name="Test User (Celery)"
        )

        print(f"✅ Task queued successfully!")
        print(f"Task ID: {result.id}")
        print(f"Task state: {result.state}")
        print()
        print("The task should be processed by the Celery worker.")
        print("Check worker logs: docker-compose logs worker --tail=50")

    except Exception as e:
        print(f"❌ EXCEPTION: {type(e).__name__}: {str(e)}")
        import traceback
        traceback.print_exc()

    print()

def check_aws_config():
    """Check AWS SES configuration"""
    print("=" * 60)
    print("AWS SES Configuration")
    print("=" * 60)

    from app.core.config import settings

    print(f"AWS Region: {settings.AWS_REGION}")
    print(f"SES From Email: {settings.AWS_SES_FROM_EMAIL}")
    print(f"SES From Name: {settings.AWS_SES_FROM_NAME}")
    print(f"AWS Access Key ID: {'Set' if settings.AWS_ACCESS_KEY_ID else 'Not Set (using IAM role)'}")
    print(f"AWS Secret Key: {'Set' if settings.AWS_SECRET_ACCESS_KEY else 'Not Set (using IAM role)'}")
    print()

if __name__ == "__main__":
    check_aws_config()
    test_direct_email()
    test_celery_task()

    print("=" * 60)
    print("Tests completed!")
    print("=" * 60)
