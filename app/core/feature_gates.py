"""
Feature gates for subscription-based access control.

Controls access to premium features based on subscription tier.
"""

from fastapi import HTTPException, status
from app.models.subscription import Subscription, SubscriptionPlan


def can_use_linkedin_posting(subscription: Subscription) -> bool:
    """
    Check if user's subscription tier allows LinkedIn posting.

    LinkedIn posting is available for:
    - RECRUITER ($20/mo)
    - SMALL_BUSINESS ($149/mo)
    - PROFESSIONAL ($499/mo)
    - ENTERPRISE

    NOT available for FREE tier.

    Args:
        subscription: User's subscription

    Returns:
        bool: True if user can use LinkedIn posting
    """
    return subscription.plan in [
        SubscriptionPlan.RECRUITER,
        SubscriptionPlan.SMALL_BUSINESS,
        SubscriptionPlan.PROFESSIONAL,
        SubscriptionPlan.ENTERPRISE
    ]


def require_linkedin_posting(subscription: Subscription) -> None:
    """
    Raise HTTPException if user cannot use LinkedIn posting.

    Args:
        subscription: User's subscription

    Raises:
        HTTPException: 403 Forbidden if user's plan doesn't support LinkedIn posting
    """
    if not can_use_linkedin_posting(subscription):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=(
                "LinkedIn posting requires a paid subscription. "
                "Upgrade to Recruiter ($20/mo), Small Business ($149/mo), or Professional ($499/mo) plan."
            )
        )


def can_use_job_board_posting(subscription: Subscription, provider: str) -> bool:
    """
    Check if user can post to a specific job board.

    Currently all job boards require the same subscription tier,
    but this function allows for provider-specific gating in the future.

    Args:
        subscription: User's subscription
        provider: Job board provider (e.g., "linkedin", "indeed")

    Returns:
        bool: True if user can post to this provider
    """
    # All job boards require paid subscription
    return can_use_linkedin_posting(subscription)


def require_job_board_posting(subscription: Subscription, provider: str) -> None:
    """
    Raise HTTPException if user cannot post to specified job board.

    Args:
        subscription: User's subscription
        provider: Job board provider (e.g., "linkedin", "indeed")

    Raises:
        HTTPException: 403 Forbidden if user's plan doesn't support this provider
    """
    if not can_use_job_board_posting(subscription, provider):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=(
                f"{provider.capitalize()} job posting requires a paid subscription. "
                "Upgrade to Recruiter ($20/mo) or higher."
            )
        )
