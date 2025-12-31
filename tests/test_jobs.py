"""
Test suite for job-related endpoints and functionality.

Tests cover:
- Job creation
- Job retrieval
- Job status tracking
- Error handling
"""

import pytest
from app.models.job import Job, JobStatus


class TestJobCreation:
    """Tests for job creation endpoint"""

    def test_create_job_success(self, client, sample_job_data, mock_celery):
        """Test successful job creation"""
        response = client.post("/api/v1/jobs/", json=sample_job_data)

        assert response.status_code == 201
        data = response.json()
        assert "job_id" in data
        assert data["status"] == "PENDING"
        assert "queued" in data["message"].lower()

    def test_create_job_missing_fields(self, client):
        """Test job creation with missing required fields"""
        response = client.post("/api/v1/jobs/", json={
            "title": "Test Job"
            # Missing description
        })

        assert response.status_code == 422  # Validation error

    def test_create_job_invalid_description(self, client):
        """Test job creation with too short description"""
        response = client.post("/api/v1/jobs/", json={
            "title": "Test Job",
            "description": "short"  # Less than 10 characters
        })

        assert response.status_code == 422


class TestJobRetrieval:
    """Tests for job retrieval endpoints"""

    def test_get_job_by_id(self, client, db_session, sample_job_data, mock_celery):
        """Test retrieving a job by ID"""
        # Create a job first
        create_response = client.post("/api/v1/jobs/", json=sample_job_data)
        job_id = create_response.json()["job_id"]

        # Retrieve it
        response = client.get(f"/api/v1/jobs/{job_id}")

        assert response.status_code == 200
        data = response.json()
        assert data["id"] == job_id
        assert data["title"] == sample_job_data["title"]
        assert "status" in data

    def test_get_nonexistent_job(self, client):
        """Test retrieving a job that doesn't exist"""
        response = client.get("/api/v1/jobs/99999")

        assert response.status_code == 404
        assert "not found" in response.json()["detail"].lower()

    def test_list_jobs(self, client, db_session, sample_job_data, mock_celery):
        """Test listing all jobs"""
        # Create multiple jobs
        for i in range(3):
            job_data = sample_job_data.copy()
            job_data["title"] = f"Job {i}"
            client.post("/api/v1/jobs/", json=job_data)

        # List all jobs
        response = client.get("/api/v1/jobs/")

        assert response.status_code == 200
        data = response.json()
        assert isinstance(data, list)
        assert len(data) == 3

    def test_list_jobs_with_pagination(self, client, db_session, sample_job_data, mock_celery):
        """Test job listing with pagination"""
        # Create 5 jobs
        for i in range(5):
            job_data = sample_job_data.copy()
            job_data["title"] = f"Job {i}"
            client.post("/api/v1/jobs/", json=job_data)

        # Get first 3
        response = client.get("/api/v1/jobs/?skip=0&limit=3")
        assert len(response.json()) == 3

        # Get next 2
        response = client.get("/api/v1/jobs/?skip=3&limit=3")
        assert len(response.json()) == 2


class TestJobStatus:
    """Tests for job status tracking"""

    def test_job_initial_status_is_pending(self, client, sample_job_data, mock_celery):
        """Test that newly created jobs have PENDING status"""
        response = client.post("/api/v1/jobs/", json=sample_job_data)
        job_id = response.json()["job_id"]

        job_response = client.get(f"/api/v1/jobs/{job_id}")
        assert job_response.json()["status"] == "PENDING"

    def test_filter_jobs_by_status(self, client, db_session, sample_job_data):
        """Test filtering jobs by status"""
        # Create jobs with different statuses
        job1 = Job(**sample_job_data, status=JobStatus.PENDING)
        job2 = Job(**sample_job_data, status=JobStatus.COMPLETED)
        job3 = Job(**sample_job_data, status=JobStatus.FAILED)

        db_session.add_all([job1, job2, job3])
        db_session.commit()

        # Filter by COMPLETED
        response = client.get("/api/v1/jobs/?status=COMPLETED")
        data = response.json()
        assert len(data) == 1
        assert data[0]["status"] == "COMPLETED"

        # Filter by FAILED
        response = client.get("/api/v1/jobs/?status=FAILED")
        data = response.json()
        assert len(data) == 1
        assert data[0]["status"] == "FAILED"


class TestJobDeletion:
    """Tests for job deletion"""

    def test_delete_job(self, client, db_session, sample_job_data, mock_celery):
        """Test deleting a job"""
        # Create a job
        create_response = client.post("/api/v1/jobs/", json=sample_job_data)
        job_id = create_response.json()["job_id"]

        # Delete it
        response = client.delete(f"/api/v1/jobs/{job_id}")
        assert response.status_code == 204

        # Verify it's gone
        get_response = client.get(f"/api/v1/jobs/{job_id}")
        assert get_response.status_code == 404

    def test_delete_nonexistent_job(self, client):
        """Test deleting a job that doesn't exist"""
        response = client.delete("/api/v1/jobs/99999")
        assert response.status_code == 404


class TestJobValidation:
    """Tests for job data validation"""

    def test_title_length_validation(self, client):
        """Test title length constraints"""
        # Empty title
        response = client.post("/api/v1/jobs/", json={
            "title": "",
            "description": "A valid description with sufficient length"
        })
        assert response.status_code == 422

    def test_description_min_length(self, client):
        """Test description minimum length"""
        response = client.post("/api/v1/jobs/", json={
            "title": "Valid Title",
            "description": "short"  # Less than 10 chars
        })
        assert response.status_code == 422

    def test_optional_fields(self, client, mock_celery):
        """Test that optional fields work correctly"""
        response = client.post("/api/v1/jobs/", json={
            "title": "Test Job",
            "description": "A valid description for testing purposes",
            # location and work_authorization_required are optional
        })

        assert response.status_code == 201
        job_id = response.json()["job_id"]

        job_response = client.get(f"/api/v1/jobs/{job_id}")
        data = job_response.json()
        assert data["location"] is None
        assert data["work_authorization_required"] is False  # Default value
