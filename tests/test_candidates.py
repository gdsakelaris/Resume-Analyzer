"""
Unit tests for candidate endpoints.

Tests:
- Resume upload
- Candidate listing
- Resume download
- Batch operations
- Rate limiting
"""

import pytest
import io
from fastapi.testclient import TestClient
import uuid


def create_test_user_and_job(db_session):
    """Helper to create test user and job"""
    from app.models.user import User
    from app.models.job import Job
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

    # Create subscription
    subscription = Subscription(
        id=uuid.uuid4(),
        user_id=user.id,
        plan=SubscriptionPlan.FREE,
        status=SubscriptionStatus.ACTIVE,
        monthly_candidate_limit=10,
        candidates_used_this_month=0
    )
    db_session.add(subscription)

    # Create job
    job = Job(
        id=uuid.uuid4(),
        title="Senior Python Developer",
        description="Looking for experienced Python developer",
        tenant_id=user.tenant_id,
        user_id=user.id
    )
    db_session.add(job)
    db_session.commit()

    return user, job


def get_auth_headers(client, user_email="test@example.com", password="TestPass123!"):
    """Helper to get authentication headers"""
    response = client.post(
        "/api/v1/auth/login",
        data={"username": user_email, "password": password}
    )
    token = response.json()["access_token"]
    return {"Authorization": f"Bearer {token}"}


class TestCandidateUpload:
    """Test resume upload endpoint"""

    def test_upload_pdf_resume(self, client, db_session, monkeypatch):
        """Test successful PDF resume upload"""
        user, job = create_test_user_and_job(db_session)
        headers = get_auth_headers(client)

        # Mock Celery task
        task_called = []

        def mock_delay(*args, **kwargs):
            task_called.append({"args": args, "kwargs": kwargs})
            return None

        monkeypatch.setattr("app.tasks.resume_tasks.extract_resume_text.delay", mock_delay)

        # Create fake PDF file
        pdf_content = b"%PDF-1.4\nFake PDF content for testing"
        file = ("resume.pdf", io.BytesIO(pdf_content), "application/pdf")

        # Upload
        response = client.post(
            f"/api/v1/jobs/{job.id}/candidates/upload",
            files={"file": file},
            headers=headers
        )

        assert response.status_code == 200
        data = response.json()
        assert "id" in data
        assert data["file_name"] == "resume.pdf"
        assert data["status"] == "UPLOADED"
        assert len(task_called) == 1  # Celery task was called

    def test_upload_docx_resume(self, client, db_session, monkeypatch):
        """Test successful DOCX resume upload"""
        user, job = create_test_user_and_job(db_session)
        headers = get_auth_headers(client)

        # Mock Celery task
        monkeypatch.setattr("app.tasks.resume_tasks.extract_resume_text.delay", lambda *a, **k: None)

        # Create fake DOCX file
        docx_content = b"PK\x03\x04"  # ZIP file signature (DOCX is a ZIP)
        file = ("resume.docx", io.BytesIO(docx_content), "application/vnd.openxmlformats-officedocument.wordprocessingml.document")

        response = client.post(
            f"/api/v1/jobs/{job.id}/candidates/upload",
            files={"file": file},
            headers=headers
        )

        assert response.status_code == 200
        assert response.json()["file_name"] == "resume.docx"

    def test_upload_invalid_file_type(self, client, db_session):
        """Test upload with invalid file type fails"""
        user, job = create_test_user_and_job(db_session)
        headers = get_auth_headers(client)

        # Try to upload .txt file
        file = ("resume.txt", io.BytesIO(b"Plain text resume"), "text/plain")

        response = client.post(
            f"/api/v1/jobs/{job.id}/candidates/upload",
            files={"file": file},
            headers=headers
        )

        assert response.status_code == 400
        assert "file type" in response.json()["detail"].lower()

    def test_upload_exceeds_monthly_limit(self, client, db_session):
        """Test upload fails when monthly limit is reached"""
        from app.models.subscription import Subscription

        user, job = create_test_user_and_job(db_session)
        headers = get_auth_headers(client)

        # Set subscription to limit
        subscription = db_session.query(Subscription).filter(
            Subscription.user_id == user.id
        ).first()
        subscription.candidates_used_this_month = 10  # At FREE tier limit
        subscription.monthly_candidate_limit = 10
        db_session.commit()

        file = ("resume.pdf", io.BytesIO(b"%PDF-1.4\nTest"), "application/pdf")

        response = client.post(
            f"/api/v1/jobs/{job.id}/candidates/upload",
            files={"file": file},
            headers=headers
        )

        assert response.status_code == 403
        assert "limit" in response.json()["detail"].lower()

    def test_upload_without_auth(self, client, db_session):
        """Test upload without authentication fails"""
        user, job = create_test_user_and_job(db_session)

        file = ("resume.pdf", io.BytesIO(b"%PDF-1.4\nTest"), "application/pdf")

        response = client.post(
            f"/api/v1/jobs/{job.id}/candidates/upload",
            files={"file": file}
        )

        assert response.status_code == 401

    def test_upload_to_nonexistent_job(self, client, db_session):
        """Test upload to non-existent job fails"""
        user, job = create_test_user_and_job(db_session)
        headers = get_auth_headers(client)

        fake_job_id = uuid.uuid4()
        file = ("resume.pdf", io.BytesIO(b"%PDF-1.4\nTest"), "application/pdf")

        response = client.post(
            f"/api/v1/jobs/{fake_job_id}/candidates/upload",
            files={"file": file},
            headers=headers
        )

        assert response.status_code == 404


class TestCandidateListing:
    """Test candidate listing endpoint"""

    def test_list_candidates(self, client, db_session, monkeypatch):
        """Test listing candidates for a job"""
        from app.models.candidate import Candidate, CandidateStatus

        user, job = create_test_user_and_job(db_session)
        headers = get_auth_headers(client)

        # Create test candidates
        for i in range(3):
            candidate = Candidate(
                id=uuid.uuid4(),
                job_id=job.id,
                tenant_id=user.tenant_id,
                file_name=f"resume_{i}.pdf",
                file_path=f"/fake/path/resume_{i}.pdf",
                status=CandidateStatus.SCORED
            )
            db_session.add(candidate)
        db_session.commit()

        response = client.get(
            f"/api/v1/jobs/{job.id}/candidates/",
            headers=headers
        )

        assert response.status_code == 200
        data = response.json()
        assert len(data) == 3
        assert all(c["job_id"] == str(job.id) for c in data)

    def test_list_candidates_filters_by_tenant(self, client, db_session):
        """Test listing only shows candidates from same tenant"""
        from app.models.candidate import Candidate, CandidateStatus
        from app.models.user import User
        from app.models.job import Job
        from app.core.security import get_password_hash

        user, job = create_test_user_and_job(db_session)
        headers = get_auth_headers(client)

        # Create candidate for same job but different tenant
        other_tenant_id = uuid.uuid4()
        candidate = Candidate(
            id=uuid.uuid4(),
            job_id=job.id,
            tenant_id=other_tenant_id,  # Different tenant
            file_name="resume.pdf",
            file_path="/fake/path/resume.pdf",
            status=CandidateStatus.SCORED
        )
        db_session.add(candidate)
        db_session.commit()

        response = client.get(
            f"/api/v1/jobs/{job.id}/candidates/",
            headers=headers
        )

        assert response.status_code == 200
        # Should not see candidate from different tenant
        assert len(response.json()) == 0


class TestCandidateDownload:
    """Test resume download endpoint"""

    def test_download_resume(self, client, db_session, monkeypatch):
        """Test downloading a resume"""
        from app.models.candidate import Candidate, CandidateStatus

        user, job = create_test_user_and_job(db_session)
        headers = get_auth_headers(client)

        # Create candidate
        candidate = Candidate(
            id=uuid.uuid4(),
            job_id=job.id,
            tenant_id=user.tenant_id,
            file_name="resume.pdf",
            file_path="/fake/path/resume.pdf",
            status=CandidateStatus.SCORED
        )
        db_session.add(candidate)
        db_session.commit()

        # Mock storage service
        def mock_download(file_path):
            return io.BytesIO(b"PDF content"), "resume.pdf"

        monkeypatch.setattr("app.core.storage.storage_service.download_file", mock_download)

        response = client.get(
            f"/api/v1/jobs/{job.id}/candidates/{candidate.id}/download",
            headers=headers
        )

        assert response.status_code == 200
        assert response.headers["content-type"] == "application/pdf"

    def test_download_nonexistent_candidate(self, client, db_session):
        """Test downloading non-existent candidate fails"""
        user, job = create_test_user_and_job(db_session)
        headers = get_auth_headers(client)

        fake_candidate_id = uuid.uuid4()

        response = client.get(
            f"/api/v1/jobs/{job.id}/candidates/{fake_candidate_id}/download",
            headers=headers
        )

        assert response.status_code == 404


class TestBatchOperations:
    """Test batch candidate operations"""

    def test_batch_download(self, client, db_session, monkeypatch):
        """Test batch downloading multiple resumes as ZIP"""
        from app.models.candidate import Candidate, CandidateStatus

        user, job = create_test_user_and_job(db_session)
        headers = get_auth_headers(client)

        # Create candidates
        candidate_ids = []
        for i in range(3):
            candidate = Candidate(
                id=uuid.uuid4(),
                job_id=job.id,
                tenant_id=user.tenant_id,
                file_name=f"resume_{i}.pdf",
                file_path=f"/fake/path/resume_{i}.pdf",
                status=CandidateStatus.SCORED
            )
            db_session.add(candidate)
            candidate_ids.append(candidate.id)
        db_session.commit()

        # Mock storage service
        def mock_download(file_path):
            return io.BytesIO(b"PDF content"), file_path.split("/")[-1]

        monkeypatch.setattr("app.core.storage.storage_service.download_file", mock_download)

        response = client.post(
            f"/api/v1/jobs/{job.id}/candidates/batch",
            json={"candidate_ids": [str(cid) for cid in candidate_ids]},
            headers=headers
        )

        assert response.status_code == 200
        assert response.headers["content-type"] == "application/zip"
