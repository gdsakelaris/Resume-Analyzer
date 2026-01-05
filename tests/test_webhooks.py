"""
Unit tests for webhook endpoints.

Tests:
- Stripe webhooks (subscription lifecycle)
- Resend webhooks (incoming support emails)
"""

import pytest
from fastapi.testclient import TestClient
import uuid
import json


class TestStripeWebhooks:
    """Test Stripe webhook handling"""

    def test_subscription_created_webhook(self, client, db_session):
        """Test handling subscription.created webhook"""
        from app.models.user import User
        from app.models.subscription import Subscription, SubscriptionPlan, SubscriptionStatus
        from app.core.security import get_password_hash

        # Create user with FREE subscription
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
            stripe_customer_id="cus_test_123"
        )
        db_session.add(subscription)
        db_session.commit()

        # Simulate Stripe webhook payload
        webhook_payload = {
            "type": "customer.subscription.created",
            "data": {
                "object": {
                    "id": "sub_test_123",
                    "customer": "cus_test_123",
                    "status": "active",
                    "current_period_start": 1704067200,
                    "current_period_end": 1706745600,
                    "items": {
                        "data": [{
                            "price": {
                                "id": "price_recruiter_monthly"
                            }
                        }]
                    }
                }
            }
        }

        # Note: In real tests, you'd need to mock Stripe signature verification
        # For now, we'll test the handler function directly
        from app.api.endpoints.stripe_webhooks import handle_subscription_created

        handle_subscription_created(db_session, webhook_payload["data"]["object"])

        # Verify subscription was updated
        db_session.refresh(subscription)
        assert subscription.stripe_subscription_id == "sub_test_123"

    def test_subscription_deleted_webhook(self, client, db_session):
        """Test handling subscription.deleted webhook (reverts to FREE)"""
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
            plan=SubscriptionPlan.RECRUITER,
            status=SubscriptionStatus.ACTIVE,
            stripe_customer_id="cus_test_123",
            stripe_subscription_id="sub_test_123",
            monthly_candidate_limit=100
        )
        db_session.add(subscription)
        db_session.commit()

        webhook_payload = {
            "type": "customer.subscription.deleted",
            "data": {
                "object": {
                    "id": "sub_test_123",
                    "customer": "cus_test_123"
                }
            }
        }

        from app.api.endpoints.stripe_webhooks import handle_subscription_deleted

        handle_subscription_deleted(db_session, webhook_payload["data"]["object"])

        # Verify subscription reverted to FREE
        db_session.refresh(subscription)
        assert subscription.plan == SubscriptionPlan.FREE
        assert subscription.monthly_candidate_limit == 10
        assert subscription.stripe_subscription_id is None

    def test_payment_succeeded_webhook(self, client, db_session):
        """Test handling invoice.payment_succeeded webhook (resets usage)"""
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
            plan=SubscriptionPlan.RECRUITER,
            status=SubscriptionStatus.ACTIVE,
            stripe_subscription_id="sub_test_123",
            candidates_used_this_month=50  # Used half the limit
        )
        db_session.add(subscription)
        db_session.commit()

        webhook_payload = {
            "type": "invoice.payment_succeeded",
            "data": {
                "object": {
                    "subscription": "sub_test_123"
                }
            }
        }

        from app.api.endpoints.stripe_webhooks import handle_payment_succeeded

        handle_payment_succeeded(db_session, webhook_payload["data"]["object"])

        # Verify usage was reset
        db_session.refresh(subscription)
        assert subscription.candidates_used_this_month == 0
        assert subscription.status == SubscriptionStatus.ACTIVE


class TestResendWebhooks:
    """Test Resend webhook handling (incoming support emails)"""

    def test_email_received_webhook(self, client, monkeypatch):
        """Test handling email.received webhook"""
        import httpx

        # Mock the Resend API call to fetch email content
        email_fetched = []

        async def mock_get(url, headers):
            email_fetched.append(url)
            return type('obj', (object,), {
                'status_code': 200,
                'json': lambda: {
                    'html': '<p>Test email body</p>',
                    'text': 'Test email body',
                    'subject': 'Test Subject',
                    'from': 'customer@example.com'
                },
                'raise_for_status': lambda: None
            })

        class MockAsyncClient:
            async def __aenter__(self):
                return self

            async def __aexit__(self, exc_type, exc, tb):
                pass

            async def get(self, url, headers):
                return await mock_get(url, headers)

        monkeypatch.setattr("httpx.AsyncClient", MockAsyncClient)

        # Mock Resend email sending
        emails_sent = []

        def mock_send(params):
            emails_sent.append(params)
            return {'id': 'email_123'}

        monkeypatch.setattr("resend.Emails.send", mock_send)

        # Simulate webhook payload
        webhook_payload = {
            "type": "email.received",
            "data": {
                "email_id": "550e8400-e29b-41d4-a716-446655440000",
                "from": "customer@example.com",
                "to": ["support@starscreen.net"],
                "subject": "I need help with my account"
            }
        }

        response = client.post(
            "/api/v1/webhooks/resend",
            json=webhook_payload
        )

        assert response.status_code == 200
        assert response.json()["status"] == "success"
        # Verify email was forwarded
        assert len(emails_sent) == 1
        assert emails_sent[0]["to"] == ["gdsakelaris6@gmail.com"]  # From SUPPORT_FORWARD_EMAIL

    def test_email_received_unknown_event_type(self, client):
        """Test handling unknown webhook event type"""
        webhook_payload = {
            "type": "unknown.event",
            "data": {}
        }

        response = client.post(
            "/api/v1/webhooks/resend",
            json=webhook_payload
        )

        assert response.status_code == 200
        assert response.json()["status"] == "ignored"
