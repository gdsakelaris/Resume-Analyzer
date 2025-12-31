"""
Starscreen AI Scoring Engine.

This module contains Celery tasks for evaluating candidates against job requirements
using the OpenAI API. The scoring engine produces structured evaluations with:
- Overall match score (0-100)
- Category breakdowns (skills, experience, etc.)
- Narrative summaries (pros, cons, executive summary)
"""

from app.core.celery_app import celery_app
from app.core.database import SessionLocal
from app.models.candidate import Candidate, CandidateStatus
from app.models.evaluation import Evaluation
from app.models.job import Job
import logging
from openai import OpenAI
import os
import json

logger = logging.getLogger(__name__)
client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))


@celery_app.task(name="app.tasks.scoring_tasks.score_candidate_task", bind=True)
def score_candidate_task(self, candidate_id: int):
    """
    Starscreen Worker: Score a candidate against job requirements using AI.

    This is the second stage in the Starscreen processing pipeline.
    Runs after resume parsing is complete.

    Args:
        candidate_id: The ID of the candidate to score

    Returns:
        dict: Contains candidate_id and match_score

    Raises:
        ValueError: If candidate not found
        Exception: If AI scoring fails
    """
    db = SessionLocal()
    try:
        logger.info(f"[Task {self.request.id}] Starscreen scoring Candidate {candidate_id}")

        # Load candidate and job
        candidate = db.query(Candidate).filter(Candidate.id == candidate_id).first()
        if not candidate:
            raise ValueError(f"Candidate {candidate_id} not found")

        job = db.query(Job).filter(Job.id == candidate.job_id).first()

        # Get AI prompt from job config
        job_config = job.job_config or {}
        scoring_prompt = job_config.get(
            "scoring_prompt",
            "You are an expert recruiter. Evaluate candidates objectively and thoroughly."
        )

        # Call OpenAI to score the candidate
        logger.info(f"[Task {self.request.id}] Calling OpenAI API for candidate evaluation")
        response = client.chat.completions.create(
            model="gpt-4o",
            messages=[
                {"role": "system", "content": scoring_prompt},
                {"role": "user", "content": f"Job: {job.description}\n\nResume:\n{candidate.resume_text}"}
            ],
            response_format={
                "type": "json_schema",
                "json_schema": {
                    "name": "candidate_evaluation",
                    "strict": True,
                    "schema": {
                        "type": "object",
                        "properties": {
                            "match_score": {"type": "number"},
                            "category_scores": {
                                "type": "object",
                                "additionalProperties": {"type": "number"}
                            },
                            "summary": {"type": "string"},
                            "pros": {
                                "type": "array",
                                "items": {"type": "string"}
                            },
                            "cons": {
                                "type": "array",
                                "items": {"type": "string"}
                            }
                        },
                        "required": ["match_score", "category_scores", "summary", "pros", "cons"],
                        "additionalProperties": False
                    }
                }
            }
        )

        # Parse AI response
        result = response.choices[0].message.content
        data = json.loads(result)

        # Store evaluation in database
        evaluation = Evaluation(
            candidate_id=candidate.id,
            match_score=data["match_score"],
            category_scores=data["category_scores"],
            summary=data["summary"],
            pros=data["pros"],
            cons=data["cons"]
        )
        db.add(evaluation)

        # Update candidate status to SCORED
        candidate.status = CandidateStatus.SCORED

        db.commit()
        logger.info(f"[Task {self.request.id}] ✓ Candidate {candidate_id} scored: {data['match_score']}/100")

        return {
            "candidate_id": candidate_id,
            "match_score": data["match_score"]
        }

    except Exception as e:
        logger.error(f"[Task {self.request.id}] ✗ Failed to score Candidate {candidate_id}: {str(e)}")
        if candidate:
            candidate.status = CandidateStatus.FAILED
            candidate.error_message = f"Scoring failed: {str(e)}"
            db.commit()
        raise
    finally:
        db.close()
