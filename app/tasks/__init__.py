"""
Celery tasks package.

Tasks are organized by domain:
- job_tasks: Job processing and AI configuration generation
- resume_tasks: Resume parsing and analysis
- (future) notification_tasks: Email/SMS notifications
"""

from app.tasks import job_tasks, resume_tasks

__all__ = ["job_tasks", "resume_tasks"]
