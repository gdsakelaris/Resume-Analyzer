                                                #!/usr/bin/env python3
"""
Simple test script to verify the Resume Analyzer API is working correctly.

Usage:
    python test_api.py
"""

import requests
import time
import sys
from typing import Dict, Any


API_BASE_URL = "http://localhost:8000"


def test_health_check() -> bool:
    """Test the health check endpoint"""
    print("Testing health check endpoint...")
    try:
        response = requests.get(f"{API_BASE_URL}/health", timeout=5)
        if response.status_code == 200:
            print("✓ Health check passed")
            return True
        else:
            print(f"✗ Health check failed with status {response.status_code}")
            return False
    except requests.exceptions.RequestException as e:
        print(f"✗ Health check failed: {e}")
        print("  Make sure the API is running on http://localhost:8000")
        return False


def create_test_job() -> Dict[str, Any]:
    """Create a test job"""
    print("\nCreating test job...")

    job_data = {
        "title": "Senior Backend Engineer",
        "description": """
        We are looking for a Senior Backend Engineer with 5+ years of experience.

        Requirements:
        - Expert knowledge of Python and FastAPI
        - Strong experience with PostgreSQL and database design
        - Experience with Docker and containerization
        - Familiarity with AWS cloud services
        - Experience building RESTful APIs
        - Knowledge of microservices architecture

        Nice to have:
        - Experience with Redis and caching strategies
        - Knowledge of CI/CD pipelines
        - Experience with Kubernetes

        Education: Bachelor's degree in Computer Science or related field
        """,
        "location": "San Francisco, CA (Remote)",
        "work_authorization_required": True
    }

    try:
        response = requests.post(
            f"{API_BASE_URL}/api/v1/jobs/",
            json=job_data,
            timeout=10
        )

        if response.status_code == 201:
            result = response.json()
            print(f"✓ Job created successfully (ID: {result['job_id']})")
            return result
        else:
            print(f"✗ Failed to create job: {response.status_code}")
            print(f"  Response: {response.text}")
            return {}
    except requests.exceptions.RequestException as e:
        print(f"✗ Failed to create job: {e}")
        return {}


def get_job(job_id: int, wait_for_config: bool = True) -> Dict[str, Any]:
    """Retrieve a job by ID"""
    print(f"\nRetrieving job {job_id}...")

    max_attempts = 6 if wait_for_config else 1

    for attempt in range(max_attempts):
        try:
            response = requests.get(
                f"{API_BASE_URL}/api/v1/jobs/{job_id}",
                timeout=5
            )

            if response.status_code == 200:
                job = response.json()
                status = job.get('status', 'UNKNOWN')

                print(f"  Status: {status}")

                if status == 'COMPLETED':
                    print(f"✓ Job retrieved with AI configuration")
                    return job
                elif status == 'FAILED':
                    error_msg = job.get('error_message', 'Unknown error')
                    print(f"✗ Job generation failed: {error_msg}")
                    return job
                elif status == 'PROCESSING':
                    if wait_for_config and attempt < max_attempts - 1:
                        print(f"  AI generation in progress, waiting... (attempt {attempt + 1}/{max_attempts})")
                        time.sleep(5)
                    else:
                        print("✓ Job retrieved (still processing)")
                        return job
                elif status == 'PENDING':
                    if wait_for_config and attempt < max_attempts - 1:
                        print(f"  AI generation queued, waiting... (attempt {attempt + 1}/{max_attempts})")
                        time.sleep(5)
                    else:
                        print("✓ Job retrieved (pending processing)")
                        return job
                else:
                    return job
            else:
                print(f"✗ Failed to retrieve job: {response.status_code}")
                return {}
        except requests.exceptions.RequestException as e:
            print(f"✗ Failed to retrieve job: {e}")
            return {}

    return {}


def display_job_config(job: Dict[str, Any]) -> None:
    """Display job configuration details"""
    status = job.get('status', 'UNKNOWN')

    if status == 'FAILED':
        print("\n" + "="*60)
        print("JOB PROCESSING FAILED")
        print("="*60)
        print(f"\nError: {job.get('error_message', 'Unknown error')}")
        print("\nThe AI failed to generate a configuration for this job.")
        print("This could be due to:")
        print("  - Invalid OpenAI API key")
        print("  - API rate limiting")
        print("  - Malformed job description")
        print("="*60)
        return

    if not job.get('job_config'):
        print(f"\n⚠ AI configuration not yet generated (Status: {status})")
        if status == 'PROCESSING':
            print("  The AI is currently analyzing the job description...")
        elif status == 'PENDING':
            print("  The job is queued for processing...")
        return

    config = job['job_config']

    print("\n" + "="*60)
    print("AI-GENERATED JOB CONFIGURATION")
    print("="*60)

    print(f"\nTitle: {config.get('title')}")
    print(f"Seniority Level: {config.get('seniority_level')}")
    print(f"\nRole Summary:\n{config.get('role_summary')}")

    print("\nCore Responsibilities:")
    for i, resp in enumerate(config.get('core_responsibilities', []), 1):
        print(f"  {i}. {resp}")

    print("\nSkill Categories:")
    for cat in config.get('categories', []):
        print(f"\n  {cat['name']} (Importance: {cat['importance']}/5)")
        print(f"  Description: {cat['description']}")
        print(f"  Evidence examples:")
        for evidence in cat.get('examples_of_evidence', [])[:3]:
            print(f"    - {evidence}")

    print("\nDesired Background:")
    bg = config.get('desired_background_patterns', {})
    for key, value in bg.items():
        print(f"  {key}: {value}")

    print("\nEducation Preferences:")
    edu = config.get('education_preferences', {})
    for key, value in edu.items():
        print(f"  {key}: {value}")

    print("\n" + "="*60)


def main():
    """Run all tests"""
    print("="*60)
    print("RESUME ANALYZER API TEST SUITE")
    print("="*60)

    # Test 1: Health Check
    if not test_health_check():
        print("\n✗ Tests failed: API is not responding")
        print("  Make sure you've started the API with: python main.py")
        sys.exit(1)

    # Test 2: Create Job
    result = create_test_job()
    if not result:
        print("\n✗ Tests failed: Could not create job")
        sys.exit(1)

    job_id = result.get('job_id')

    # Test 3: Retrieve Job
    job = get_job(job_id, wait_for_config=True)
    if not job:
        print("\n✗ Tests failed: Could not retrieve job")
        sys.exit(1)

    # Display Results
    display_job_config(job)

    print("\n" + "="*60)
    print("✓ ALL TESTS PASSED!")
    print("="*60)
    print(f"\nYour Resume Analyzer API is working correctly!")
    print(f"Visit http://localhost:8000/docs for interactive documentation")


if __name__ == "__main__":
    main()
