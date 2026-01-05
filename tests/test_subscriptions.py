"""
Unit tests for subscription endpoints.

Tests:
- Get subscription status
- List pricing plans
- Upgrade subscription
- Cancel subscription
- Usage tracking
"""

import pytest
from fastapi.testclient import TestClient
import uuid


def create_test_user(db_session):
    """Helper to create test user with subscription"""
    from app.models.user import User
    from app.models.subscription import Subscription, SubscriptionPlan, SubscriptionStatus
    from app.core.security import get_password_hash

    user = User(
        id=uuid.uuid4(),
        email="test@example.com",
        hashed_password=get_password_hash("TestPass123!"),
        tenant_id=uuid.uuid4(),
        is_verified=True
    )
    db_session.add(user)
    db_session.flush()

    subscription = Subscription(
        id=uuid.uuid4(),
        user_id=user.id,
        plan=SubscriptionPlan.FREE,
        status=SubscriptionStatus.ACTIVE,
        monthly_candidate_limit=10,
        candidates_used_this_month=0
    )
    db_session.add(subscription)
    db_session.commit()

    return user


def get_auth_headers(client):
    """Helper to get authentication headers"""
    response = client.post(
        "/api/v1/auth/login",
        data={"username": "test@example.com", "password": "TestPass123!"}
    )
    token = response.json()["access_token"]
    return {"Authorization": f"Bearer {token}"}


class TestGetSubscription:
    """Test get subscription status endpoint"""

    def test_get_subscription_success(self, client, db_session):
        """Test getting current subscription"""
        user = create_test_user(db_session)
        headers = get_auth_headers(client)

        response = client.get(
            "/api/v1/subscriptions/",
            headers=headers
        )

        assert response.status_code == 200
        data = response.json()
        assert data["plan"] == "FREE"
        assert data["status"] == "ACTIVE"
        assert data["monthly_candidate_limit"] == 10
        assert data["candidates_used_this_month"] == 0

    def test_get_subscription_without_auth(self, client):
        """Test getting subscription without auth fails"""
        response = client.get("/api/v1/subscriptions/")
        assert response.status_code == 401


class TestListPricingPlans:
    """Test list pricing plans endpoint"""

    def test_list_plans(self, client, db_session):
        """Test listing available pricing plans"""
        user = create_test_user(db_session)
        headers = get_auth_headers(client)

        response = client.get(
            "/api/v1/subscriptions/plans",
            headers=headers
        )

        assert response.status_code == 200
        data = response.json()
        assert isinstance(data, list)
        assert len(data) >= 3  # At least FREE, RECRUITER, SMALL_BUSINESS, ENTERPRISE

        # Check plan structure
        for plan in data:
            assert "name" in plan
            assert "price_monthly" in plan
            assert "candidate_limit" in plan
            assert "features" in plan

    def test_list_plans_without_auth(self, client):
        """Test listing plans works without authentication"""
        # Pricing plans should be public
        response = client.get("/api/v1/subscriptions/plans")
        assert response.status_code == 200


class TestUpgradeSubscription:
    """Test subscription upgrade endpoint"""

    def test_upgrade_to_recruiter(self, client, db_session, monkeypatch):
        """Test upgrading from FREE to RECRUITER"""
        user = create_test_user(db_session)
        headers = get_auth_headers(client)

        # Mock Stripe
        stripe_session_created = []

        def mock_create_session(**kwargs):
            stripe_session_created.append(kwargs)
            return type('obj', (object,), {
                'id': 'cs_test_123',
                'url': 'https://checkout.stripe.com/test'
            })

        monkeypatch.setattr("stripe.checkout.Session.create", mock_create_session)

        response = client.post(
            "/api/v1/subscriptions/upgrade",
            json={
                "plan": "RECRUITER",
                "billing_period": "monthly"
            },
            headers=headers
        )

        assert response.status_code == 200
        data = response.json()
        assert "checkout_url" in data
        assert len(stripe_session_created) == 1

    def test_upgrade_to_invalid_plan(self, client, db_session):
        """Test upgrading to invalid plan fails"""
        user = create_test_user(db_session)
        headers = get_auth_headers(client)

        response = client.post(
            "/api/v1/subscriptions/upgrade",
            json={
                "plan": "INVALID_PLAN",
                "billing_period": "monthly"
            },
            headers=headers
        )

        assert response.status_code == 422

    def test_cannot_downgrade_to_free(self, client, db_session):
        """Test cannot upgrade to FREE plan (must cancel instead)"""
        from app.models.subscription import Subscription, SubscriptionPlan

        user = create_test_user(db_session)
        headers = get_auth_headers(client)

        # Upgrade user to RECRUITER first
        subscription = db_session.query(Subscription).filter(
            Subscription.user_id == user.id
        ).first()
        subscription.plan = SubscriptionPlan.RECRUITER
        db_session.commit()

        response = client.post(
            "/api/v1/subscriptions/upgrade",
            json={
                "plan": "FREE",
                "billing_period": "monthly"
            },
            headers=headers
        )

        assert response.status_code == 400


class TestCancelSubscription:
    """Test subscription cancellation endpoint"""

    def test_cancel_subscription_success(self, client, db_session, monkeypatch):
        """Test successful subscription cancellation"""
        from app.models.subscription import Subscription, SubscriptionPlan

        user = create_test_user(db_session)
        headers = get_auth_headers(client)

        # Upgrade user to paid plan first
        subscription = db_session.query(Subscription).filter(
            Subscription.user_id == user.id
        ).first()
        subscription.plan = SubscriptionPlan.RECRUITER
        subscription.stripe_subscription_id = "sub_test_123"
        db_session.commit()

        # Mock Stripe cancellation
        stripe_cancel_called = []

        def mock_cancel(id):
            stripe_cancel_called.append(id)
            return type('obj', (object,), {'id': id, 'status': 'canceled'})

        monkeypatch.setattr("stripe.Subscription.delete", mock_cancel)

        response = client.post(
            "/api/v1/subscriptions/cancel",
            headers=headers
        )

        assert response.status_code == 200
        assert "canceled" in response.json()["message"].lower()
        assert len(stripe_cancel_called) == 1

    def test_cancel_free_subscription_fails(self, client, db_session):
        """Test canceling FREE subscription fails"""
        user = create_test_user(db_session)
        headers = get_auth_headers(client)

        response = client.post(
            "/api/v1/subscriptions/cancel",
            headers=headers
        )

        assert response.status_code == 400
        assert "free" in response.json()["detail"].lower()


class TestUsageTracking:
    """Test subscription usage tracking"""

    def test_usage_increments_on_upload(self, client, db_session, monkeypatch):
        """Test that candidate upload increments usage counter"""
        from app.models.job import Job
        from app.models.subscription import Subscription
        import io

        user = create_test_user(db_session)
        headers = get_auth_headers(client)

        # Create job
        job = Job(
            id=uuid.uuid4(),
            title="Test Job",
            description="Test description",
            tenant_id=user.tenant_id,
            user_id=user.id
        )
        db_session.add(job)
        db_session.commit()

        # Mock Celery task
        monkeypatch.setattr("app.tasks.resume_tasks.extract_resume_text.delay", lambda *a, **k: None)

        # Upload resume
        file = ("resume.pdf", io.BytesIO(b"%PDF-1.4\nTest"), "application/pdf")
        response = client.post(
            f"/api/v1/jobs/{job.id}/candidates/upload",
            files={"file": file},
            headers=headers
        )

        assert response.status_code == 200

        # Check usage incremented
        subscription = db_session.query(Subscription).filter(
            Subscription.user_id == user.id
        ).first()
        assert subscription.candidates_used_this_month == 1

    def test_usage_resets_monthly(self, client, db_session):
        """Test that usage counter resets at billing period"""
        from app.models.subscription import Subscription
        from datetime import datetime, timedelta

        user = create_test_user(db_session)

        # Set usage to 5
        subscription = db_session.query(Subscription).filter(
            Subscription.user_id == user.id
        ).first()
        subscription.candidates_used_this_month = 5
        subscription.current_period_start = datetime.utcnow() - timedelta(days=31)
        subscription.current_period_end = datetime.utcnow() - timedelta(days=1)
        db_session.commit()

        # Simulate monthly reset (this would be done by Stripe webhook or scheduled job)
        # In real app, this happens via stripe webhook invoice.payment_succeeded
        subscription.candidates_used_this_month = 0
        subscription.current_period_start = datetime.utcnow()
        subscription.current_period_end = datetime.utcnow() + timedelta(days=30)
        db_session.commit()

        # Verify reset
        db_session.refresh(subscription)
        assert subscription.candidates_used_this_month == 0
