"""
Email verification endpoints.

Handles sending, resending, and verifying 6-digit email verification codes.
"""

import logging
from fastapi import APIRouter, HTTPException, Depends, status
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.deps import get_current_user
from app.core.verification import create_verification_code, verify_code, get_active_verification
from app.core.rate_limiter import check_send_verification_limit, check_resend_verification_limit, check_verify_code_limit
from app.models.user import User
from app.schemas.verification import (
    VerifyCodeRequest,
    ResendCodeRequest,
    VerificationResponse,
    SendCodeResponse
)
from app.tasks.email_tasks import send_verification_email_task

router = APIRouter(prefix="/auth", tags=["Email Verification"])
logger = logging.getLogger(__name__)


@router.post("/send-verification-code", response_model=SendCodeResponse)
def send_verification_code(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Generate and send a verification code to the current user's email.

    Rate limit: 1 request per minute per user.

    Returns:
        SendCodeResponse: Success message and expiration time

    Raises:
        HTTPException 429: Rate limit exceeded
        HTTPException 400: User already verified
    """
    # Check if user is already verified
    if current_user.is_verified:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Email is already verified"
        )

    # Apply rate limiting (1 per minute)
    check_send_verification_limit(str(current_user.id))

    # Create verification code
    verification = create_verification_code(db, current_user.id)

    # Queue async email task
    send_verification_email_task.delay(
        to_email=current_user.email,
        verification_code=verification.code,
        user_name=current_user.full_name
    )

    logger.info(f"Verification code sent to user {current_user.email}")

    return SendCodeResponse(
        success=True,
        message=f"Verification code sent to {current_user.email}",
        expires_in_minutes=15
    )


@router.post("/resend-verification-code", response_model=SendCodeResponse)
def resend_verification_code(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Resend verification code to the current user's email.

    Generates a new code and invalidates the old one.
    Rate limit: 1 request per 2 minutes per user.

    Returns:
        SendCodeResponse: Success message and expiration time

    Raises:
        HTTPException 429: Rate limit exceeded
        HTTPException 400: User already verified
    """
    # Check if user is already verified
    if current_user.is_verified:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Email is already verified"
        )

    # Apply rate limiting (1 per 2 minutes)
    check_resend_verification_limit(str(current_user.id))

    # Create new verification code (invalidates old one)
    verification = create_verification_code(db, current_user.id)

    # Queue async email task
    send_verification_email_task.delay(
        to_email=current_user.email,
        verification_code=verification.code,
        user_name=current_user.full_name
    )

    logger.info(f"Verification code resent to user {current_user.email}")

    return SendCodeResponse(
        success=True,
        message=f"New verification code sent to {current_user.email}",
        expires_in_minutes=15
    )


@router.post("/verify-email", response_model=VerificationResponse)
def verify_email(
    request: VerifyCodeRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Verify user's email with a 6-digit code.

    Rate limit: 10 attempts per 10 minutes per user.

    Args:
        request: VerifyCodeRequest with 6-digit code

    Returns:
        VerificationResponse: Success status and message

    Raises:
        HTTPException 429: Rate limit exceeded
        HTTPException 400: Invalid, expired, or already used code
    """
    # Check if user is already verified
    if current_user.is_verified:
        return VerificationResponse(
            success=True,
            message="Email is already verified",
            is_verified=True
        )

    # Apply rate limiting (10 per 10 minutes)
    check_verify_code_limit(str(current_user.id))

    # Verify the code
    success, message = verify_code(db, current_user.id, request.code)

    if not success:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=message
        )

    logger.info(f"User {current_user.email} successfully verified their email")

    return VerificationResponse(
        success=True,
        message=message,
        is_verified=True
    )


@router.get("/verification-status", response_model=VerificationResponse)
def get_verification_status(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Get the current user's email verification status.

    Returns:
        VerificationResponse: Verification status and any active code info
    """
    if current_user.is_verified:
        return VerificationResponse(
            success=True,
            message="Email is verified",
            is_verified=True
        )

    # Check if there's an active verification code
    active_verification = get_active_verification(db, current_user.id)

    if active_verification:
        message = "Verification pending. Please check your email for the code."
    else:
        message = "Email not verified. Please request a verification code."

    return VerificationResponse(
        success=False,
        message=message,
        is_verified=False
    )
