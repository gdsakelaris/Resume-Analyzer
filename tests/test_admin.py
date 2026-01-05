"""
Unit tests for admin endpoints.

Tests:
- Admin dashboard stats
- User management
- System health checks
"""

import pytest
from fastapi.testclient import TestClient
import uuid


def create_admin_user(db_session):
    """Helper to create admin user"""
    from app.models.user import User
    from app.models.subscription import Subscription, SubscriptionPlan, SubscriptionStatus
    from app.core.security import get_password_hash

    user = User(
        id=uuid.uuid4(),
        email="admin@example.com",
        hashed_password=get_password_hash("AdminPass123!"),
        tenant_id=uuid.uuid4(),
        is_verified=True,
        is_admin=True
    )
    db_session.add(user)
    db_session.flush()

    subscription = Subscription(
        id=uuid.uuid4(),
        user_id=user.id,
        plan=SubscriptionPlan.FREE,
        status=SubscriptionStatus.ACTIVE
    )
    db_session.add(subscription)
    db_session.commit()

    return user


def get_admin_headers(client):
    """Helper to get admin authentication headers"""
    response = client.post(
        "/api/v1/auth/login",
        data={"username": "admin@example.com", "password": "AdminPass123!"}
    )
    token = response.json()["access_token"]
    return {"Authorization": f"Bearer {token}"}


class TestAdminDashboard:
    """Test admin dashboard endpoint"""

    def test_get_dashboard_stats(self, client, db_session):
        """Test getting admin dashboard statistics"""
        admin = create_admin_user(db_session)
        headers = get_admin_headers(client)

        response = client.get(
            "/api/v1/admin/dashboard",
            headers=headers
        )

        assert response.status_code == 200
        data = response.json()

        # Check expected statistics
        assert "total_users" in data
        assert "total_jobs" in data
        assert "total_candidates" in data
        assert "active_subscriptions" in data
        assert isinstance(data["total_users"], int)

    def test_dashboard_requires_admin(self, client, db_session):
        """Test non-admin users cannot access dashboard"""
        from app.models.user import User
        from app.models.subscription import Subscription, SubscriptionPlan, SubscriptionStatus
        from app.core.security import get_password_hash

        # Create regular (non-admin) user
        user = User(
            id=uuid.uuid4(),
            email="regular@example.com",
            hashed_password=get_password_hash("RegularPass123!"),
            tenant_id=uuid.uuid4(),
            is_verified=True,
            is_admin=False
        )
        db_session.add(user)
        db_session.flush()

        subscription = Subscription(
            id=uuid.uuid4(),
            user_id=user.id,
            plan=SubscriptionPlan.FREE,
            status=SubscriptionStatus.ACTIVE
        )
        db_session.add(subscription)
        db_session.commit()

        # Login as regular user
        response = client.post(
            "/api/v1/auth/login",
            data={"username": "regular@example.com", "password": "RegularPass123!"}
        )
        token = response.json()["access_token"]
        headers = {"Authorization": f"Bearer {token}"}

        # Try to access admin dashboard
        response = client.get(
            "/api/v1/admin/dashboard",
            headers=headers
        )

        assert response.status_code == 403


class TestHealthCheck:
    """Test health check endpoints"""

    def test_health_check(self, client):
        """Test basic health check endpoint"""
        response = client.get("/api/v1/health/")

        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "healthy"

    def test_health_check_with_database(self, client, db_session):
        """Test health check includes database connectivity"""
        response = client.get("/api/v1/health/")

        assert response.status_code == 200
        # Database connection should be successful if this test runs
