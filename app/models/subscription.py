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
    Available subscription plans with competitive pricing tiers.

    FREE: Trial tier (5 candidates/month) - Perfect for testing
    STARTER: Solo recruiters ($50/mo, 100 candidates/month)
    SMALL_BUSINESS: Small teams ($99/mo, 250 candidates/month)
    PROFESSIONAL: Growing companies ($200/mo, 1000 candidates/month)
    ENTERPRISE: High-volume recruiting ($499/mo base + $0.50 per candidate)
    """
    FREE = "free"
    STARTER = "starter"
    SMALL_BUSINESS = "small_business"
    PROFESSIONAL = "professional"
    ENTERPRISE = "enterprise"

    @property
    def monthly_limit(self) -> int:
        """Get the monthly candidate limit for this plan."""
        limits = {
            SubscriptionPlan.FREE: 5,
            SubscriptionPlan.STARTER: 100,
            SubscriptionPlan.SMALL_BUSINESS: 250,
            SubscriptionPlan.PROFESSIONAL: 1000,
            SubscriptionPlan.ENTERPRISE: 999999  # Unlimited (pay per use)
        }
        return limits.get(self, 5)

    @property
    def base_price_usd(self) -> int:
        """Get the monthly base price in USD for this plan."""
        prices = {
            SubscriptionPlan.FREE: 0,
            SubscriptionPlan.STARTER: 50,
            SubscriptionPlan.SMALL_BUSINESS: 99,
            SubscriptionPlan.PROFESSIONAL: 200,
            SubscriptionPlan.ENTERPRISE: 499  # Base fee + per-candidate pricing
        }
        return prices.get(self, 0)

    @property
    def per_candidate_price_usd(self) -> float:
        """Get the per-candidate price in USD (only for ENTERPRISE)."""
        if self == SubscriptionPlan.ENTERPRISE:
            return 0.50
        return 0.0

    @property
    def price_usd(self) -> int:
        """Legacy property for backwards compatibility. Returns base price."""
        return self.base_price_usd


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

    @property
    def remaining_candidates(self) -> int:
        """Get the number of candidates remaining this month."""
        remaining = self.monthly_candidate_limit - self.candidates_used_this_month
        return max(0, remaining)

    @property
    def usage_percentage(self) -> float:
        """Get the usage percentage for this billing period (0-100)."""
        if self.monthly_candidate_limit == 0:
            return 0.0
        if self.plan == SubscriptionPlan.ENTERPRISE:
            return 0.0  # Unlimited plan
        return min(100.0, (self.candidates_used_this_month / self.monthly_candidate_limit) * 100)

    def sync_plan_limits(self) -> None:
        """Sync monthly_candidate_limit with the plan's default limit."""
        self.monthly_candidate_limit = self.plan.monthly_limit

    def calculate_monthly_cost(self) -> float:
        """
        Calculate total monthly cost based on plan and usage.

        For ENTERPRISE: base_price + (candidates_used * per_candidate_price)
        For other plans: fixed monthly price
        """
        base_cost = self.plan.base_price_usd

        if self.plan == SubscriptionPlan.ENTERPRISE:
            # Enterprise: $499/mo base + $0.50 per candidate
            usage_cost = self.candidates_used_this_month * self.plan.per_candidate_price_usd
            return float(base_cost) + usage_cost

        return float(base_cost)

    @property
    def estimated_monthly_cost(self) -> float:
        """Get the estimated cost for the current billing period."""
        return self.calculate_monthly_cost()
