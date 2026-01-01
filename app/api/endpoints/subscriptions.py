"""
API endpoints for subscription management.

Handles subscription creation, upgrades, downgrades, and billing portal access.
"""

import logging
import stripe
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from pydantic import BaseModel
from typing import Optional

from app.core.config import settings
from app.core.database import get_db
from app.core.deps import get_current_user
from app.models.subscription import Subscription, SubscriptionPlan, SubscriptionStatus
from app.models.user import User

router = APIRouter(prefix="/subscriptions", tags=["Subscriptions"])
logger = logging.getLogger(__name__)

# Initialize Stripe
stripe.api_key = settings.STRIPE_API_KEY


class CreateSubscriptionRequest(BaseModel):
    """Request model for creating a subscription"""
    tier: str  # STARTER, SMALL_BUSINESS, PROFESSIONAL
    billing_period: str = "monthly"  # monthly or annual
    payment_method_id: str


class SubscriptionResponse(BaseModel):
    """Response model for subscription info"""
    plan: str
    status: str
    monthly_candidate_limit: int
    candidates_used_this_month: int
    remaining_candidates: int
    current_period_end: Optional[int]


@router.post("/create")
async def create_subscription(
    request: CreateSubscriptionRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Create a new Stripe subscription for the current user.

    This creates:
    1. A Stripe customer (if doesn't exist)
    2. Attaches the payment method
    3. Creates a Stripe subscription with trial period
    4. Updates the local subscription record

    Returns subscription details.
    """
    try:
        # Get user's subscription
        subscription = db.query(Subscription).filter(
            Subscription.user_id == current_user.id
        ).first()

        if not subscription:
            raise HTTPException(status_code=404, detail="No subscription found for user")

        # Check if already has active subscription
        if subscription.status == SubscriptionStatus.ACTIVE:
            raise HTTPException(
                status_code=400,
                detail="User already has an active subscription"
            )

        # Map tier to Stripe price ID and limits
        tier_mapping = {
            "STARTER": {
                "price_id": settings.STRIPE_PRICE_ID_STARTER,
                "limit": 100,
                "plan": SubscriptionPlan.STARTER
            },
            "SMALL_BUSINESS": {
                "price_id": settings.STRIPE_PRICE_ID_SMALL_BUSINESS,
                "limit": 250,
                "plan": SubscriptionPlan.SMALL_BUSINESS
            },
            "PROFESSIONAL": {
                "price_id": settings.STRIPE_PRICE_ID_PROFESSIONAL,
                "limit": 1000,
                "plan": SubscriptionPlan.PROFESSIONAL
            }
        }

        tier_config = tier_mapping.get(request.tier.upper())
        if not tier_config:
            raise HTTPException(status_code=400, detail=f"Invalid tier: {request.tier}")

        # Create or retrieve Stripe customer
        if not subscription.stripe_customer_id:
            customer = stripe.Customer.create(
                email=current_user.email,
                payment_method=request.payment_method_id,
                invoice_settings={
                    'default_payment_method': request.payment_method_id,
                },
                metadata={
                    'user_id': str(current_user.id),
                    'tenant_id': str(current_user.tenant_id)
                }
            )
            subscription.stripe_customer_id = customer.id
        else:
            # Attach payment method to existing customer
            stripe.PaymentMethod.attach(
                request.payment_method_id,
                customer=subscription.stripe_customer_id,
            )

            # Set as default payment method
            stripe.Customer.modify(
                subscription.stripe_customer_id,
                invoice_settings={
                    'default_payment_method': request.payment_method_id,
                },
            )

        # Create Stripe subscription with 14-day trial
        stripe_subscription = stripe.Subscription.create(
            customer=subscription.stripe_customer_id,
            items=[{
                'price': tier_config['price_id'],
            }],
            trial_period_days=14,
            metadata={
                'user_id': str(current_user.id),
                'tenant_id': str(current_user.tenant_id),
                'plan': request.tier
            }
        )

        # Update local subscription record
        subscription.stripe_subscription_id = stripe_subscription.id
        subscription.plan = tier_config['plan']
        subscription.status = SubscriptionStatus.TRIALING
        subscription.monthly_candidate_limit = tier_config['limit']
        subscription.current_period_start = stripe_subscription.current_period_start
        subscription.current_period_end = stripe_subscription.current_period_end

        db.commit()
        db.refresh(subscription)

        logger.info(f"Created subscription for user {current_user.id}: {request.tier}")

        return {
            "subscription_id": stripe_subscription.id,
            "status": subscription.status.value,
            "plan": subscription.plan.value,
            "trial_end": stripe_subscription.trial_end,
            "monthly_candidate_limit": subscription.monthly_candidate_limit
        }

    except stripe.error.StripeError as e:
        logger.error(f"Stripe error creating subscription: {e}")
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        logger.error(f"Error creating subscription: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to create subscription: {str(e)}")


@router.get("/current", response_model=SubscriptionResponse)
async def get_current_subscription(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Get the current user's subscription details.
    """
    subscription = db.query(Subscription).filter(
        Subscription.user_id == current_user.id
    ).first()

    if not subscription:
        raise HTTPException(status_code=404, detail="No subscription found")

    return {
        "plan": subscription.plan.value,
        "status": subscription.status.value,
        "monthly_candidate_limit": subscription.monthly_candidate_limit,
        "candidates_used_this_month": subscription.candidates_used_this_month,
        "remaining_candidates": subscription.remaining_candidates,
        "current_period_end": subscription.current_period_end
    }


@router.post("/portal")
async def create_billing_portal_session(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Create a Stripe billing portal session for the user to manage their subscription.

    Returns a URL to redirect the user to the Stripe Customer Portal where they can:
    - Update payment method
    - View invoices
    - Cancel subscription
    - Upgrade/downgrade plan
    """
    subscription = db.query(Subscription).filter(
        Subscription.user_id == current_user.id
    ).first()

    if not subscription or not subscription.stripe_customer_id:
        raise HTTPException(
            status_code=404,
            detail="No subscription found. Please subscribe first."
        )

    try:
        # Create billing portal session
        session = stripe.billing_portal.Session.create(
            customer=subscription.stripe_customer_id,
            return_url=f"{settings.FRONTEND_URL}/?billing=success",
        )

        return {"url": session.url}

    except stripe.error.StripeError as e:
        logger.error(f"Stripe error creating portal session: {e}")
        raise HTTPException(status_code=400, detail=str(e))


@router.post("/cancel")
async def cancel_subscription(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Cancel the current user's subscription.
    Subscription remains active until the end of the billing period.
    """
    subscription = db.query(Subscription).filter(
        Subscription.user_id == current_user.id
    ).first()

    if not subscription or not subscription.stripe_subscription_id:
        raise HTTPException(status_code=404, detail="No active subscription found")

    try:
        # Cancel at period end (don't cancel immediately)
        stripe_subscription = stripe.Subscription.modify(
            subscription.stripe_subscription_id,
            cancel_at_period_end=True
        )

        logger.info(f"Canceled subscription for user {current_user.id}")

        return {
            "message": "Subscription will be canceled at the end of the billing period",
            "cancel_at": stripe_subscription.cancel_at
        }

    except stripe.error.StripeError as e:
        logger.error(f"Stripe error canceling subscription: {e}")
        raise HTTPException(status_code=400, detail=str(e))


@router.post("/upgrade")
async def upgrade_subscription(
    new_tier: str,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Upgrade (or downgrade) the current subscription to a new tier.
    Changes take effect immediately and are prorated.
    """
    subscription = db.query(Subscription).filter(
        Subscription.user_id == current_user.id
    ).first()

    if not subscription or not subscription.stripe_subscription_id:
        raise HTTPException(status_code=404, detail="No active subscription found")

    # Map tier to price ID
    tier_mapping = {
        "STARTER": settings.STRIPE_PRICE_ID_STARTER,
        "SMALL_BUSINESS": settings.STRIPE_PRICE_ID_SMALL_BUSINESS,
        "PROFESSIONAL": settings.STRIPE_PRICE_ID_PROFESSIONAL
    }

    new_price_id = tier_mapping.get(new_tier.upper())
    if not new_price_id:
        raise HTTPException(status_code=400, detail=f"Invalid tier: {new_tier}")

    try:
        # Get current subscription from Stripe
        stripe_sub = stripe.Subscription.retrieve(subscription.stripe_subscription_id)

        # Update subscription item with new price
        stripe.Subscription.modify(
            subscription.stripe_subscription_id,
            items=[{
                'id': stripe_sub['items']['data'][0].id,
                'price': new_price_id,
            }],
            proration_behavior='always_invoice',
        )

        logger.info(f"Upgraded subscription for user {current_user.id} to {new_tier}")

        return {
            "message": f"Successfully upgraded to {new_tier}",
            "status": "active"
        }

    except stripe.error.StripeError as e:
        logger.error(f"Stripe error upgrading subscription: {e}")
        raise HTTPException(status_code=400, detail=str(e))
