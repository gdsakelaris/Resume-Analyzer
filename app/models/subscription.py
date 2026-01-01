"""
Subscription model for Stripe billing integration.

Tracks user subscription status and limits. Integrated with Stripe webhooks
to automatically update subscription status when payment succeeds/fails.
"""

import enum
from sqlalchemy import Column, String, Integer, DateTime, Enum, ForeignKey, func
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship
from app.core.database import Base


class SubscriptionStatus(str, enum.Enum):
    """
    Subscription lifecycle states (mirrors Stripe subscription statuses).

    - TRIALING: Free trial period (default for new signups)
    - ACTIVE: Paid and in good standing
    - PAST_DUE: Payment failed, grace period active
    - CANCELED: User canceled, access remains until period_end
    - UNPAID: Payment failed multiple times, access revoked
    """
    TRIALING = "trialing"
    ACTIVE = "active"
    PAST_DUE = "past_due"
    CANCELED = "canceled"
    UNPAID = "unpaid"


class SubscriptionPlan(str, enum.Enum):
    """
    Available subscription plans.

    FREE: Limited trial (e.g., 5 candidates per month)
    STARTER: Small teams ($49/mo, 50 candidates)
    PROFESSIONAL: Growing companies ($149/mo, 200 candidates)
    ENTERPRISE: Custom pricing, unlimited
    """
    FREE = "free"
    STARTER = "starter"
    PROFESSIONAL = "professional"
    ENTERPRISE = "enterprise"


class Subscription(Base):
    """
    User subscription record synced with Stripe.

    Updated via Stripe webhooks when:
    - Payment succeeds (status -> ACTIVE)
    - Payment fails (status -> PAST_DUE)
    - Subscription canceled (status -> CANCELED)
    """
    __tablename__ = "subscriptions"

    id = Column(UUID(as_uuid=True), primary_key=True, index=True)
    user_id = Column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=False, unique=True, index=True)

    # Stripe integration
    stripe_customer_id = Column(String, nullable=True, unique=True, index=True)
    stripe_subscription_id = Column(String, nullable=True, unique=True, index=True)

    # Subscription details
    plan = Column(Enum(SubscriptionPlan), default=SubscriptionPlan.FREE, nullable=False)
    status = Column(Enum(SubscriptionStatus), default=SubscriptionStatus.TRIALING, nullable=False, index=True)

    # Usage limits (enforced by application logic)
    monthly_candidate_limit = Column(Integer, default=5, nullable=False)  # Free tier: 5 candidates/month
    candidates_used_this_month = Column(Integer, default=0, nullable=False)

    # Billing cycle
    current_period_start = Column(DateTime(timezone=True), nullable=True)
    current_period_end = Column(DateTime(timezone=True), nullable=True)

    # Timestamps
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())

    # Relationships
    user = relationship("User", back_populates="subscription")

    def __repr__(self):
        return f"<Subscription(user_id={self.user_id}, plan={self.plan.value}, status={self.status.value})>"

    @property
    def is_active(self) -> bool:
        """Check if subscription allows access to paid features."""
        return self.status in [SubscriptionStatus.ACTIVE, SubscriptionStatus.TRIALING]

    @property
    def can_upload_candidate(self) -> bool:
        """Check if user can upload another candidate this month."""
        if self.plan == SubscriptionPlan.ENTERPRISE:
            return True
        return self.is_active and self.candidates_used_this_month < self.monthly_candidate_limit
