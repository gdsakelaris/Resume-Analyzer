"""
Authentication endpoints for user registration, login, and token refresh.

Implements JWT-based stateless authentication:
- POST /register: Create new user account
- POST /login: Authenticate and receive JWT tokens
- POST /refresh: Get new access token using refresh token
- GET /me: Get current user profile
"""

import logging
import uuid
from datetime import datetime
from fastapi import APIRouter, HTTPException, Depends, status
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.security import verify_password, get_password_hash, create_access_token, create_refresh_token, decode_token
from app.core.deps import get_current_user
from app.core.config import settings
from app.core.verification import create_verification_code
from app.models.user import User
from app.models.subscription import Subscription, SubscriptionPlan, SubscriptionStatus
from app.schemas.user import (
    UserRegisterRequest,
    UserLoginRequest,
    TokenResponse,
    TokenRefreshRequest,
    UserResponse
)
from app.tasks.email_tasks import send_verification_email_task

router = APIRouter(prefix="/auth", tags=["Authentication"])
logger = logging.getLogger(__name__)


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
    try:
        verification = create_verification_code(db, new_user.id)
        send_verification_email_task.delay(
            to_email=new_user.email,
            verification_code=verification.code,
            user_name=new_user.full_name
        )
        logger.info(f"Verification email queued for {new_user.email}")
    except Exception as e:
        logger.error(f"Failed to queue verification email: {e}")
        # Don't fail registration if email fails - user can request resend

    # Generate JWT tokens
    access_token = create_access_token(data={"sub": str(new_user.id), "tenant_id": str(new_user.tenant_id)})
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
    user.last_login_at = datetime.utcnow()
    db.commit()

    logger.info(f"User logged in: {user.email}")

    # Generate JWT tokens
    access_token = create_access_token(data={"sub": str(user.id), "tenant_id": str(user.tenant_id)})
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
        access_token = create_access_token(data={"sub": str(user.id), "tenant_id": str(user.tenant_id)})
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
