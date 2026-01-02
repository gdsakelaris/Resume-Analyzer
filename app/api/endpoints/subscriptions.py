"""
API endpoints for subscription management.

Handles subscription creation, upgrades, downgrades, and billing portal access.
"""

import logging
import stripe
from datetime import datetime
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
    3. Creates a Stripe subscription (charges immediately)
    4. Updates the local subscription record

    Returns subscription details.
    """
    try:
        logger.info(f"Creating subscription for user {current_user.id}, tier: {request.tier}, payment_method: {request.payment_method_id}")

        # Validate payment method ID
        if not request.payment_method_id:
            raise HTTPException(status_code=400, detail="Payment method ID is required")

        # Get user's subscription
        subscription = db.query(Subscription).filter(
            Subscription.user_id == current_user.id
        ).first()

        if not subscription:
            raise HTTPException(status_code=404, detail="No subscription found for user")

        # Check if already has active PAID subscription (allow upgrading from FREE)
        if subscription.status == SubscriptionStatus.ACTIVE and subscription.plan != SubscriptionPlan.FREE:
            # User has a paid subscription - cancel it first
            if subscription.stripe_subscription_id:
                try:
                    # Cancel the current Stripe subscription
                    stripe.Subscription.delete(subscription.stripe_subscription_id)
                    logger.info(f"Cancelled existing subscription {subscription.stripe_subscription_id} for user {current_user.id}")
                except stripe.error.StripeError as e:
                    logger.error(f"Failed to cancel existing subscription: {e}")
                    raise HTTPException(
                        status_code=400,
                        detail=f"Failed to cancel existing subscription: {str(e)}"
                    )

        # Map tier to Stripe price ID and limits
        tier_mapping = {
            "STARTER": {
                "price_id": settings.STRIPE_PRICE_ID_RECRUITER_MONTHLY,
                "limit": 100,
                "plan": SubscriptionPlan.STARTER
            },
            "SMALL_BUSINESS": {
                "price_id": settings.STRIPE_PRICE_ID_SMALL_BUSINESS_MONTHLY,
                "limit": 1000,
                "plan": SubscriptionPlan.SMALL_BUSINESS
            },
            "PROFESSIONAL": {
                "price_id": settings.STRIPE_PRICE_ID_ENTERPRISE_MONTHLY,
                "limit": 5000,  # Enterprise tier with fixed limit
                "plan": SubscriptionPlan.PROFESSIONAL
            }
        }

        tier_config = tier_mapping.get(request.tier.upper())
        if not tier_config:
            raise HTTPException(status_code=400, detail=f"Invalid tier: {request.tier}")

        # Validate price_id is set
        if not tier_config['price_id']:
            logger.error(f"Stripe price ID for tier {request.tier} is not configured! Check environment variables.")
            raise HTTPException(status_code=500, detail=f"Stripe price ID not configured for {request.tier}")

        logger.info(f"Using Stripe price ID: {tier_config['price_id']}")

        # Ensure Stripe API key is set
        if not stripe.api_key:
            logger.error("Stripe API key is not set!")
            stripe.api_key = settings.STRIPE_API_KEY
            logger.info(f"Stripe API key set: {stripe.api_key[:20] if stripe.api_key else 'NONE'}...")

        # Create or retrieve Stripe customer
        if not subscription.stripe_customer_id:
            logger.info(f"Creating new Stripe customer for {current_user.email}")
            try:
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
                logger.info(f"Stripe customer object type: {type(customer)}")
                logger.info(f"Stripe customer object: {customer}")
                logger.info(f"Attempting to access customer.id...")
                customer_id = customer.id
                logger.info(f"Successfully accessed customer ID: {customer_id}")
                subscription.stripe_customer_id = customer_id
                logger.info(f"Successfully saved customer ID to subscription")
            except Exception as e:
                logger.error(f"Error in customer creation flow: {type(e).__name__}: {str(e)}")
                logger.error(f"Stripe API key status: {stripe.api_key[:20] if stripe.api_key else 'NONE'}...")
                import traceback
                logger.error(f"Full traceback: {traceback.format_exc()}")
                raise
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

        # Create Stripe subscription (no trial - charge immediately)
        try:
            logger.info(f"Creating Stripe subscription with price: {tier_config['price_id']}, customer: {subscription.stripe_customer_id}")
            stripe_subscription = stripe.Subscription.create(
                customer=subscription.stripe_customer_id,
                items=[{
                    'price': tier_config['price_id'],
                }],
                metadata={
                    'user_id': str(current_user.id),
                    'tenant_id': str(current_user.tenant_id),
                    'plan': request.tier
                }
            )
            logger.info(f"Stripe subscription created successfully: {stripe_subscription.id}")
        except Exception as e:
            logger.error(f"Failed to create Stripe subscription: {type(e).__name__}: {str(e)}")
            raise

        # Update local subscription record
        subscription.stripe_subscription_id = stripe_subscription.id
        subscription.plan = tier_config['plan']
        subscription.status = SubscriptionStatus.ACTIVE
        subscription.monthly_candidate_limit = tier_config['limit']
        # Convert Unix timestamps to datetime objects
        subscription.current_period_start = datetime.fromtimestamp(stripe_subscription.current_period_start)
        subscription.current_period_end = datetime.fromtimestamp(stripe_subscription.current_period_end)

        db.commit()
        db.refresh(subscription)

        logger.info(f"Created subscription for user {current_user.id}: {request.tier}")

        return {
            "subscription_id": stripe_subscription.id,
            "status": subscription.status.value,
            "plan": subscription.plan.value,
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
        "STARTER": settings.STRIPE_PRICE_ID_RECRUITER_MONTHLY,
        "SMALL_BUSINESS": settings.STRIPE_PRICE_ID_SMALL_BUSINESS_MONTHLY,
        "PROFESSIONAL": settings.STRIPE_PRICE_ID_ENTERPRISE_MONTHLY
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
