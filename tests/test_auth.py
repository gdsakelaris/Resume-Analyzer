"""
Unit tests for authentication endpoints.

Tests:
- User registration
- Login
- Token refresh
- Email verification flow
- Password validation
"""

import pytest
from fastapi.testclient import TestClient
from datetime import datetime, timedelta
import uuid

from app.models.user import User
from app.models.email_verification import EmailVerification
from app.core.security import create_access_token, verify_password


class TestUserRegistration:
    """Test user registration endpoint"""

    def test_register_success(self, client):
        """Test successful user registration"""
        response = client.post(
            "/api/v1/auth/register",
            json={
                "email": "test@example.com",
                "password": "SecurePass123!",
                "full_name": "Test User"
            }
        )

        assert response.status_code == 200
        data = response.json()
        assert "access_token" in data
        assert "refresh_token" in data
        assert data["token_type"] == "bearer"

    def test_register_duplicate_email(self, client, db_session):
        """Test registration with duplicate email fails"""
        # Create existing user
        from app.models.user import User
        import uuid
        from app.core.security import get_password_hash

        user = User(
            id=uuid.uuid4(),
            email="existing@example.com",
            hashed_password=get_password_hash("password123"),
            tenant_id=uuid.uuid4(),
            is_verified=True
        )
        db_session.add(user)
        db_session.commit()

        # Try to register with same email
        response = client.post(
            "/api/v1/auth/register",
            json={
                "email": "existing@example.com",
                "password": "DifferentPass123!"
            }
        )

        assert response.status_code == 400
        assert "already registered" in response.json()["detail"].lower()

    def test_register_weak_password(self, client):
        """Test registration with weak password fails"""
        response = client.post(
            "/api/v1/auth/register",
            json={
                "email": "test@example.com",
                "password": "weak"
            }
        )

        assert response.status_code == 422

    def test_register_invalid_email(self, client):
        """Test registration with invalid email fails"""
        response = client.post(
            "/api/v1/auth/register",
            json={
                "email": "not-an-email",
                "password": "SecurePass123!"
            }
        )

        assert response.status_code == 422


class TestUserLogin:
    """Test user login endpoint"""

    def test_login_success(self, client, db_session):
        """Test successful login"""
        from app.models.user import User
        from app.core.security import get_password_hash
        import uuid

        # Create verified user
        user = User(
            id=uuid.uuid4(),
            email="test@example.com",
            hashed_password=get_password_hash("TestPass123!"),
            tenant_id=uuid.uuid4(),
            is_verified=True
        )
        db_session.add(user)
        db_session.commit()

        # Login
        response = client.post(
            "/api/v1/auth/login",
            data={
                "username": "test@example.com",
                "password": "TestPass123!"
            }
        )

        assert response.status_code == 200
        data = response.json()
        assert "access_token" in data
        assert "refresh_token" in data

    def test_login_wrong_password(self, client, db_session):
        """Test login with wrong password fails"""
        from app.models.user import User
        from app.core.security import get_password_hash
        import uuid

        user = User(
            id=uuid.uuid4(),
            email="test@example.com",
            hashed_password=get_password_hash("CorrectPass123!"),
            tenant_id=uuid.uuid4(),
            is_verified=True
        )
        db_session.add(user)
        db_session.commit()

        response = client.post(
            "/api/v1/auth/login",
            data={
                "username": "test@example.com",
                "password": "WrongPass123!"
            }
        )

        assert response.status_code == 401

    def test_login_unverified_user(self, client, db_session):
        """Test login with unverified email fails"""
        from app.models.user import User
        from app.core.security import get_password_hash
        import uuid

        user = User(
            id=uuid.uuid4(),
            email="test@example.com",
            hashed_password=get_password_hash("TestPass123!"),
            tenant_id=uuid.uuid4(),
            is_verified=False
        )
        db_session.add(user)
        db_session.commit()

        response = client.post(
            "/api/v1/auth/login",
            data={
                "username": "test@example.com",
                "password": "TestPass123!"
            }
        )

        assert response.status_code == 403
        assert "verify" in response.json()["detail"].lower()

    def test_login_nonexistent_user(self, client):
        """Test login with nonexistent user fails"""
        response = client.post(
            "/api/v1/auth/login",
            data={
                "username": "nonexistent@example.com",
                "password": "TestPass123!"
            }
        )

        assert response.status_code == 401


class TestTokenRefresh:
    """Test token refresh endpoint"""

    def test_refresh_token_success(self, client, db_session):
        """Test successful token refresh"""
        from app.models.user import User
        from app.core.security import get_password_hash, create_refresh_token
        import uuid

        user = User(
            id=uuid.uuid4(),
            email="test@example.com",
            hashed_password=get_password_hash("TestPass123!"),
            tenant_id=uuid.uuid4(),
            is_verified=True
        )
        db_session.add(user)
        db_session.commit()

        # Create refresh token
        refresh_token = create_refresh_token(data={"sub": user.email})

        # Refresh
        response = client.post(
            "/api/v1/auth/refresh",
            json={"refresh_token": refresh_token}
        )

        assert response.status_code == 200
        data = response.json()
        assert "access_token" in data
        assert "refresh_token" in data

    def test_refresh_token_invalid(self, client):
        """Test refresh with invalid token fails"""
        response = client.post(
            "/api/v1/auth/refresh",
            json={"refresh_token": "invalid.token.here"}
        )

        assert response.status_code == 401


class TestEmailVerification:
    """Test email verification endpoints"""

    def test_send_verification_email(self, client, db_session, monkeypatch):
        """Test sending verification email"""
        from app.models.user import User
        from app.core.security import get_password_hash
        import uuid

        # Mock email service
        email_sent = []

        def mock_send_verification(self, to_email, code, user_name=None):
            email_sent.append({"to": to_email, "code": code})
            return True

        monkeypatch.setattr(
            "app.services.email_service.EmailService.send_verification_email",
            mock_send_verification
        )

        user = User(
            id=uuid.uuid4(),
            email="test@example.com",
            hashed_password=get_password_hash("TestPass123!"),
            tenant_id=uuid.uuid4(),
            is_verified=False
        )
        db_session.add(user)
        db_session.commit()

        # Send verification
        response = client.post(
            "/api/v1/verify/send-verification-email",
            json={"email": "test@example.com"}
        )

        assert response.status_code == 200
        assert len(email_sent) == 1
        assert email_sent[0]["to"] == "test@example.com"

    def test_verify_email_success(self, client, db_session):
        """Test successful email verification"""
        from app.models.user import User
        from app.models.email_verification import EmailVerification
        from app.core.security import get_password_hash
        import uuid
        from datetime import datetime, timedelta

        user = User(
            id=uuid.uuid4(),
            email="test@example.com",
            hashed_password=get_password_hash("TestPass123!"),
            tenant_id=uuid.uuid4(),
            is_verified=False
        )
        db_session.add(user)
        db_session.flush()

        # Create verification code
        verification = EmailVerification(
            id=uuid.uuid4(),
            user_id=user.id,
            code="123456",
            expires_at=datetime.utcnow() + timedelta(minutes=15)
        )
        db_session.add(verification)
        db_session.commit()

        # Verify
        response = client.post(
            "/api/v1/verify/verify-email",
            json={
                "email": "test@example.com",
                "code": "123456"
            }
        )

        assert response.status_code == 200
        assert "verified" in response.json()["message"].lower()

        # Check user is now verified
        db_session.refresh(user)
        assert user.is_verified is True

    def test_verify_email_expired_code(self, client, db_session):
        """Test verification with expired code fails"""
        from app.models.user import User
        from app.models.email_verification import EmailVerification
        from app.core.security import get_password_hash
        import uuid
        from datetime import datetime, timedelta

        user = User(
            id=uuid.uuid4(),
            email="test@example.com",
            hashed_password=get_password_hash("TestPass123!"),
            tenant_id=uuid.uuid4(),
            is_verified=False
        )
        db_session.add(user)
        db_session.flush()

        # Create expired verification code
        verification = EmailVerification(
            id=uuid.uuid4(),
            user_id=user.id,
            code="123456",
            expires_at=datetime.utcnow() - timedelta(minutes=1)
        )
        db_session.add(verification)
        db_session.commit()

        # Verify
        response = client.post(
            "/api/v1/verify/verify-email",
            json={
                "email": "test@example.com",
                "code": "123456"
            }
        )

        assert response.status_code == 400
        assert "expired" in response.json()["detail"].lower()

    def test_verify_email_wrong_code(self, client, db_session):
        """Test verification with wrong code fails"""
        from app.models.user import User
        from app.models.email_verification import EmailVerification
        from app.core.security import get_password_hash
        import uuid
        from datetime import datetime, timedelta

        user = User(
            id=uuid.uuid4(),
            email="test@example.com",
            hashed_password=get_password_hash("TestPass123!"),
            tenant_id=uuid.uuid4(),
            is_verified=False
        )
        db_session.add(user)
        db_session.flush()

        # Create verification code
        verification = EmailVerification(
            id=uuid.uuid4(),
            user_id=user.id,
            code="123456",
            expires_at=datetime.utcnow() + timedelta(minutes=15)
        )
        db_session.add(verification)
        db_session.commit()

        # Verify with wrong code
        response = client.post(
            "/api/v1/verify/verify-email",
            json={
                "email": "test@example.com",
                "code": "999999"
            }
        )

        assert response.status_code == 400
        assert "invalid" in response.json()["detail"].lower()
