"""
Celery tasks package.

Tasks are organized by domain:
- job_tasks: Job processing and AI configuration generation
- resume_tasks: Resume parsing and analysis
- scoring_tasks: AI-powered candidate scoring
- email_tasks: Email notifications (verification, etc.)
"""

from app.tasks import job_tasks, resume_tasks, scoring_tasks, email_tasks

__all__ = ["job_tasks", "resume_tasks", "scoring_tasks", "email_tasks"]
