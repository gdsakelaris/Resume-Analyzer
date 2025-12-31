"""
Celery tasks for resume processing.

These tasks handle the resume processing pipeline:
1. PDF text extraction (parse_resume_task)
2. PII anonymization (future)
3. AI-powered candidate scoring (future)
"""

import logging
import pdfplumber
import os
from app.core.celery_app import celery_app
from app.core.database import SessionLocal
from app.models.candidate import Candidate, CandidateStatus

logger = logging.getLogger(__name__)


@celery_app.task(name="app.tasks.resume_tasks.parse_resume_task", bind=True)
def parse_resume_task(self, candidate_id: int):
    """
    Starscreen Worker: Extract text from a candidate's resume PDF.

    This is the first stage in the Starscreen processing pipeline.
    Future enhancements:
    - PII redaction for blind screening
    - Structured data extraction (skills, experience, education)
    - Chain to candidate scoring task

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

        # Extract text from PDF
        # In production with S3, you would:
        # 1. Download file from S3 to temp location
        # 2. Process it
        # 3. Delete temp file
        # For now, we read from the local shared volume.
        file_path = candidate.file_path

        if not os.path.exists(file_path):
            raise FileNotFoundError(f"Resume file not found at {file_path}")

        extracted_text = ""
        with pdfplumber.open(file_path) as pdf:
            for page_num, page in enumerate(pdf.pages, 1):
                text = page.extract_text()
                if text:
                    extracted_text += text + "\n"
                    logger.debug(f"[Task {self.request.id}] Extracted {len(text)} chars from page {page_num}")

        if not extracted_text.strip():
            raise ValueError("No text could be extracted from this PDF. The file may be a scanned image.")

        # Save extracted text and update status
        candidate.resume_text = extracted_text
        candidate.status = CandidateStatus.PARSED
        candidate.error_message = None
        db.commit()

        logger.info(
            f"[Task {self.request.id}] Successfully extracted {len(extracted_text)} chars "
            f"for Candidate {candidate_id}"
        )

        # FUTURE: Chain next task in pipeline
        # from app.tasks.scoring_tasks import evaluate_candidate_task
        # evaluate_candidate_task.delay(candidate_id)

        return {
            "status": "success",
            "candidate_id": candidate_id,
            "text_length": len(extracted_text),
            "message": "Resume parsed successfully"
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
