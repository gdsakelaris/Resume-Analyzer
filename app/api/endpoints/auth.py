"""
Authentication endpoints for user registration, login, and token refresh.

Implements JWT-based stateless authentication:
- POST /register: Create new user account
- POST /login: Authenticate and receive JWT tokens
- POST /refresh: Get new access token using refresh token
- GET /me: Get current user profile
- DELETE /me: Delete current user account (cancels Stripe subscription)
"""

import logging
import uuid
import stripe
import secrets
from datetime import datetime, timedelta, timezone
from fastapi import APIRouter, HTTPException, Depends, status
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.security import verify_password, get_password_hash, create_access_token, create_refresh_token, decode_token
from app.core.deps import get_current_user
from app.core.config import settings
from app.core.verification import create_verification_code
from app.core.celery_utils import queue_task_safely
from app.models.user import User
from app.models.subscription import Subscription, SubscriptionPlan, SubscriptionStatus
from app.schemas.user import (
    UserRegisterRequest,
    UserLoginRequest,
    TokenResponse,
    TokenRefreshRequest,
    UserResponse,
    ForgotPasswordRequest,
    ResetPasswordRequest
)
from app.tasks.email_tasks import send_verification_email_task
from app.services.email_service import email_service

router = APIRouter(prefix="/auth", tags=["Authentication"])
logger = logging.getLogger(__name__)

# Initialize Stripe
stripe.api_key = settings.STRIPE_API_KEY


@router.post("/register", status_code=201, response_model=TokenResponse)
def register(
    request: UserRegisterRequest,
    db: Session = Depends(get_db)
):
    """
    Register a new user account.

    Creates:
    1. User record with hashed password and unique tenant_id
    2. Free trial subscription (5 candidates/month)

    Returns JWT tokens for immediate login.
    """
    # Check if email already exists
    existing_user = db.query(User).filter(User.email == request.email).first()
    if existing_user:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Email already registered"
        )

    # Create user with unique tenant_id
    new_user = User(
        id=uuid.uuid4(),
        tenant_id=uuid.uuid4(),  # Each user gets their own tenant
        email=request.email,
        hashed_password=get_password_hash(request.password),
        full_name=request.full_name,
        company_name=request.company_name,
        is_active=True,
        is_verified=False,  # Email verification can be added later
    )
    db.add(new_user)
    db.flush()  # Flush to get user.id for subscription FK

    # Create free trial subscription
    subscription = Subscription(
        id=uuid.uuid4(),
        user_id=new_user.id,
        plan=SubscriptionPlan.FREE,
        status=SubscriptionStatus.ACTIVE,  # Free tier is active (no trial period)
        monthly_candidate_limit=settings.FREE_TIER_CANDIDATE_LIMIT,
        candidates_used_this_month=0,
    )
    db.add(subscription)
    db.commit()
    db.refresh(new_user)

    logger.info(f"New user registered: {new_user.email} (tenant_id: {new_user.tenant_id})")

    # Generate and send verification code
    verification = create_verification_code(db, new_user.id)
    success = queue_task_safely(
        send_verification_email_task,
        to_email=new_user.email,
        verification_code=verification.code,
        user_name=new_user.full_name
    )
    if success:
        logger.info(f"Verification email queued for {new_user.email}")
    else:
        logger.error(f"Failed to queue verification email for {new_user.email}")
        # Don't fail registration if email fails - user can request resend

    # Generate JWT tokens
    access_token = create_access_token(data={"sub": str(new_user.id), "tenant_id": str(new_user.tenant_id), "is_admin": new_user.is_admin})
    refresh_token = create_refresh_token(data={"sub": str(new_user.id)})

    return TokenResponse(
        access_token=access_token,
        refresh_token=refresh_token,
        token_type="bearer",
        user=UserResponse.model_validate(new_user)
    )


@router.post("/login", response_model=TokenResponse)
def login(
    request: UserLoginRequest,
    db: Session = Depends(get_db)
):
    """
    Authenticate user and return JWT tokens.

    Validates email/password and returns access + refresh tokens.
    Updates last_login_at timestamp.
    """
    # Find user by email
    user = db.query(User).filter(User.email == request.username).first()
    if not user or not verify_password(request.password, user.hashed_password):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect email or password",
            headers={"WWW-Authenticate": "Bearer"},
        )

    if not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Account is inactive. Please contact support."
        )

    # Update last login timestamp
    user.last_login_at = datetime.now(timezone.utc)
    db.commit()

    logger.info(f"User logged in: {user.email} (verified: {user.is_verified})")

    # Generate JWT tokens (allow unverified users to login and see verification page)
    access_token = create_access_token(data={"sub": str(user.id), "tenant_id": str(user.tenant_id), "is_admin": user.is_admin})
    refresh_token = create_refresh_token(data={"sub": str(user.id)})

    return TokenResponse(
        access_token=access_token,
        refresh_token=refresh_token,
        token_type="bearer",
        user=UserResponse.model_validate(user)
    )


@router.post("/refresh", response_model=TokenResponse)
def refresh_token(
    request: TokenRefreshRequest,
    db: Session = Depends(get_db)
):
    """
    Refresh access token using refresh token.

    Validates the refresh token and issues a new access token.
    Refresh token remains valid until its expiration.
    """
    try:
        payload = decode_token(request.refresh_token)
        user_id: str = payload.get("sub")
        token_type: str = payload.get("type")

        if user_id is None or token_type != "refresh":
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid refresh token"
            )

        # Verify user still exists and is active
        user = db.query(User).filter(User.id == uuid.UUID(user_id)).first()
        if not user or not user.is_active:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="User not found or inactive"
            )

        # Generate new tokens
        access_token = create_access_token(data={"sub": str(user.id), "tenant_id": str(user.tenant_id), "is_admin": user.is_admin})
        refresh_token = create_refresh_token(data={"sub": str(user.id)})

        return TokenResponse(
            access_token=access_token,
            refresh_token=refresh_token,
            token_type="bearer"
        )

    except Exception as e:
        logger.error(f"Token refresh error: {e}")
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or expired refresh token"
        )


@router.get("/me", response_model=UserResponse)
def get_current_user_profile(
    current_user: User = Depends(get_current_user)
):
    """
    Get current authenticated user's profile.

    Requires valid JWT token in Authorization header.
    """
    return current_user


@router.delete("/me")
def delete_current_user(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Delete the current user's account.

    IMPORTANT: This will:
    1. Cancel any active Stripe subscription (user won't be charged anymore)
    2. Delete the user account and ALL associated data (jobs, candidates, evaluations)
    3. This action is IRREVERSIBLE

    Returns a success message.
    """
    try:
        # Get user's subscription
        subscription = db.query(Subscription).filter(
            Subscription.user_id == current_user.id
        ).first()

        # Cancel Stripe subscription if it exists
        stripe_canceled = False
        if subscription and subscription.stripe_subscription_id:
            try:
                logger.info(f"Canceling Stripe subscription {subscription.stripe_subscription_id} for user {current_user.email}")
                stripe.Subscription.delete(subscription.stripe_subscription_id)
                stripe_canceled = True
                logger.info(f"Stripe subscription canceled successfully")
            except stripe.error.StripeError as e:
                logger.error(f"Failed to cancel Stripe subscription: {e}")
                # Continue with user deletion even if Stripe cancellation fails
                # User can manually cancel in Stripe dashboard if needed

        # Delete the user (cascade will delete subscription and all related data)
        user_email = current_user.email
        db.delete(current_user)
        db.commit()

        logger.info(f"User account deleted: {user_email} (Stripe canceled: {stripe_canceled})")

        return {
            "message": "Account deleted successfully",
            "stripe_subscription_canceled": stripe_canceled
        }

    except Exception as e:
        db.rollback()
        logger.error(f"Error deleting user {current_user.email}: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to delete account: {str(e)}"
        )


@router.post("/forgot-password")
def forgot_password(
    request: ForgotPasswordRequest,
    db: Session = Depends(get_db)
):
    """
    Send password reset email.

    Generates a secure reset token and sends it via email.
    The token expires in 1 hour.

    Always returns success to prevent email enumeration attacks.
    """
    # Find user by email
    user = db.query(User).filter(User.email == request.email).first()

    # Always return success message to prevent email enumeration
    # (don't reveal if email exists or not)
    success_message = {
        "message": "If an account with that email exists, a password reset link has been sent."
    }

    if not user:
        logger.info(f"Password reset requested for non-existent email: {request.email}")
        return success_message

    # Generate secure random token (32 bytes = 64 hex characters)
    reset_token = secrets.token_urlsafe(32)

    # Set token and expiration (1 hour from now)
    user.reset_token = reset_token
    user.reset_token_expires_at = datetime.now(timezone.utc) + timedelta(hours=1)

    try:
        db.commit()

        # Send password reset email
        email_sent = email_service.send_password_reset_email(
            to_email=user.email,
            reset_token=reset_token,
            user_name=user.full_name
        )

        if email_sent:
            logger.info(f"Password reset email sent to {user.email}")
        else:
            logger.error(f"Failed to send password reset email to {user.email}")
            # Don't fail the request if email fails - user can try again

    except Exception as e:
        db.rollback()
        logger.error(f"Error generating password reset token for {request.email}: {e}")
        # Still return success to prevent enumeration

    return success_message


@router.post("/reset-password")
def reset_password(
    request: ResetPasswordRequest,
    db: Session = Depends(get_db)
):
    """
    Reset password using reset token.

    Validates the token and updates the user's password.
    The token must be valid and not expired.
    """
    # Find user by reset token
    user = db.query(User).filter(User.reset_token == request.token).first()

    if not user:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid or expired reset token"
        )

    # Check if token is expired
    if not user.reset_token_expires_at or user.reset_token_expires_at < datetime.now(timezone.utc):
        # Clear expired token
        user.reset_token = None
        user.reset_token_expires_at = None
        db.commit()

        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Reset token has expired. Please request a new password reset."
        )

    # Update password and clear reset token
    user.hashed_password = get_password_hash(request.new_password)
    user.reset_token = None
    user.reset_token_expires_at = None

    try:
        db.commit()
        logger.info(f"Password successfully reset for user: {user.email}")

        return {
            "message": "Password has been reset successfully. You can now login with your new password."
        }

    except Exception as e:
        db.rollback()
        logger.error(f"Error resetting password for user {user.email}: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to reset password. Please try again."
        )
