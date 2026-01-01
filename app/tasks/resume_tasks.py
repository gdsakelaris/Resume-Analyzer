"""
Starscreen Resume Parsing Engine.

This module handles the first stage of the Starscreen processing pipeline:
1. Document text extraction from PDF, DOC, and DOCX files (parse_resume_task)
2. Chains to AI scoring task (scoring_tasks.score_candidate_task)

Supported formats:
- PDF: Parsed with pdfplumber
- DOCX: Parsed with python-docx and docx2txt
- DOC: Legacy format - users should convert to DOCX or PDF

Future enhancements:
- PII anonymization for blind screening
- Structured data extraction (skills, experience, education)
"""

import logging
import pdfplumber
import docx
import docx2txt
import os
import tempfile
from io import BytesIO
from app.core.celery_app import celery_app
from app.core.database import SessionLocal
from app.core.storage import storage
from app.core.config import settings
from app.models.candidate import Candidate, CandidateStatus

logger = logging.getLogger(__name__)


@celery_app.task(name="app.tasks.resume_tasks.parse_resume_task", bind=True)
def parse_resume_task(self, candidate_id: int):
    """
    Starscreen Worker: Extract text from a candidate's resume (PDF, DOC, DOCX).

    This is the first stage in the Starscreen processing pipeline.
    After successful extraction, automatically chains to the AI scoring task.

    Supports:
    - PDF files (parsed with pdfplumber)
    - DOCX files (parsed with python-docx/docx2txt)
    - DOC files (legacy - prompts user to convert)

    Args:
        self: Celery task instance (when bind=True)
        candidate_id: The candidate ID to process

    Returns:
        dict: Processing result with status and extracted text length
    """
    logger.info(f"[Task {self.request.id}] Starscreen processing Candidate {candidate_id}")

    db = SessionLocal()

    try:
        # Get candidate and verify it exists
        candidate = db.query(Candidate).filter(Candidate.id == candidate_id).first()

        if not candidate:
            logger.error(f"[Task {self.request.id}] Candidate {candidate_id} not found")
            return {"status": "error", "message": "Candidate not found"}

        # Update status to PROCESSING
        candidate.status = CandidateStatus.PROCESSING
        db.commit()
        logger.info(f"[Task {self.request.id}] Candidate {candidate_id} status set to PROCESSING")

        # Extract text based on file format
        # If using S3, download file to temp location first
        # If using local storage, use file path directly
        file_path = candidate.file_path
        temp_file_path = None

        try:
            # Check if we need to download from S3
            if settings.USE_S3:
                # Download file from S3 to temporary location
                logger.info(f"[Task {self.request.id}] Downloading file from S3: {file_path}")
                file_data = storage.download_file(file_path)

                # Save to temporary file for processing
                file_ext = os.path.splitext(candidate.original_filename)[1]
                with tempfile.NamedTemporaryFile(delete=False, suffix=file_ext) as tmp_file:
                    tmp_file.write(file_data.getvalue())
                    temp_file_path = tmp_file.name

                # Use temp file for processing
                processing_path = temp_file_path
                logger.info(f"[Task {self.request.id}] Downloaded to temp file: {processing_path}")
            else:
                # Local storage - use file path directly
                if not os.path.exists(file_path):
                    raise FileNotFoundError(f"Resume file not found at {file_path}")
                processing_path = file_path

            # Determine file type from extension
            file_ext = os.path.splitext(candidate.original_filename)[1].lower()
            extracted_text = ""

            # DEFINITION: 25,000 chars is roughly 6-8 pages of text.
            # This limit optimizes token usage for OpenAI API calls while supporting comprehensive resumes.
            MAX_PAGES = 6
            MAX_CHARS = 25000

            if file_ext == ".pdf":
                # Extract from PDF using pdfplumber
                with pdfplumber.open(processing_path) as pdf:
                    # Enforce Page Limit
                    pages_to_parse = pdf.pages[:MAX_PAGES]

                    for page_num, page in enumerate(pages_to_parse, 1):
                        text = page.extract_text()
                        if text:
                            extracted_text += text + "\n"
                            # Stop if we exceed char limit even within allowed pages
                            if len(extracted_text) > MAX_CHARS:
                                extracted_text = extracted_text[:MAX_CHARS]
                                logger.info(f"[Task {self.request.id}] Truncated PDF at {MAX_CHARS} chars (page {page_num})")
                                break
                            logger.debug(f"[Task {self.request.id}] Extracted {len(text)} chars from page {page_num}")

            elif file_ext == ".docx":
                # Extract from DOCX using docx2txt (simpler than python-docx)
                full_text = docx2txt.process(processing_path)
                # Enforce Character Limit
                extracted_text = full_text[:MAX_CHARS]
                if len(full_text) > MAX_CHARS:
                    logger.info(f"[Task {self.request.id}] Truncated DOCX from {len(full_text)} to {MAX_CHARS} chars")
                logger.debug(f"[Task {self.request.id}] Extracted {len(extracted_text)} chars from DOCX")

            elif file_ext == ".doc":
                # Legacy .doc format not directly supported
                raise ValueError(
                    "Legacy .doc format is not supported. "
                    "Please convert your resume to .docx or .pdf format and upload again."
                )

            else:
                raise ValueError(f"Unsupported file format: {file_ext}. Only PDF, DOC, and DOCX are supported.")

            if not extracted_text.strip():
                raise ValueError(f"No text could be extracted from this {file_ext.upper()} file. The file may be corrupted or a scanned image.")

            # Save extracted text and update status
            candidate.resume_text = extracted_text
            candidate.status = CandidateStatus.PARSED
            candidate.error_message = None
            db.commit()

            logger.info(
                f"[Task {self.request.id}] Successfully extracted {len(extracted_text)} chars "
                f"for Candidate {candidate_id}"
            )

            # Chain to scoring task - Starscreen pipeline stage 2
            from app.tasks.scoring_tasks import score_candidate_task
            score_candidate_task.delay(candidate_id)
            logger.info(f"[Task {self.request.id}] Queued scoring task for Candidate {candidate_id}")

            return {
                "status": "success",
                "candidate_id": candidate_id,
                "text_length": len(extracted_text),
                "message": "Resume parsed successfully, scoring queued"
            }

        finally:
            # Clean up temp file if we downloaded from S3
            if temp_file_path and os.path.exists(temp_file_path):
                try:
                    os.remove(temp_file_path)
                    logger.info(f"[Task {self.request.id}] Cleaned up temp file: {temp_file_path}")
                except Exception as e:
                    logger.error(f"[Task {self.request.id}] Failed to clean up temp file: {e}")

    except FileNotFoundError as e:
        logger.error(f"[Task {self.request.id}] File not found: {e}")
        candidate.status = CandidateStatus.FAILED
        candidate.error_message = f"File not found: {str(e)}"
        db.commit()
        return {"status": "error", "message": str(e)}

    except ValueError as e:
        logger.error(f"[Task {self.request.id}] Parsing error: {e}")
        candidate.status = CandidateStatus.FAILED
        candidate.error_message = str(e)
        db.commit()
        return {"status": "error", "message": str(e)}

    except Exception as e:
        logger.error(f"[Task {self.request.id}] Unexpected error parsing resume: {e}")
        candidate.status = CandidateStatus.FAILED
        candidate.error_message = f"Unexpected error: {str(e)}"
        db.commit()
        return {"status": "error", "message": str(e)}

    finally:
        db.close()
