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
from uuid import UUID as UUIDType
from fastapi import APIRouter, UploadFile, File, Form, Depends, HTTPException
from fastapi.responses import FileResponse, StreamingResponse
from sqlalchemy.orm import Session
from app.core.database import get_db
from app.core.deps import get_tenant_id, get_current_active_subscription
from app.core.storage import storage  # S3/Local storage abstraction
from app.core.api_rate_limiter import check_candidate_upload_rate_limit
from app.models.candidate import Candidate, CandidateStatus
from app.models.subscription import Subscription
from app.schemas.candidate import CandidateUploadResponse, CandidateResponse, CandidateListResponse
from app.tasks import resume_tasks

router = APIRouter(prefix="/jobs/{job_id}/candidates", tags=["Starscreen Candidates"])
logger = logging.getLogger(__name__)

# Upload directory configuration (for local storage fallback)
# In production with S3, this is not used
UPLOAD_DIR = "uploads"
os.makedirs(UPLOAD_DIR, exist_ok=True)


@router.post("/upload", response_model=CandidateUploadResponse)
async def upload_resume(
    job_id: int,
    file: UploadFile = File(...),
    first_name: Optional[str] = Form(None),
    last_name: Optional[str] = Form(None),
    email: Optional[str] = Form(None),
    db: Session = Depends(get_db),
    subscription: Subscription = Depends(get_current_active_subscription)
):
    """
    Upload a candidate's resume for a specific job.

    **Requires active subscription with available candidate slots.**

    This endpoint implements the competitive advantage strategy:
    - Accepts optional PII (first_name, last_name, email) for blind screening
    - Queues asynchronous processing to avoid blocking the user
    - Returns immediately with tracking ID
    - Enforces monthly candidate limits based on subscription plan

    Flow:
    1. Check subscription limits (FREE: 10/mo, STARTER: 100/mo, SMALL_BUSINESS: 1,000/mo, PROFESSIONAL: 5,000/mo)
    2. Validate file type (PDF, DOC, DOCX)
    3. Save file securely (UUID-based naming to prevent path traversal)
    4. Create database record with status=UPLOADED
    5. Increment usage counter
    6. Queue parsing task to Celery worker
    7. Return candidate_id for status tracking

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
        HTTPException 402: If monthly candidate limit reached
        HTTPException 404: If job doesn't exist
    """
    from app.models.job import Job

    # Derive tenant_id from the verified subscription
    tenant_id = subscription.user.tenant_id

    # 0. CHECK RATE LIMIT (prevent API abuse and cost explosions)
    check_candidate_upload_rate_limit(str(tenant_id))

    # 1. CHECK SUBSCRIPTION LIMIT (Priority check before file processing)
    if not subscription.can_upload_candidate:
        raise HTTPException(
            status_code=402,
            detail=f"Monthly candidate limit reached ({subscription.candidates_used_this_month}/{subscription.monthly_candidate_limit}). Please upgrade your plan or wait for next billing cycle."
        )

    # 2. Validate that the job exists AND belongs to the tenant (SECURITY: prevent cross-tenant attacks)
    job = db.query(Job).filter(Job.id == job_id, Job.tenant_id == tenant_id).first()
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

    # 3. Save file securely using storage backend (S3 or local)
    # This prevents:
    # - Path traversal attacks (../../etc/passwd)
    # - Filename collisions (UUID-based naming)
    # - Special character issues
    try:
        # Upload to storage backend (S3 or local filesystem)
        file_path = storage.upload_file(file.file, file.filename)
        logger.info(f"Saved resume to storage: {file_path}")
    except Exception as e:
        logger.error(f"Failed to save file: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to save file: {str(e)}")

    # 4. Create database entry (with tenant_id for multi-tenancy)
    candidate = Candidate(
        tenant_id=tenant_id,
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

        # 5. INCREMENT USAGE COUNTER (Track monthly candidate usage)
        subscription.candidates_used_this_month += 1
        db.commit()
        logger.info(
            f"Subscription usage: {subscription.candidates_used_this_month}/{subscription.monthly_candidate_limit} "
            f"({subscription.remaining_candidates} remaining)"
        )

    except Exception as e:
        # Clean up file if database insert fails
        try:
            storage.delete_file(file_path)
        except Exception as cleanup_error:
            logger.error(f"Failed to clean up file after database error: {cleanup_error}")
        logger.error(f"Failed to create candidate record: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to create candidate: {str(e)}")

    # 6. Queue parsing task to Celery worker via Redis
    task = resume_tasks.parse_resume_task.delay(candidate.id)
    logger.info(f"Queued parsing task {task.id} for candidate {candidate.id}")

    return {
        "candidate_id": candidate.id,
        "job_id": job_id,
        "status": CandidateStatus.UPLOADED.value,
        "task_id": task.id,
        "message": f"Resume uploaded successfully. Parsing queued to background worker. ({subscription.remaining_candidates} candidates remaining this month)"
    }


@router.post("/bulk-upload-zip")
async def bulk_upload_resumes(
    job_id: int,
    file: UploadFile = File(...),
    db: Session = Depends(get_db),
    subscription: Subscription = Depends(get_current_active_subscription)
):
    """
    Upload a ZIP file containing multiple resumes (PDF, DOC, DOCX).

    **Requires active subscription with sufficient candidate slots.**

    This is the KILLER FEATURE for B2B sales:
    - Recruiters export 50+ resumes as ZIP from LinkedIn/Greenhouse
    - They drag ONE file into your app
    - Your system processes all resumes automatically
    - Respects subscription limits (stops when limit reached)

    This solves the "manual friction" problem and makes the tool
    sellable to businesses who need to screen hundreds of candidates.

    Flow:
    1. Check subscription limits
    2. Validate ZIP file format
    3. Extract all resumes from ZIP (skip folders, non-resume files, __MACOSX)
    4. Create candidate record for each resume (up to subscription limit)
    5. Queue parsing task for each candidate
    6. Increment usage counter
    7. Return summary of processed candidates

    Args:
        job_id: The job posting ID these candidates are applying for
        file: ZIP archive containing resume files (PDF, DOC, DOCX)

    Returns:
        dict: Summary with count of processed candidates and job_id

    Raises:
        HTTPException 400: If file is not a ZIP
        HTTPException 402: If monthly candidate limit reached
        HTTPException 404: If job doesn't exist
        HTTPException 500: If extraction fails

    Example Response:
        {
            "message": "Bulk upload processed. 47 candidates created.",
            "job_id": 123,
            "processed_count": 47,
            "skipped_count": 3,
            "limit_reached": false,
            "remaining_candidates": 53
        }
    """
    from app.models.job import Job

    # Derive tenant_id from the verified subscription
    tenant_id = subscription.user.tenant_id

    # 1. CHECK SUBSCRIPTION LIMIT
    if not subscription.can_upload_candidate:
        raise HTTPException(
            status_code=402,
            detail=f"Monthly candidate limit reached ({subscription.candidates_used_this_month}/{subscription.monthly_candidate_limit}). Please upgrade your plan or wait for next billing cycle."
        )

    # 2. Validate that the job exists AND belongs to the tenant (SECURITY: prevent cross-tenant attacks)
    job = db.query(Job).filter(Job.id == job_id, Job.tenant_id == tenant_id).first()
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
    limit_reached = False

    # 4. Extract and process resume files from ZIP
    ALLOWED_EXTENSIONS = ('.pdf', '.doc', '.docx')
    try:
        with zipfile.ZipFile(zip_path, 'r') as zip_ref:
            for filename in zip_ref.namelist():
                # CHECK LIMIT BEFORE EACH FILE (stop processing if limit reached)
                if not subscription.can_upload_candidate:
                    logger.warning(
                        f"Subscription limit reached during bulk upload. "
                        f"Processed {processed_count} files, stopping."
                    )
                    limit_reached = True
                    break

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

                    # Upload to storage backend (S3 or local)
                    original_filename = os.path.basename(filename)
                    target_path = storage.upload_file(source, original_filename)

                    logger.info(f"Uploaded {filename} to storage: {target_path}")

                    # Create database entry for this candidate (with tenant_id)
                    candidate = Candidate(
                        tenant_id=tenant_id,
                        job_id=job_id,
                        original_filename=os.path.basename(filename),
                        file_path=target_path,
                        status=CandidateStatus.UPLOADED
                    )

                    db.add(candidate)
                    db.commit()
                    db.refresh(candidate)

                    # INCREMENT USAGE COUNTER for each processed candidate
                    subscription.candidates_used_this_month += 1
                    db.commit()

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
            f"{processed_count} processed, {skipped_count} skipped, "
            f"limit_reached={limit_reached}"
        )

        message = f"Bulk upload processed. {processed_count} candidates created."
        if limit_reached:
            message += f" Subscription limit reached ({subscription.monthly_candidate_limit}/month). Upgrade to process more candidates."

        return {
            "message": message,
            "job_id": job_id,
            "processed_count": processed_count,
            "skipped_count": skipped_count,
            "limit_reached": limit_reached,
            "remaining_candidates": subscription.remaining_candidates
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
    db: Session = Depends(get_db),
    tenant_id: UUIDType = Depends(get_tenant_id)
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
    # SECURITY: Filter by tenant_id to prevent cross-tenant access
    candidate = db.query(Candidate).filter(
        Candidate.id == candidate_id,
        Candidate.job_id == job_id,
        Candidate.tenant_id == tenant_id
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
    db: Session = Depends(get_db),
    tenant_id: UUIDType = Depends(get_tenant_id)
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

    # SECURITY: Filter by tenant_id to prevent cross-tenant access
    # Also filter out soft-deleted candidates (EEOC/OFCCP retention)
    query = db.query(Candidate).filter(
        Candidate.job_id == job_id,
        Candidate.tenant_id == tenant_id,
        Candidate.is_deleted == False  # Hide soft-deleted candidates
    )

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
    db: Session = Depends(get_db),
    tenant_id: UUIDType = Depends(get_tenant_id)
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
    # SECURITY: Filter by tenant_id to prevent file access across tenants
    candidate = db.query(Candidate).filter(
        Candidate.id == candidate_id,
        Candidate.job_id == job_id,
        Candidate.tenant_id == tenant_id
    ).first()

    if not candidate:
        raise HTTPException(
            status_code=404,
            detail=f"Candidate {candidate_id} not found for job {job_id}"
        )

    # Check if file exists in storage
    if not storage.file_exists(candidate.file_path):
        raise HTTPException(
            status_code=404,
            detail=f"Resume file not found for candidate {candidate_id}"
        )

    # For S3, stream file directly from memory (no temp file needed)
    # For local storage, file_path is already on disk
    from app.core.config import settings
    if settings.USE_S3:
        try:
            # Download from S3 to memory
            file_data = storage.download_file(candidate.file_path)

            # Determine content type
            file_ext = os.path.splitext(candidate.original_filename)[1].lower()
            content_type_map = {
                '.pdf': 'application/pdf',
                '.doc': 'application/msword',
                '.docx': 'application/vnd.openxmlformats-officedocument.wordprocessingml.document'
            }
            content_type = content_type_map.get(file_ext, 'application/octet-stream')

            # Reset BytesIO position to beginning
            file_data.seek(0)

            # Stream directly from memory - no temp file needed
            return StreamingResponse(
                file_data,
                media_type=content_type,
                headers={
                    'Content-Disposition': f'attachment; filename="{candidate.original_filename}"'
                }
            )
        except Exception as e:
            logger.error(f"Failed to download file from S3: {e}")
            raise HTTPException(status_code=500, detail="Failed to retrieve file from storage")
    else:
        # Local storage - file path is on disk
        return FileResponse(
            path=candidate.file_path,
            filename=candidate.original_filename,
            media_type="application/octet-stream"
        )


@router.get("/{candidate_id}/evaluation")
def get_candidate_evaluation(
    job_id: int,
    candidate_id: int,
    db: Session = Depends(get_db),
    tenant_id: UUIDType = Depends(get_tenant_id)
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

    # SECURITY: Filter by tenant_id
    candidate = db.query(Candidate).filter(
        Candidate.id == candidate_id,
        Candidate.job_id == job_id,
        Candidate.tenant_id == tenant_id
    ).first()

    if not candidate:
        raise HTTPException(
            status_code=404,
            detail=f"Candidate {candidate_id} not found for job {job_id}"
        )

    # SECURITY: Filter evaluation by tenant_id as well
    evaluation = db.query(Evaluation).filter(
        Evaluation.candidate_id == candidate_id,
        Evaluation.tenant_id == tenant_id
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
        "interview_questions": evaluation.interview_questions,
        "created_at": evaluation.created_at
    }


@router.delete("/{candidate_id}", status_code=204)
def delete_candidate(
    job_id: int,
    candidate_id: int,
    db: Session = Depends(get_db),
    tenant_id: UUIDType = Depends(get_tenant_id)
):
    """
    Soft delete a candidate (EEOC/OFCCP compliant).

    ⚠️ LEGAL COMPLIANCE: Federal law (EEOC/OFCCP) requires keeping employment
    records for 1-3 years. This endpoint implements soft delete to comply with
    record retention requirements.

    - Marks candidate as deleted (not visible in UI)
    - Retains all data for legal compliance
    - Files are NOT deleted from storage
    - Records auto-purge after retention period (configurable)

    Args:
        job_id: The job posting ID
        candidate_id: The candidate ID to delete

    Raises:
        HTTPException 404: If candidate not found
    """
    from app.core.config import settings
    from datetime import datetime, timedelta

    # SECURITY: Filter by tenant_id to prevent deletion across tenants
    candidate = db.query(Candidate).filter(
        Candidate.id == candidate_id,
        Candidate.job_id == job_id,
        Candidate.tenant_id == tenant_id,
        Candidate.is_deleted == False  # Only allow deleting non-deleted candidates
    ).first()

    if not candidate:
        raise HTTPException(
            status_code=404,
            detail=f"Candidate {candidate_id} not found for job {job_id}"
        )

    # SOFT DELETE: Mark as deleted instead of actually deleting
    if settings.ENABLE_SOFT_DELETE:
        candidate.is_deleted = True
        candidate.deleted_at = datetime.utcnow()
        # Calculate retention period (3 years by default for OFCCP compliance)
        candidate.retention_until = datetime.utcnow() + timedelta(days=settings.CANDIDATE_RETENTION_DAYS)

        db.commit()
        logger.info(
            f"Soft deleted candidate {candidate_id}. "
            f"Will be retained until {candidate.retention_until.date()} for legal compliance."
        )
    else:
        # HARD DELETE (not recommended - use only for development/testing)
        logger.warning(
            f"Hard delete requested for candidate {candidate_id}. "
            f"This may violate EEOC/OFCCP record retention requirements!"
        )

        # Delete file from storage (S3 or local)
        try:
            storage.delete_file(candidate.file_path)
            logger.info(f"Deleted resume file from storage: {candidate.file_path}")
        except Exception as e:
            logger.error(f"Failed to delete file {candidate.file_path}: {e}")

        # Delete database record
        db.delete(candidate)
        db.commit()
        logger.info(f"Hard deleted candidate {candidate_id}")

    return None
