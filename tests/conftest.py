"""
Pytest configuration and fixtures for testing.

This file provides reusable test fixtures for:
- Database setup/teardown
- FastAPI test client
- Mock Celery tasks
"""

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.core.database import Base, get_db
from app.models.job import Job
from main import app


# Use in-memory SQLite for testing (fast, isolated)
SQLALCHEMY_TEST_DATABASE_URL = "sqlite:///:memory:"

engine = create_engine(
    SQLALCHEMY_TEST_DATABASE_URL,
    connect_args={"check_same_thread": False},
    poolclass=StaticPool,
)
TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)


@pytest.fixture
def db_session():
    """
    Create a fresh database session for each test.
    Automatically rolls back after test completes.
    """
    Base.metadata.create_all(bind=engine)
    db = TestingSessionLocal()
    try:
        yield db
    finally:
        db.close()
        Base.metadata.drop_all(bind=engine)


@pytest.fixture
def client(db_session):
    """
    FastAPI test client with overridden database dependency.
    """
    def override_get_db():
        try:
            yield db_session
        finally:
            pass

    app.dependency_overrides[get_db] = override_get_db

    with TestClient(app) as test_client:
        yield test_client

    app.dependency_overrides.clear()


@pytest.fixture
def mock_celery(monkeypatch):
    """
    Mock Celery task execution for testing without Redis.
    Executes tasks synchronously in tests.
    """
    from app.tasks import job_tasks

    def mock_delay(self, *args, **kwargs):
        """Execute task synchronously instead of queuing"""
        # Call the actual task function directly
        return self(*args, **kwargs)

    monkeypatch.setattr("celery.Task.delay", mock_delay)
    return mock_delay


@pytest.fixture
def sample_job_data():
    """Sample job data for testing"""
    return {
        "title": "Senior Python Developer",
        "description": """
        We are looking for a Senior Python Developer with 5+ years of experience.

        Requirements:
        - Expert knowledge of Python and FastAPI
        - Strong experience with PostgreSQL
        - Experience with Docker and containerization
        - Familiarity with AWS cloud services

        Nice to have:
        - Experience with Redis and Celery
        - Knowledge of CI/CD pipelines
        """,
        "location": "San Francisco, CA (Remote)",
        "work_authorization_required": True
    }
