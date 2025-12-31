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
from app.core.celery_app import celery_app
from app.core.database import SessionLocal
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
        # In production with S3, you would:
        # 1. Download file from S3 to temp location
        # 2. Process it
        # 3. Delete temp file
        # For now, we read from the local shared volume.
        file_path = candidate.file_path

        if not os.path.exists(file_path):
            raise FileNotFoundError(f"Resume file not found at {file_path}")

        # Determine file type from extension
        file_ext = os.path.splitext(file_path)[1].lower()
        extracted_text = ""

        if file_ext == ".pdf":
            # Extract from PDF using pdfplumber
            with pdfplumber.open(file_path) as pdf:
                for page_num, page in enumerate(pdf.pages, 1):
                    text = page.extract_text()
                    if text:
                        extracted_text += text + "\n"
                        logger.debug(f"[Task {self.request.id}] Extracted {len(text)} chars from page {page_num}")

        elif file_ext == ".docx":
            # Extract from DOCX using docx2txt (simpler than python-docx)
            extracted_text = docx2txt.process(file_path)
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
