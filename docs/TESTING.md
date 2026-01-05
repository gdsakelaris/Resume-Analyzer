# Testing Guide for Starscreen

This guide explains how to run and write tests for Starscreen.

## Running Tests

### Run All Tests

```bash
# From project root
pytest

# With verbose output
pytest -v

# With coverage report
pytest --cov=app --cov-report=html
```

### Run Specific Test Files

```bash
# Test authentication
pytest tests/test_auth.py

# Test candidates
pytest tests/test_candidates.py

# Test subscriptions
pytest tests/test_subscriptions.py

# Test webhooks
pytest tests/test_webhooks.py

# Test admin endpoints
pytest tests/test_admin.py
```

### Run Tests by Category

```bash
# Run only unit tests
pytest -m unit

# Run only integration tests
pytest -m integration

# Skip slow tests
pytest -m "not slow"
```

### Run Specific Test Classes or Functions

```bash
# Run specific test class
pytest tests/test_auth.py::TestUserRegistration

# Run specific test function
pytest tests/test_auth.py::TestUserLogin::test_login_success
```

---

## Test Coverage

### Current Test Coverage

The test suite covers:

✅ **Authentication (test_auth.py):**
- User registration (duplicate email, weak password, invalid email)
- Login (success, wrong password, unverified user, nonexistent user)
- Token refresh (success, invalid token)
- Email verification (success, expired code, wrong code)

✅ **Candidates (test_candidates.py):**
- Resume upload (PDF, DOCX, invalid file type)
- Monthly limit enforcement
- Candidate listing (filtering by tenant)
- Resume download
- Batch operations

✅ **Subscriptions (test_subscriptions.py):**
- Get subscription status
- List pricing plans
- Upgrade subscription (valid/invalid plans)
- Cancel subscription
- Usage tracking

✅ **Webhooks (test_webhooks.py):**
- Stripe webhooks (subscription created/deleted, payment succeeded)
- Resend webhooks (email received)

✅ **Admin (test_admin.py):**
- Dashboard statistics
- Admin-only access control
- Health checks

### Generate Coverage Report

```bash
# Terminal report
pytest --cov=app --cov-report=term-missing

# HTML report (opens in browser)
pytest --cov=app --cov-report=html
open htmlcov/index.html  # macOS/Linux
start htmlcov/index.html  # Windows
```

---

## Writing New Tests

### Test Structure

```python
# tests/test_feature.py
import pytest
from fastapi.testclient import TestClient


class TestFeatureName:
    """Test description"""

    def test_success_case(self, client, db_session):
        """Test successful operation"""
        # Arrange
        # ... setup test data

        # Act
        response = client.post("/api/v1/endpoint", json={...})

        # Assert
        assert response.status_code == 200
        assert response.json()["field"] == "expected_value"

    def test_failure_case(self, client, db_session):
        """Test error handling"""
        response = client.post("/api/v1/endpoint", json={...})

        assert response.status_code == 400
        assert "error message" in response.json()["detail"]
```

### Using Fixtures

Common fixtures available in `conftest.py`:

```python
def test_with_database(db_session):
    """Use database session"""
    from app.models.user import User
    user = User(...)
    db_session.add(user)
    db_session.commit()

def test_with_client(client):
    """Use FastAPI test client"""
    response = client.get("/api/v1/endpoint")

def test_with_mock_celery(mock_celery):
    """Mock Celery tasks (runs synchronously)"""
    # Tasks will execute immediately instead of queuing

def test_with_sample_data(sample_job_data):
    """Use sample job data"""
    job_data = sample_job_data
```

### Mocking External Services

#### Mock Stripe API

```python
def test_stripe_integration(client, monkeypatch):
    """Mock Stripe API calls"""
    def mock_create_session(**kwargs):
        return type('obj', (object,), {
            'id': 'cs_test_123',
            'url': 'https://checkout.stripe.com/test'
        })

    monkeypatch.setattr(
        "stripe.checkout.Session.create",
        mock_create_session
    )

    # Test code that calls Stripe
```

#### Mock Email Service

```python
def test_email_sending(client, monkeypatch):
    """Mock email sending"""
    emails_sent = []

    def mock_send(self, to_email, code, user_name=None):
        emails_sent.append({"to": to_email, "code": code})
        return True

    monkeypatch.setattr(
        "app.services.email_service.EmailService.send_verification_email",
        mock_send
    )

    # Test code that sends emails
    assert len(emails_sent) == 1
```

#### Mock OpenAI API

```python
def test_ai_scoring(client, monkeypatch):
    """Mock OpenAI GPT-4o API"""
    def mock_create(**kwargs):
        return type('obj', (object,), {
            'choices': [{
                'message': {
                    'content': '{"match_score": 85, "skills": {"Python": 90}}'
                }
            }]
        })

    monkeypatch.setattr(
        "openai.ChatCompletion.create",
        mock_create
    )

    # Test code that uses OpenAI
```

---

## Continuous Integration

### GitHub Actions Workflow

Create `.github/workflows/test.yml`:

```yaml
name: Tests

on: [push, pull_request]

jobs:
  test:
    runs-on: ubuntu-latest

    services:
      postgres:
        image: postgres:15
        env:
          POSTGRES_PASSWORD: postgres
        options: >-
          --health-cmd pg_isready
          --health-interval 10s
          --health-timeout 5s
          --health-retries 5

      redis:
        image: redis:7-alpine
        options: >-
          --health-cmd "redis-cli ping"
          --health-interval 10s
          --health-timeout 5s
          --health-retries 5

    steps:
    - uses: actions/checkout@v3

    - name: Set up Python
      uses: actions/setup-python@v4
      with:
        python-version: '3.11'

    - name: Install dependencies
      run: |
        pip install -r requirements.txt
        pip install pytest pytest-cov pytest-asyncio

    - name: Run tests
      run: pytest --cov=app --cov-report=xml

    - name: Upload coverage
      uses: codecov/codecov-action@v3
```

---

## Test Best Practices

### DO:
✅ Test one thing per test function
✅ Use descriptive test names (`test_upload_resume_success` not `test1`)
✅ Arrange-Act-Assert pattern
✅ Mock external services (Stripe, OpenAI, S3)
✅ Clean up test data (handled automatically by fixtures)
✅ Test both success and failure cases

### DON'T:
❌ Test framework code (FastAPI, SQLAlchemy)
❌ Test third-party libraries
❌ Make real API calls to Stripe/OpenAI
❌ Rely on specific database IDs
❌ Share state between tests
❌ Skip error cases

---

## Debugging Failed Tests

### Run with verbose output

```bash
pytest -v -s  # -s shows print statements
```

### Run with debugger

```bash
pytest --pdb  # Drops into debugger on failure
```

### Run single test

```bash
pytest tests/test_auth.py::TestUserLogin::test_login_success -v
```

### Check test database

```python
def test_debug_database(db_session):
    """Debug test - check database state"""
    from app.models.user import User
    users = db_session.query(User).all()
    print(f"Users in DB: {len(users)}")
    for user in users:
        print(f"  - {user.email}")
```

---

## Common Issues

### Issue: `ModuleNotFoundError: No module named 'app'`
**Solution:** Run pytest from project root, not from `tests/` directory

### Issue: `Database locked` error
**Solution:** Use SQLite with `StaticPool` (already configured in `conftest.py`)

### Issue: Tests pass locally but fail in CI
**Solution:** Check environment variables, ensure mock data doesn't rely on local files

### Issue: Flaky tests (sometimes pass, sometimes fail)
**Solution:** Remove time-based logic, use deterministic mocks, avoid shared state

---

## Next Steps

To improve test coverage:

1. **Add E2E tests** - Test full user journey (register → upload resume → get results)
2. **Add performance tests** - Test with 1000+ resumes
3. **Add security tests** - Test SQL injection, XSS, CSRF protection
4. **Add load tests** - Use locust or k6 to simulate 100+ concurrent users

---

## Questions?

If tests are failing or you need help writing new tests:
- Check this guide first
- Review existing tests for examples
- Email: support@starscreen.net
