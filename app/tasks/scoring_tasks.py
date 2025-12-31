"""
Starscreen Hybrid Scoring Engine - AI Judgment + Python Math.

This module implements a fundamentally superior scoring system that:
- AI: Uses Chain-of-Thought reasoning to GRADE competence (0-100) per category
- Python: Calculates deterministic weighted scores based on importance
- Values projects, volunteer work, and implicit signals (not just keywords)
- Detects keyword stuffing and prioritizes evidence of actual competence
- Provides detailed reasoning for each category score

Why Hybrid?
- AI is excellent at semantic judgment but terrible at weighted math
- AI often hallucinates calculations like (80*5 + 90*1) / 6 = 82 (wrong!)
- Python ensures the importance weights from job_config are respected
- Users can trust the final score is mathematically correct

This is what makes Starscreen superior to traditional ATS keyword matching.
"""

from app.core.celery_app import celery_app
from app.core.database import SessionLocal
from app.models.candidate import Candidate, CandidateStatus
from app.models.evaluation import Evaluation
from app.models.job import Job
import logging
from openai import OpenAI
from app.core.config import settings
import json

logger = logging.getLogger(__name__)
client = OpenAI(api_key=settings.OPENAI_API_KEY)


@celery_app.task(name="app.tasks.scoring_tasks.score_candidate_task", bind=True)
def score_candidate_task(self, candidate_id: int):
    """
    Hybrid Scoring Engine: AI Judgment + Python Math.

    Architecture:
    1. AI: Grades each category (0-100) based on semantic evidence
    2. Python: Calculates weighted average using importance from job_config

    This prevents AI from hallucinating weighted math while maintaining
    semantic understanding for inferring skills from context.

    Flow:
    - AI analyzes resume and grades categories
    - Python multiplies each score by its importance weight
    - Python calculates final score = sum(score*importance) / sum(importance)

    Args:
        candidate_id: The ID of the candidate to score

    Returns:
        dict: Contains candidate_id and mathematically correct match_score

    Raises:
        ValueError: If candidate not found
        Exception: If AI scoring fails
    """
    db = SessionLocal()
    try:
        logger.info(f"[Task {self.request.id}] Hybrid scoring for Candidate {candidate_id}")

        # Load candidate and job
        candidate = db.query(Candidate).filter(Candidate.id == candidate_id).first()
        if not candidate:
            raise ValueError(f"Candidate {candidate_id} not found")

        job = db.query(Job).filter(Job.id == candidate.job_id).first()
        if not job:
            raise ValueError(f"Job {candidate.job_id} not found")

        # Extract job configuration
        job_config = job.job_config or {}
        categories = job_config.get("categories", [])

        if not categories:
            logger.warning(f"[Task {self.request.id}] No categories found in job config, using default scoring")

        # Build AI prompt - Focus ONLY on grading, NOT on math
        prompt = f"""You are a Principal Engineer and expert Hiring Manager.
Your goal is to GRADE a candidate's competence for each skill category.

CRITICAL INSTRUCTIONS:
1. **Analyze Full Context:** Look at the candidate's [Projects], [Experience], [Education], [Certifications], and [Skills] sections.
2. **Explicit Skills Check:** If a skill is listed in the 'Skills' section (e.g., 'C#', 'AWS'), the candidate HAS that skill. Do not say "no experience" if it is listed.
   - If listed in 'Skills' but not used in projects: Score 30-50 (Knowledgeable).
   - If used in 'Projects' or 'Experience': Score 60-100 (Competent to Expert).
3. **Infer from Projects:**
   - "Built Django app" → They know Python (even if not explicitly listed)
   - "Led student group" → Leadership skills
4. **Keyword Stuffing:** If a skill appears ONLY in a list with 50 other keywords and is totally irrelevant to their actual work, discount it slightly, but acknowledge they claimed it.

GRADING SCALE:
- 0-20: No evidence found anywhere.
- 21-50: Listed in 'Skills' section or implied by education, but no direct project usage.
- 51-75: Competent. Used in at least one project or role.
- 76-90: Strong match. Multiple projects, years of experience, or clear impact.
- 91-100: Exceptional. Lead architect, complex implementations, or major achievements.

--------------------------------------------------------
JOB CONFIGURATION (Categories to Grade):
{json.dumps(job_config, indent=2)}

JOB DESCRIPTION:
{job.description}

--------------------------------------------------------
CANDIDATE RESUME:
{candidate.resume_text}

--------------------------------------------------------
YOUR TASK:
For EACH category in the Job Configuration, assign a competence_score (0-100).
Cite specific evidence from the resume in your reasoning.

Output strictly valid JSON:
{{
    "summary": "3-4 sentence professional assessment of overall fit",
    "category_scores": {{
        "Exact Category Name From Config": {{
            "score": (integer 0-100),
            "reasoning": "1-2 sentences citing specific evidence from resume"
        }}
    }},
    "pros": ["specific strength 1", "specific strength 2"],
    "cons": ["specific gap 1", "specific gap 2"]
}}

IMPORTANT: Do NOT include a "match_score" field. Python will calculate that.
"""

        # Call OpenAI
        logger.info(f"[Task {self.request.id}] Calling OpenAI for category grading")
        response = client.chat.completions.create(
            model="gpt-4o",
            messages=[
                {"role": "system", "content": "You are a fair, rigorous evaluator. You grade competence but do NOT calculate weighted scores."},
                {"role": "user", "content": prompt}
            ],
            response_format={"type": "json_object"},
            temperature=0.0  # Deterministic grading
        )

        # Parse AI response
        result = response.choices[0].message.content
        ai_result = json.loads(result)

        logger.info(f"[Task {self.request.id}] AI grading complete, calculating weighted score...")

        # ============================================================
        # PYTHON DOES THE MATH (Deterministic Weighted Scoring)
        # ============================================================

        total_weighted_score = 0.0
        total_importance = 0

        ai_scores = ai_result.get("category_scores", {})

        # Loop through job_config categories (source of truth for importance weights)
        for category in categories:
            cat_name = category.get("name", "")
            importance = category.get("importance", 1)  # Default importance = 1

            # Find the AI's grade for this category (case-insensitive match)
            ai_cat_data = None

            # Try exact match first
            if cat_name in ai_scores:
                ai_cat_data = ai_scores[cat_name]
            else:
                # Try case-insensitive match
                for key, val in ai_scores.items():
                    if key.lower() == cat_name.lower():
                        ai_cat_data = val
                        break

            # Extract score (default to 0 if AI missed this category)
            if ai_cat_data and isinstance(ai_cat_data, dict):
                score = ai_cat_data.get("score", 0)
            else:
                score = 0
                logger.warning(f"[Task {self.request.id}] AI did not grade category '{cat_name}', defaulting to 0")

            # Weighted math: score * importance
            weighted_contribution = score * importance
            total_weighted_score += weighted_contribution
            total_importance += importance

            logger.debug(f"[Task {self.request.id}] {cat_name}: score={score}, importance={importance}, weighted={weighted_contribution}")

        # Calculate final weighted average
        if total_importance > 0:
            final_match_score = round(total_weighted_score / total_importance, 1)
        else:
            final_match_score = 0
            logger.warning(f"[Task {self.request.id}] Total importance is 0, setting match_score to 0")

        logger.info(f"[Task {self.request.id}] Final weighted score: {final_match_score}/100 (weighted by importance)")

        # ============================================================
        # Save Evaluation to Database
        # ============================================================

        # Check if evaluation already exists (for idempotency)
        existing_eval = db.query(Evaluation).filter(Evaluation.candidate_id == candidate.id).first()
        if existing_eval:
            logger.info(f"[Task {self.request.id}] Replacing existing evaluation for Candidate {candidate_id}")
            db.delete(existing_eval)
            db.commit()

        # Store evaluation with Python-calculated score
        evaluation = Evaluation(
            candidate_id=candidate.id,
            match_score=final_match_score,  # Python-calculated weighted score
            category_scores=ai_result["category_scores"],  # AI's grades + reasoning
            summary=ai_result["summary"],
            pros=ai_result["pros"],
            cons=ai_result["cons"]
        )
        db.add(evaluation)

        # Update candidate status to SCORED
        candidate.status = CandidateStatus.SCORED
        candidate.error_message = None

        db.commit()
        logger.info(f"[Task {self.request.id}] ✓ Candidate {candidate_id} scored: {final_match_score}/100 (hybrid: AI grading + Python math)")

        return {
            "candidate_id": candidate_id,
            "match_score": final_match_score
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