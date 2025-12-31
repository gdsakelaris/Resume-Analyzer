import json
import logging
from typing import Dict
from openai import AsyncOpenAI
import asyncio
from app.schemas.job import JobConfigSchema, JobCategory
from app.core.config import settings

logger = logging.getLogger(__name__)


class JobConfigGenerationError(Exception):
    """Custom exception for job config generation errors"""
    pass


def _get_schema_example() -> str:
    """Generate a JSON schema example for the AI to follow"""
    return """
{
  "title": "Senior Backend Engineer",
  "seniority_level": "Senior",
  "role_summary": "Lead backend development for scalable microservices...",
  "core_responsibilities": [
    "Design and implement RESTful APIs",
    "Optimize database queries and schema design"
  ],
  "categories": [
    {
      "category_id": "backend_dev",
      "name": "Backend Development",
      "importance": 5,
      "description": "Core backend programming skills",
      "examples_of_evidence": [
        "Built RESTful APIs with Python/FastAPI",
        "Designed microservices architecture"
      ]
    }
  ],
  "desired_background_patterns": {
    "years_experience": "5+",
    "industries": ["SaaS", "FinTech"]
  },
  "education_preferences": {
    "required_degree": "Bachelor's in Computer Science or equivalent",
    "preferred_fields": ["Computer Science", "Software Engineering"],
    "certifications": ["AWS Certified", "Kubernetes"]
  }
}
"""


async def generate_job_config(job_title: str, job_description: str, max_retries: int = 3) -> Dict:
    """
    Uses LLM to analyze job description and return a structured JobConfig.
    Implements retry logic with exponential backoff.

    Args:
        job_title: The job title
        job_description: Full job description text
        max_retries: Maximum number of retry attempts (default: 3)

    Returns:
        Dictionary containing the validated job configuration

    Raises:
        JobConfigGenerationError: If AI generation or validation fails after all retries
    """

    system_prompt = f"""You are an expert Technical Recruiter and AI Architect.
Your goal is to analyze a job description and break it down into a structured
configuration for a resume-scoring algorithm.

IMPORTANT INSTRUCTIONS:
1. Create 4-8 distinct skill categories (e.g., 'Cloud Platforms', 'Backend Development', 'Database Management')
2. Assign an importance score (1-5) to each category where:
   - 5 = Critical/Must-have skill
   - 4 = Very important
   - 3 = Important
   - 2 = Nice to have
   - 1 = Bonus/Optional
3. For each category, provide 3-5 concrete examples of evidence that would demonstrate competence
4. Identify the seniority level (Entry, Mid, Senior, Staff, Principal, etc.)
5. Extract core responsibilities as a bulleted list
6. Identify desired background patterns (years of experience, specific industries, etc.)
7. Note education preferences (required degree, preferred fields, etc.)

Return ONLY valid JSON matching this exact structure:
{_get_schema_example()}"""

    user_prompt = f"""Analyze this job posting and generate a structured configuration:

JOB TITLE: {job_title}

JOB DESCRIPTION:
{job_description}

Generate the JSON configuration following the exact schema structure provided."""

    # Initialize OpenAI client
    client = AsyncOpenAI(api_key=settings.OPENAI_API_KEY)

    # Retry loop with exponential backoff
    for attempt in range(max_retries):
        try:
            # Call OpenAI API with JSON mode
            response = await client.chat.completions.create(
                model=settings.OPENAI_MODEL,
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_prompt}
                ],
                response_format={"type": "json_object"},
                temperature=settings.OPENAI_TEMPERATURE
            )

            # Extract and parse response
            content = response.choices[0].message.content
            if not content:
                raise JobConfigGenerationError("Empty response from OpenAI")

            config_data = json.loads(content)

            # Validate against Pydantic schema
            validated_config = JobConfigSchema(**config_data)

            logger.info(f"Successfully generated job config for: {job_title}")
            return validated_config.model_dump()

        except json.JSONDecodeError as e:
            logger.warning(f"Attempt {attempt + 1}/{max_retries}: Failed to parse JSON: {e}")
            if attempt == max_retries - 1:
                raise JobConfigGenerationError(f"Invalid JSON after {max_retries} attempts: {e}")

        except Exception as e:
            logger.warning(f"Attempt {attempt + 1}/{max_retries}: Generation error: {e}")
            if attempt == max_retries - 1:
                raise JobConfigGenerationError(f"Failed after {max_retries} attempts: {e}")

        # Exponential backoff: wait 1s, 2s, 4s between retries
        if attempt < max_retries - 1:
            wait_time = 2 ** attempt
            logger.info(f"Retrying in {wait_time} seconds...")
            await asyncio.sleep(wait_time)

    raise JobConfigGenerationError(f"Failed to generate config after {max_retries} attempts")
