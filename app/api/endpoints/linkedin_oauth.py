"""
LinkedIn OAuth 2.0 flow endpoints.

Handles authorization redirect and callback for LinkedIn integration.
"""

import logging
from fastapi import APIRouter, HTTPException, Depends, Query, status
from sqlalchemy.orm import Session
from app.core.database import get_db
from app.core.deps import get_verified_user, get_current_active_subscription
from app.core.feature_gates import require_linkedin_posting
from app.models.user import User
from app.models.subscription import Subscription
from app.services.linkedin_service import linkedin_service
from app.crud import oauth_connection as oauth_crud

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/linkedin", tags=["LinkedIn Integration"])


@router.get("/auth/initiate")
async def initiate_linkedin_oauth(
    user: User = Depends(get_verified_user),
    subscription: Subscription = Depends(get_current_active_subscription),
    db: Session = Depends(get_db)
):
    """
    Step 1: Initiate LinkedIn OAuth flow.

    Requirements:
    - User must have verified email
    - User must have paid subscription (RECRUITER, SMALL_BUSINESS, PROFESSIONAL, ENTERPRISE)

    Returns:
        dict: Contains authorization_url to redirect user to LinkedIn
    """
    # Check subscription tier (FREE tier not allowed)
    require_linkedin_posting(subscription)

    # Generate authorization URL with state parameter (CSRF protection)
    auth_url, state = linkedin_service.get_authorization_url(str(user.id))

    # Store state in Redis for validation (15-min expiry, single-use)
    await linkedin_service.store_oauth_state(str(user.id), state)

    return {
        "authorization_url": auth_url,
        "message": "Redirect user to this URL to authorize LinkedIn access"
    }


@router.get("/auth/callback")
async def linkedin_oauth_callback(
    code: str = Query(..., description="Authorization code from LinkedIn"),
    state: str = Query(..., description="State parameter for CSRF protection"),
    user: User = Depends(get_verified_user),
    db: Session = Depends(get_db)
):
    """
    Step 2: Handle OAuth callback from LinkedIn.

    LinkedIn redirects here after user authorizes the app.
    Exchanges authorization code for access token.

    Args:
        code: Authorization code from LinkedIn
        state: State parameter for CSRF validation
        user: Current authenticated user
        db: Database session

    Returns:
        dict: Success message

    Raises:
        HTTPException: If state validation fails or token exchange fails
    """
    # Validate state parameter (CSRF protection)
    is_valid_state = await linkedin_service.validate_oauth_state(str(user.id), state)
    if not is_valid_state:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid state parameter. Please try connecting LinkedIn again."
        )

    try:
        # Exchange code for access token
        token_data = await linkedin_service.exchange_code_for_token(code)

        # Store OAuth connection in database
        oauth_crud.create_or_update_connection(
            db=db,
            user_id=user.id,
            tenant_id=user.tenant_id,
            provider="linkedin",
            access_token=token_data["access_token"],
            refresh_token=token_data.get("refresh_token"),
            expires_in=token_data.get("expires_in")
        )

        logger.info(f"LinkedIn account connected successfully for user {user.id}")

        return {
            "success": True,
            "message": "LinkedIn account connected successfully!"
        }

    except Exception as e:
        logger.error(f"LinkedIn OAuth error for user {user.id}: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to connect LinkedIn account: {str(e)}"
        )


@router.get("/status")
async def get_linkedin_connection_status(
    user: User = Depends(get_verified_user),
    db: Session = Depends(get_db)
):
    """
    Get LinkedIn connection status for current user.

    Returns:
        dict: Connection status with connected flag and metadata
    """
    connection = oauth_crud.get_connection(db, user.id, "linkedin")

    if not connection or not connection.is_active:
        return {
            "connected": False,
            "message": "No active LinkedIn connection"
        }

    return {
        "connected": True,
        "connected_at": connection.created_at,
        "last_refresh_at": connection.last_refresh_at,
        "requires_refresh": linkedin_service.is_token_expired(connection)
    }


@router.delete("/disconnect")
async def disconnect_linkedin(
    user: User = Depends(get_verified_user),
    db: Session = Depends(get_db)
):
    """
    Disconnect LinkedIn account (soft delete).

    Marks the OAuth connection as inactive.
    User will need to reconnect to post jobs to LinkedIn.

    Returns:
        dict: Success message
    """
    success = oauth_crud.delete_connection(db, user.id, "linkedin")

    if not success:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="No LinkedIn connection found"
        )

    logger.info(f"LinkedIn account disconnected for user {user.id}")

    return {
        "success": True,
        "message": "LinkedIn account disconnected successfully"
    }
