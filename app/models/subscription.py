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

    - INCOMPLETE: Subscription created but payment not completed
    - INCOMPLETE_EXPIRED: Payment was never completed
    - TRIALING: Free trial period (default for new signups)
    - ACTIVE: Paid and in good standing
    - PAST_DUE: Payment failed, grace period active
    - CANCELED: User canceled, access remains until period_end
    - UNPAID: Payment failed multiple times, access revoked
    """
    INCOMPLETE = "incomplete"
    INCOMPLETE_EXPIRED = "incomplete_expired"
    TRIALING = "trialing"
    ACTIVE = "active"
    PAST_DUE = "past_due"
    CANCELED = "canceled"
    UNPAID = "unpaid"


class SubscriptionPlan(str, enum.Enum):
    """
    Available subscription plans with competitive pricing tiers.

    Display Names: Free, Recruiter, Small Business, Professional, Enterprise

    FREE: Trial tier (10 candidates/month) - Perfect for testing
    STARTER (UI: "Recruiter"): Solo recruiters ($20/mo, 100 candidates/month)
    SMALL_BUSINESS: Small teams ($149/mo, 1,000 candidates/month)
    PROFESSIONAL: Large teams ($499/mo, 5,000 candidates/month)
    ENTERPRISE: Reserved for future custom enterprise solutions
    """
    FREE = "free"
    STARTER = "starter"
    SMALL_BUSINESS = "small_business"
    PROFESSIONAL = "professional"
    ENTERPRISE = "enterprise"

    @property
    def display_name(self) -> str:
        """Get the user-facing display name for this plan."""
        names = {
            SubscriptionPlan.FREE: "Free",
            SubscriptionPlan.STARTER: "Recruiter",
            SubscriptionPlan.SMALL_BUSINESS: "Small Business",
            SubscriptionPlan.PROFESSIONAL: "Professional",
            SubscriptionPlan.ENTERPRISE: "Enterprise"
        }
        return names.get(self, "Unknown")

    @property
    def monthly_limit(self) -> int:
        """Get the monthly candidate limit for this plan."""
        from app.core.config import settings

        limits = {
            SubscriptionPlan.FREE: settings.FREE_TIER_CANDIDATE_LIMIT,
            SubscriptionPlan.STARTER: 100,
            SubscriptionPlan.SMALL_BUSINESS: 1000,
            SubscriptionPlan.PROFESSIONAL: 5000,  # Enterprise tier with fixed limit
            SubscriptionPlan.ENTERPRISE: 5000  # Reserved for future use
        }
        return limits.get(self, settings.FREE_TIER_CANDIDATE_LIMIT)

    @property
    def base_price_usd(self) -> int:
        """Get the monthly base price in USD for this plan."""
        prices = {
            SubscriptionPlan.FREE: 0,
            SubscriptionPlan.STARTER: 20,
            SubscriptionPlan.SMALL_BUSINESS: 149,
            SubscriptionPlan.PROFESSIONAL: 499,  # Enterprise tier pricing
            SubscriptionPlan.ENTERPRISE: 499  # Reserved for future use
        }
        return prices.get(self, 0)

    @property
    def per_candidate_price_usd(self) -> float:
        """Get the per-candidate price in USD (reserved for future metered billing)."""
        # No longer using per-candidate pricing
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
    plan = Column(Enum(SubscriptionPlan, values_callable=lambda x: [e.value for e in x]), default=SubscriptionPlan.FREE, nullable=False)
    status = Column(Enum(SubscriptionStatus, values_callable=lambda x: [e.value for e in x]), default=SubscriptionStatus.TRIALING, nullable=False, index=True)

    # Usage limits (enforced by application logic)
    # Note: Default value is set dynamically in registration endpoint based on settings.FREE_TIER_CANDIDATE_LIMIT
    monthly_candidate_limit = Column(Integer, nullable=False)  # Candidate limit based on plan
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
        return min(100.0, (self.candidates_used_this_month / self.monthly_candidate_limit) * 100)

    def sync_plan_limits(self) -> None:
        """Sync monthly_candidate_limit with the plan's default limit."""
        self.monthly_candidate_limit = self.plan.monthly_limit

    def calculate_monthly_cost(self) -> float:
        """
        Calculate total monthly cost based on plan.

        All plans now have fixed monthly pricing.
        """
        return float(self.plan.base_price_usd)

    @property
    def estimated_monthly_cost(self) -> float:
        """Get the estimated cost for the current billing period."""
        return self.calculate_monthly_cost()
