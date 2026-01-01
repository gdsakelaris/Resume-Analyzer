"""
Stripe webhook handler for subscription lifecycle events.

Listens to Stripe webhooks to keep subscription status in sync:
- payment_intent.succeeded -> Update subscription status to ACTIVE
- customer.subscription.updated -> Update subscription details
- customer.subscription.deleted -> Set status to CANCELED
"""

import logging
import stripe
from fastapi import APIRouter, Request, HTTPException, Depends, Header
from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.database import get_db
from app.models.subscription import Subscription, SubscriptionStatus, SubscriptionPlan

router = APIRouter(prefix="/webhooks", tags=["Stripe Webhooks"])
logger = logging.getLogger(__name__)

# Initialize Stripe with API key
stripe.api_key = settings.STRIPE_API_KEY


@router.post("/stripe")
async def stripe_webhook(
    request: Request,
    db: Session = Depends(get_db),
    stripe_signature: str = Header(None, alias="stripe-signature")
):
    """
    Handle Stripe webhook events.

    This endpoint is called by Stripe when subscription events occur:
    - customer.subscription.created
    - customer.subscription.updated
    - customer.subscription.deleted
    - invoice.payment_succeeded
    - invoice.payment_failed

    Security: Validates webhook signature using STRIPE_WEBHOOK_SECRET.
    """
    if not stripe_signature:
        raise HTTPException(status_code=400, detail="Missing Stripe signature")

    # Get raw request body for signature verification
    payload = await request.body()

    try:
        # Verify webhook signature
        event = stripe.Webhook.construct_event(
            payload, stripe_signature, settings.STRIPE_WEBHOOK_SECRET
        )
    except ValueError:
        logger.error("Invalid webhook payload")
        raise HTTPException(status_code=400, detail="Invalid payload")
    except stripe.error.SignatureVerificationError:
        logger.error("Invalid webhook signature")
        raise HTTPException(status_code=400, detail="Invalid signature")

    # Handle the event
    event_type = event["type"]
    data = event["data"]["object"]

    logger.info(f"Received Stripe webhook: {event_type}")

    try:
        if event_type == "customer.subscription.created":
            handle_subscription_created(db, data)
        elif event_type == "customer.subscription.updated":
            handle_subscription_updated(db, data)
        elif event_type == "customer.subscription.deleted":
            handle_subscription_deleted(db, data)
        elif event_type == "invoice.payment_succeeded":
            handle_payment_succeeded(db, data)
        elif event_type == "invoice.payment_failed":
            handle_payment_failed(db, data)
        else:
            logger.info(f"Unhandled event type: {event_type}")

        return {"status": "success"}

    except Exception as e:
        logger.error(f"Error processing webhook {event_type}: {e}")
        raise HTTPException(status_code=500, detail=f"Webhook processing failed: {str(e)}")


def handle_subscription_created(db: Session, stripe_sub: dict):
    """Handle new subscription creation from Stripe."""
    stripe_customer_id = stripe_sub["customer"]
    stripe_subscription_id = stripe_sub["id"]

    # Find user by Stripe customer ID
    subscription = db.query(Subscription).filter(
        Subscription.stripe_customer_id == stripe_customer_id
    ).first()

    if not subscription:
        logger.warning(f"No subscription found for Stripe customer {stripe_customer_id}")
        return

    # Update subscription with Stripe details
    subscription.stripe_subscription_id = stripe_subscription_id
    subscription.status = SubscriptionStatus(stripe_sub["status"])
    subscription.current_period_start = stripe_sub.get("current_period_start")
    subscription.current_period_end = stripe_sub.get("current_period_end")

    # Map Stripe price ID to plan and limits (same as subscriptions.py)
    price_id = stripe_sub["items"]["data"][0]["price"]["id"]
    tier_mapping = {
        settings.STRIPE_PRICE_ID_RECRUITER_MONTHLY: {
            "plan": SubscriptionPlan.STARTER,
            "limit": 100
        },
        settings.STRIPE_PRICE_ID_SMALL_BUSINESS_MONTHLY: {
            "plan": SubscriptionPlan.SMALL_BUSINESS,
            "limit": 1000
        },
        settings.STRIPE_PRICE_ID_ENTERPRISE_MONTHLY: {
            "plan": SubscriptionPlan.PROFESSIONAL,
            "limit": 999999  # Unlimited
        }
    }

    tier_config = tier_mapping.get(price_id)
    if tier_config:
        subscription.plan = tier_config["plan"]
        subscription.monthly_candidate_limit = tier_config["limit"]
        logger.info(f"Mapped price {price_id} to plan {tier_config['plan'].value} with limit {tier_config['limit']}")
    else:
        logger.warning(f"Unknown Stripe price ID: {price_id}")

    db.commit()
    logger.info(f"Subscription created for customer {stripe_customer_id}")


def handle_subscription_updated(db: Session, stripe_sub: dict):
    """Handle subscription updates (plan changes, renewals)."""
    stripe_subscription_id = stripe_sub["id"]

    subscription = db.query(Subscription).filter(
        Subscription.stripe_subscription_id == stripe_subscription_id
    ).first()

    if not subscription:
        logger.warning(f"No subscription found for Stripe subscription {stripe_subscription_id}")
        return

    # Update subscription status
    subscription.status = SubscriptionStatus(stripe_sub["status"])
    subscription.current_period_start = stripe_sub.get("current_period_start")
    subscription.current_period_end = stripe_sub.get("current_period_end")

    # Check for plan changes (use same tier mapping as subscription creation)
    price_id = stripe_sub["items"]["data"][0]["price"]["id"]
    tier_mapping = {
        settings.STRIPE_PRICE_ID_RECRUITER_MONTHLY: {
            "plan": SubscriptionPlan.STARTER,
            "limit": 100
        },
        settings.STRIPE_PRICE_ID_SMALL_BUSINESS_MONTHLY: {
            "plan": SubscriptionPlan.SMALL_BUSINESS,
            "limit": 1000
        },
        settings.STRIPE_PRICE_ID_ENTERPRISE_MONTHLY: {
            "plan": SubscriptionPlan.PROFESSIONAL,
            "limit": 999999  # Unlimited
        }
    }

    tier_config = tier_mapping.get(price_id)
    if tier_config:
        subscription.plan = tier_config["plan"]
        subscription.monthly_candidate_limit = tier_config["limit"]
        logger.info(f"Updated to plan {tier_config['plan'].value} with limit {tier_config['limit']}")
    else:
        logger.warning(f"Unknown Stripe price ID during update: {price_id}")

    db.commit()
    logger.info(f"Subscription updated: {stripe_subscription_id} -> {subscription.status.value}")


def handle_subscription_deleted(db: Session, stripe_sub: dict):
    """Handle subscription cancellation."""
    stripe_subscription_id = stripe_sub["id"]

    subscription = db.query(Subscription).filter(
        Subscription.stripe_subscription_id == stripe_subscription_id
    ).first()

    if not subscription:
        logger.warning(f"No subscription found for Stripe subscription {stripe_subscription_id}")
        return

    subscription.status = SubscriptionStatus.CANCELED
    db.commit()
    logger.info(f"Subscription canceled: {stripe_subscription_id}")


def handle_payment_succeeded(db: Session, invoice: dict):
    """Handle successful payment (reactivate subscription if needed)."""
    stripe_subscription_id = invoice.get("subscription")

    if not stripe_subscription_id:
        return

    subscription = db.query(Subscription).filter(
        Subscription.stripe_subscription_id == stripe_subscription_id
    ).first()

    if not subscription:
        return

    # Reactivate subscription on successful payment
    subscription.status = SubscriptionStatus.ACTIVE

    # Reset monthly usage on new billing period
    subscription.candidates_used_this_month = 0

    db.commit()
    logger.info(f"Payment succeeded for subscription {stripe_subscription_id}")


def handle_payment_failed(db: Session, invoice: dict):
    """Handle failed payment."""
    stripe_subscription_id = invoice.get("subscription")

    if not stripe_subscription_id:
        return

    subscription = db.query(Subscription).filter(
        Subscription.stripe_subscription_id == stripe_subscription_id
    ).first()

    if not subscription:
        return

    # Mark subscription as past due
    subscription.status = SubscriptionStatus.PAST_DUE

    db.commit()
    logger.warning(f"Payment failed for subscription {stripe_subscription_id}")
