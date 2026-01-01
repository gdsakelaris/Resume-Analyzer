"""
API endpoints for candidate management.

Handles resume uploads, candidate status tracking, and retrieval.
"""

import logging
import shutil
import os
import uuid
import zipfile
from typing import Optional
from fastapi import APIRouter, UploadFile, File, Form, Depends, HTTPException
from sqlalchemy.orm import Session
from app.core.database import get_db
from app.models.candidate import Candidate, CandidateStatus
from app.schemas.candidate import CandidateUploadResponse, CandidateResponse, CandidateListResponse
from app.tasks import resume_tasks

router = APIRouter(prefix="/jobs/{job_id}/candidates", tags=["Starscreen Candidates"])
logger = logging.getLogger(__name__)

# Upload directory configuration
# In production, this would be replaced with S3/blob storage
UPLOAD_DIR = "uploads"
os.makedirs(UPLOAD_DIR, exist_ok=True)


@router.post("/upload", response_model=CandidateUploadResponse)
async def upload_resume(
    job_id: int,
    file: UploadFile = File(...),
    first_name: Optional[str] = Form(None),
    last_name: Optional[str] = Form(None),
    email: Optional[str] = Form(None),
    db: Session = Depends(get_db)
):
    """
    Upload a candidate's resume for a specific job.

    This endpoint implements the competitive advantage strategy:
    - Accepts optional PII (first_name, last_name, email) for blind screening
    - Queues asynchronous processing to avoid blocking the user
    - Returns immediately with tracking ID

    Flow:
    1. Validate file type (PDF, DOC, DOCX)
    2. Save file securely (UUID-based naming to prevent path traversal)
    3. Create database record with status=UPLOADED
    4. Queue parsing task to Celery worker
    5. Return candidate_id for status tracking

    Args:
        job_id: The job posting ID this candidate is applying for
        file: Resume file (PDF, DOC, or DOCX)
        first_name: Optional candidate first name (can be null for blind screening)
        last_name: Optional candidate last name (can be null for blind screening)
        email: Optional candidate email (can be null for blind screening)

    Returns:
        dict: Candidate ID, status, and confirmation message

    Raises:
        HTTPException 400: If file is not PDF, DOC, or DOCX
        HTTPException 404: If job doesn't exist
    """
    from app.models.job import Job

    # 1. Validate that the job exists
    job = db.query(Job).filter(Job.id == job_id).first()
    if not job:
        raise HTTPException(status_code=404, detail=f"Job {job_id} not found")

    # 2. Validate file type (PDF, DOC, DOCX)
    ALLOWED_CONTENT_TYPES = {
        "application/pdf",
        "application/msword",  # .doc
        "application/vnd.openxmlformats-officedocument.wordprocessingml.document"  # .docx
    }
    ALLOWED_EXTENSIONS = {".pdf", ".doc", ".docx"}

    file_ext = os.path.splitext(file.filename)[1].lower()

    if file.content_type not in ALLOWED_CONTENT_TYPES and file_ext not in ALLOWED_EXTENSIONS:
        raise HTTPException(
            status_code=400,
            detail=f"Only PDF, DOC, and DOCX files are supported. Received: {file.content_type}"
        )

    # 3. Save file securely with UUID-based naming
    # This prevents:
    # - Path traversal attacks (../../etc/passwd)
    # - Filename collisions
    # - Special character issues
    file_ext = os.path.splitext(file.filename)[1]
    safe_filename = f"{uuid.uuid4()}{file_ext}"
    file_path = os.path.join(UPLOAD_DIR, safe_filename)

    try:
        with open(file_path, "wb") as buffer:
            shutil.copyfileobj(file.file, buffer)
        logger.info(f"Saved resume to {file_path}")
    except Exception as e:
        logger.error(f"Failed to save file: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to save file: {str(e)}")

    # 4. Create database entry
    candidate = Candidate(
        job_id=job_id,
        first_name=first_name,
        last_name=last_name,
        email=email,
        original_filename=file.filename,
        file_path=file_path,
        status=CandidateStatus.UPLOADED
    )

    try:
        db.add(candidate)
        db.commit()
        db.refresh(candidate)
        logger.info(f"Created candidate {candidate.id} for job {job_id}")
    except Exception as e:
        # Clean up file if database insert fails
        if os.path.exists(file_path):
            os.remove(file_path)
        logger.error(f"Failed to create candidate record: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to create candidate: {str(e)}")

    # 5. Queue parsing task to Celery worker via Redis
    task = resume_tasks.parse_resume_task.delay(candidate.id)
    logger.info(f"Queued parsing task {task.id} for candidate {candidate.id}")

    return {
        "candidate_id": candidate.id,
        "job_id": job_id,
        "status": CandidateStatus.UPLOADED.value,
        "task_id": task.id,
        "message": "Resume uploaded successfully. Parsing queued to background worker."
    }


@router.post("/bulk-upload-zip")
async def bulk_upload_resumes(
    job_id: int,
    file: UploadFile = File(...),
    db: Session = Depends(get_db)
):
    """
    Upload a ZIP file containing multiple resumes (PDF, DOC, DOCX).

    This is the KILLER FEATURE for B2B sales:
    - Recruiters export 50+ resumes as ZIP from LinkedIn/Greenhouse
    - They drag ONE file into your app
    - Your system processes all resumes automatically

    This solves the "manual friction" problem and makes the tool
    sellable to businesses who need to screen hundreds of candidates.

    Flow:
    1. Validate ZIP file format
    2. Extract all resumes from ZIP (skip folders, non-resume files, __MACOSX)
    3. Create candidate record for each resume
    4. Queue parsing task for each candidate
    5. Return summary of processed candidates

    Args:
        job_id: The job posting ID these candidates are applying for
        file: ZIP archive containing resume files (PDF, DOC, DOCX)

    Returns:
        dict: Summary with count of processed candidates and job_id

    Raises:
        HTTPException 400: If file is not a ZIP
        HTTPException 404: If job doesn't exist
        HTTPException 500: If extraction fails

    Example Response:
        {
            "message": "Bulk upload processed. 47 candidates created.",
            "job_id": 123,
            "processed_count": 47,
            "skipped_count": 3
        }
    """
    from app.models.job import Job

    # 1. Validate that the job exists
    job = db.query(Job).filter(Job.id == job_id).first()
    if not job:
        raise HTTPException(status_code=404, detail=f"Job {job_id} not found")

    # 2. Validate file type
    if not file.filename.endswith(".zip"):
        raise HTTPException(
            status_code=400,
            detail=f"File must be a ZIP archive. Received: {file.filename}"
        )

    # 3. Save ZIP file temporarily
    zip_filename = f"{uuid.uuid4()}.zip"
    zip_path = os.path.join(UPLOAD_DIR, zip_filename)

    try:
        with open(zip_path, "wb") as buffer:
            shutil.copyfileobj(file.file, buffer)
        logger.info(f"Saved ZIP file to {zip_path}")
    except Exception as e:
        logger.error(f"Failed to save ZIP file: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to save ZIP file: {str(e)}")

    processed_count = 0
    skipped_count = 0

    # 4. Extract and process resume files from ZIP
    ALLOWED_EXTENSIONS = ('.pdf', '.doc', '.docx')
    try:
        with zipfile.ZipFile(zip_path, 'r') as zip_ref:
            for filename in zip_ref.namelist():
                # Skip folders and non-resume files
                # Also skip macOS metadata folders (.__MACOSX, .DS_Store)
                filename_lower = filename.lower()
                if (filename.startswith("__") or
                    filename.startswith(".") or
                    filename.endswith("/") or
                    not filename_lower.endswith(ALLOWED_EXTENSIONS)):
                    logger.debug(f"Skipping non-resume file: {filename}")
                    skipped_count += 1
                    continue

                # Extract single resume file
                try:
                    source = zip_ref.open(filename)

                    # Create unique filename with original extension
                    file_ext = os.path.splitext(filename)[1]
                    unique_filename = f"{uuid.uuid4()}{file_ext}"
                    target_path = os.path.join(UPLOAD_DIR, unique_filename)

                    with open(target_path, "wb") as target:
                        shutil.copyfileobj(source, target)

                    logger.info(f"Extracted {filename} to {target_path}")

                    # Create database entry for this candidate
                    candidate = Candidate(
                        job_id=job_id,
                        original_filename=os.path.basename(filename),
                        file_path=target_path,
                        status=CandidateStatus.UPLOADED
                    )

                    db.add(candidate)
                    db.commit()
                    db.refresh(candidate)

                    # Queue parsing task for this candidate
                    task = resume_tasks.parse_resume_task.delay(candidate.id)
                    logger.info(f"Created candidate {candidate.id}, queued task {task.id}")

                    processed_count += 1

                except Exception as e:
                    logger.error(f"Failed to process {filename} from ZIP: {e}")
                    # Continue with next file even if one fails
                    skipped_count += 1
                    continue

        # 5. Clean up the original ZIP file
        if os.path.exists(zip_path):
            os.remove(zip_path)
            logger.info(f"Cleaned up ZIP file: {zip_path}")

        logger.info(
            f"Bulk upload complete for job {job_id}: "
            f"{processed_count} processed, {skipped_count} skipped"
        )

        return {
            "message": f"Bulk upload processed. {processed_count} candidates created.",
            "job_id": job_id,
            "processed_count": processed_count,
            "skipped_count": skipped_count
        }

    except zipfile.BadZipFile:
        # Clean up on failure
        if os.path.exists(zip_path):
            os.remove(zip_path)
        raise HTTPException(
            status_code=400,
            detail="Invalid ZIP file. Please ensure the file is a valid ZIP archive."
        )
    except Exception as e:
        # Clean up on failure
        if os.path.exists(zip_path):
            os.remove(zip_path)
        logger.error(f"Bulk upload failed: {e}")
        raise HTTPException(
            status_code=500,
            detail=f"Bulk upload failed: {str(e)}"
        )


@router.get("/{candidate_id}", response_model=CandidateResponse)
def get_candidate(
    job_id: int,
    candidate_id: int,
    db: Session = Depends(get_db)
):
    """
    Get a candidate's details and processing status.

    Check the `status` field to understand the processing state:
    - UPLOADED: File received, parsing not yet started
    - PROCESSING: Text extraction in progress
    - PARSED: Text extracted, ready for AI scoring
    - SCORED: AI evaluation complete (future)
    - FAILED: Processing failed, check error_message

    Args:
        job_id: The job posting ID
        candidate_id: The candidate ID

    Returns:
        Candidate: Full candidate record including status and resume text

    Raises:
        HTTPException 404: If candidate not found or doesn't belong to job
    """
    candidate = db.query(Candidate).filter(
        Candidate.id == candidate_id,
        Candidate.job_id == job_id
    ).first()

    if not candidate:
        raise HTTPException(
            status_code=404,
            detail=f"Candidate {candidate_id} not found for job {job_id}"
        )

    return candidate


@router.get("/", response_model=list[CandidateListResponse])
def list_candidates(
    job_id: int,
    skip: int = 0,
    limit: int = 100,
    status: Optional[CandidateStatus] = None,
    db: Session = Depends(get_db)
):
    """
    List all candidates for a job with optional status filtering.

    Args:
        job_id: The job posting ID
        skip: Number of records to skip (pagination)
        limit: Maximum records to return (max 100)
        status: Optional filter by candidate status

    Returns:
        list[Candidate]: List of candidates matching criteria
    """
    if limit > 100:
        limit = 100

    query = db.query(Candidate).filter(Candidate.job_id == job_id)

    if status:
        query = query.filter(Candidate.status == status)

    candidates = query.offset(skip).limit(limit).all()

    # Populate score from evaluation relationship
    results = []
    for c in candidates:
        candidate_dict = {
            'id': c.id,
            'job_id': c.job_id,
            'first_name': c.first_name,
            'last_name': c.last_name,
            'email': c.email,
            'phone': c.phone,
            'location': c.location,
            'linkedin_url': c.linkedin_url,
            'github_url': c.github_url,
            'portfolio_url': c.portfolio_url,
            'other_urls': c.other_urls,
            'original_filename': c.original_filename,
            'status': c.status,
            'error_message': c.error_message,
            'created_at': c.created_at,
            'score': c.evaluation.match_score if c.evaluation else None
        }
        results.append(candidate_dict)

    return results


@router.get("/{candidate_id}/file")
def get_candidate_file(
    job_id: int,
    candidate_id: int,
    db: Session = Depends(get_db)
):
    """
    Download or view a candidate's resume file.

    Args:
        job_id: The job posting ID
        candidate_id: The candidate ID

    Returns:
        FileResponse: The resume file

    Raises:
        HTTPException 404: If candidate not found or file doesn't exist
    """
    from fastapi.responses import FileResponse

    candidate = db.query(Candidate).filter(
        Candidate.id == candidate_id,
        Candidate.job_id == job_id
    ).first()

    if not candidate:
        raise HTTPException(
            status_code=404,
            detail=f"Candidate {candidate_id} not found for job {job_id}"
        )

    if not os.path.exists(candidate.file_path):
        raise HTTPException(
            status_code=404,
            detail=f"Resume file not found for candidate {candidate_id}"
        )

    return FileResponse(
        path=candidate.file_path,
        filename=candidate.original_filename,
        media_type="application/octet-stream"
    )


@router.get("/{candidate_id}/evaluation")
def get_candidate_evaluation(
    job_id: int,
    candidate_id: int,
    db: Session = Depends(get_db)
):
    """
    Get the AI evaluation for a candidate.

    Args:
        job_id: The job posting ID
        candidate_id: The candidate ID

    Returns:
        Evaluation: The AI-generated evaluation with scores, summary, pros, and cons

    Raises:
        HTTPException 404: If candidate not found or evaluation doesn't exist
    """
    from app.models.evaluation import Evaluation

    candidate = db.query(Candidate).filter(
        Candidate.id == candidate_id,
        Candidate.job_id == job_id
    ).first()

    if not candidate:
        raise HTTPException(
            status_code=404,
            detail=f"Candidate {candidate_id} not found for job {job_id}"
        )

    evaluation = db.query(Evaluation).filter(
        Evaluation.candidate_id == candidate_id
    ).first()

    if not evaluation:
        raise HTTPException(
            status_code=404,
            detail=f"Evaluation not found for candidate {candidate_id}"
        )

    return {
        "match_score": evaluation.match_score,
        "category_scores": evaluation.category_scores,
        "summary": evaluation.summary,
        "pros": evaluation.pros,
        "cons": evaluation.cons,
        "created_at": evaluation.created_at
    }


@router.delete("/{candidate_id}", status_code=204)
def delete_candidate(
    job_id: int,
    candidate_id: int,
    db: Session = Depends(get_db)
):
    """
    Delete a candidate and their resume file.

    Args:
        job_id: The job posting ID
        candidate_id: The candidate ID to delete

    Raises:
        HTTPException 404: If candidate not found
    """
    candidate = db.query(Candidate).filter(
        Candidate.id == candidate_id,
        Candidate.job_id == job_id
    ).first()

    if not candidate:
        raise HTTPException(
            status_code=404,
            detail=f"Candidate {candidate_id} not found for job {job_id}"
        )

    # Delete file from storage
    if os.path.exists(candidate.file_path):
        try:
            os.remove(candidate.file_path)
            logger.info(f"Deleted resume file: {candidate.file_path}")
        except Exception as e:
            logger.error(f"Failed to delete file {candidate.file_path}: {e}")
            # Continue with database deletion even if file deletion fails

    # Delete database record
    db.delete(candidate)
    db.commit()
    logger.info(f"Deleted candidate {candidate_id}")

    return None
