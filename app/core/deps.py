"""
FastAPI dependencies for authentication and authorization.

These dependencies are used to protect endpoints and extract user context.
"""

from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from jose import JWTError
from sqlalchemy.orm import Session
from typing import Optional
from uuid import UUID

from app.core.database import get_db
from app.core.security import decode_token
from app.models.user import User
from app.models.subscription import Subscription

# HTTP Bearer token scheme (Authorization: Bearer <token>)
security = HTTPBearer()


async def get_current_user(
    credentials: HTTPAuthorizationCredentials = Depends(security),
    db: Session = Depends(get_db)
) -> User:
    """
    Extract and validate the current user from JWT token.

    This dependency:
    1. Extracts the Bearer token from Authorization header
    2. Decodes and validates the JWT
    3. Fetches the user from the database
    4. Ensures the user is active

    Raises:
        HTTPException 401: If token is invalid or user not found
    """
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Could not validate credentials",
        headers={"WWW-Authenticate": "Bearer"},
    )

    try:
        # Decode JWT token
        token = credentials.credentials
        payload = decode_token(token)
        user_id: str = payload.get("sub")
        if user_id is None:
            raise credentials_exception

    except JWTError:
        raise credentials_exception

    # Fetch user from database
    user = db.query(User).filter(User.id == UUID(user_id)).first()
    if user is None:
        raise credentials_exception

    if not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="User account is inactive"
        )

    return user


async def get_verified_user(
    user: User = Depends(get_current_user),
) -> User:
    """
    Get the current user and ensure their email is verified.

    This dependency should be used for ALL protected endpoints that require
    email verification (jobs, candidates, subscriptions, etc.).

    The /auth/me endpoint should continue using get_current_user to allow
    unverified users to access their profile.

    Raises:
        HTTPException 403: If user's email is not verified
    """
    if not user.is_verified:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Email verification required. Please verify your email to access this feature."
        )

    return user


async def get_current_active_subscription(
    user: User = Depends(get_verified_user),
    db: Session = Depends(get_db)
) -> Subscription:
    """
    Get the current user's subscription and verify it's active.

    This dependency enforces billing requirements:
    - User must be verified (email verification)
    - User must have an active subscription (ACTIVE or TRIALING status)
    - Used to protect paid features like candidate uploads

    Raises:
        HTTPException 403: Email not verified
        HTTPException 402: Payment required (subscription inactive)
        HTTPException 404: Subscription not found
    """
    subscription = db.query(Subscription).filter(Subscription.user_id == user.id).first()

    if not subscription:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Subscription not found. Please contact support."
        )

    if not subscription.is_active:
        raise HTTPException(
            status_code=status.HTTP_402_PAYMENT_REQUIRED,
            detail=f"Subscription is {subscription.status.value}. Please update your payment method."
        )

    return subscription


def get_tenant_id(user: User = Depends(get_verified_user)) -> UUID:
    """
    Extract tenant_id from the current verified user.

    This is the core multi-tenancy dependency. All queries must filter by tenant_id
    to prevent cross-tenant data access.

    Requires email verification.

    Usage:
        @router.get("/jobs")
        def list_jobs(tenant_id: UUID = Depends(get_tenant_id), db: Session = Depends(get_db)):
            jobs = db.query(Job).filter(Job.tenant_id == tenant_id).all()

    Raises:
        HTTPException 403: Email not verified
    """
    return user.tenant_id


async def get_optional_user(
    credentials: Optional[HTTPAuthorizationCredentials] = Depends(HTTPBearer(auto_error=False)),
    db: Session = Depends(get_db)
) -> Optional[User]:
    """
    DEVELOPMENT ONLY: Extract user from JWT token if provided, otherwise return None.

    This allows testing the API without authentication while still supporting
    authenticated requests. Remove this in production.

    Returns None if no token provided (unauthenticated access).
    """
    if not credentials:
        return None

    try:
        token = credentials.credentials
        payload = decode_token(token)
        user_id: str = payload.get("sub")
        if user_id is None:
            return None

        user = db.query(User).filter(User.id == UUID(user_id)).first()
        return user if user and user.is_active else None
    except:
        return None


def get_tenant_id_optional(
    user: Optional[User] = Depends(get_optional_user),
    db: Session = Depends(get_db)
) -> Optional[UUID]:
    """
    DEVELOPMENT ONLY: Get tenant_id if authenticated, otherwise use legacy tenant.

    This allows the app to work without authentication by defaulting to the
    legacy user's tenant_id. Remove this in production and require authentication.
    """
    if user:
        return user.tenant_id

    # Fall back to legacy tenant for unauthenticated requests (development only)
    legacy_user = db.query(User).filter(User.email == "legacy@starscreen.internal").first()
    return legacy_user.tenant_id if legacy_user else None
