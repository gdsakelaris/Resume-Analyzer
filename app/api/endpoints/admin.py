"""
Admin API endpoints for database management.

SECURITY WARNING: These endpoints should only be accessible to superuser/admin accounts.
In production, implement proper role-based access control (RBAC).
"""

import logging
from typing import List
from uuid import UUID
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from sqlalchemy import func
from app.core.database import get_db
from app.core.deps import get_admin_user
from app.models.user import User
from app.models.job import Job
from app.models.candidate import Candidate
from app.models.evaluation import Evaluation
from app.models.subscription import Subscription
from app.core.storage import storage

router = APIRouter(prefix="/admin", tags=["Admin"])
logger = logging.getLogger(__name__)


@router.get("/users")
def list_all_users(
    db: Session = Depends(get_db),
    admin_user: User = Depends(get_admin_user)
):
    """List all users in the system."""
    users = db.query(User).all()
    return [{
        "id": u.id,
        "email": u.email,
        "tenant_id": str(u.tenant_id),
        "is_verified": u.is_verified,
        "created_at": u.created_at
    } for u in users]


@router.delete("/users/{user_id}")
def delete_user(
    user_id: UUID,
    db: Session = Depends(get_db),
    admin_user: User = Depends(get_admin_user)
):
    """
    Delete a user and all associated data (jobs, candidates, subscriptions).

    This is a CASCADE delete operation.
    """
    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")

    # SQLAlchemy will handle cascade deletes based on relationship definitions
    db.delete(user)
    db.commit()
    logger.info(f"Admin deleted user {user_id}")
    return {"message": f"User {user_id} deleted successfully"}


@router.get("/subscriptions")
def list_all_subscriptions(
    db: Session = Depends(get_db),
    admin_user: User = Depends(get_admin_user)
):
    """List all subscriptions in the system."""
    subscriptions = db.query(Subscription).all()
    return [{
        "id": s.id,
        "user_id": s.user_id,
        "plan": s.plan.value,
        "status": s.status.value,
        "candidates_used_this_month": s.candidates_used_this_month,
        "monthly_candidate_limit": s.monthly_candidate_limit,
        "current_period_end": s.current_period_end
    } for s in subscriptions]


@router.delete("/subscriptions/{subscription_id}")
def delete_subscription(
    subscription_id: UUID,
    db: Session = Depends(get_db),
    admin_user: User = Depends(get_admin_user)
):
    """Delete a subscription."""
    subscription = db.query(Subscription).filter(Subscription.id == subscription_id).first()
    if not subscription:
        raise HTTPException(status_code=404, detail="Subscription not found")

    db.delete(subscription)
    db.commit()
    logger.info(f"Admin deleted subscription {subscription_id}")
    return {"message": f"Subscription {subscription_id} deleted successfully"}


@router.post("/subscriptions/{subscription_id}/reset-usage")
def reset_subscription_usage(
    subscription_id: UUID,
    db: Session = Depends(get_db),
    admin_user: User = Depends(get_admin_user)
):
    """Reset the usage counter for a specific subscription."""
    subscription = db.query(Subscription).filter(Subscription.id == subscription_id).first()
    if not subscription:
        raise HTTPException(status_code=404, detail="Subscription not found")

    subscription.candidates_used_this_month = 0
    db.commit()
    logger.info(f"Admin reset usage for subscription {subscription_id}")
    return {"message": f"Usage reset for subscription {subscription_id}"}


@router.post("/subscriptions/reset-all-usage")
def reset_all_subscription_usage(
    db: Session = Depends(get_db),
    admin_user: User = Depends(get_admin_user)
):
    """Reset usage counters for ALL subscriptions."""
    count = db.query(Subscription).update({"candidates_used_this_month": 0})
    db.commit()
    logger.info(f"Admin reset usage for {count} subscriptions")
    return {"message": f"Reset usage for {count} subscriptions"}


@router.get("/jobs")
def list_all_jobs(
    db: Session = Depends(get_db),
    admin_user: User = Depends(get_admin_user)
):
    """List all jobs across all tenants."""
    jobs = db.query(Job).all()
    return [{
        "id": j.id,
        "tenant_id": str(j.tenant_id),
        "title": j.title,
        "description": j.description[:100] + "..." if len(j.description) > 100 else j.description,
        "status": j.status.value,
        "created_at": j.created_at
    } for j in jobs]


@router.delete("/jobs/{job_id}")
def delete_job(
    job_id: UUID,
    db: Session = Depends(get_db),
    admin_user: User = Depends(get_admin_user)
):
    """Delete a job and all its candidates (cascade)."""
    job = db.query(Job).filter(Job.id == job_id).first()
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")

    # Get all candidates for this job to delete their files
    candidates = db.query(Candidate).filter(Candidate.job_id == job_id).all()

    # Delete files from storage
    for candidate in candidates:
        try:
            storage.delete_file(candidate.file_path)
            logger.info(f"Deleted file {candidate.file_path}")
        except Exception as e:
            logger.error(f"Failed to delete file {candidate.file_path}: {e}")

    # Delete job (candidates will be cascade deleted)
    db.delete(job)
    db.commit()
    logger.info(f"Admin deleted job {job_id}")
    return {"message": f"Job {job_id} and {len(candidates)} candidates deleted successfully"}


@router.delete("/jobs/delete-all")
def delete_all_jobs(
    db: Session = Depends(get_db),
    admin_user: User = Depends(get_admin_user)
):
    """
    DANGER: Delete ALL jobs and candidates from ALL tenants.
    Use with extreme caution!
    """
    # Get all candidates to delete their files
    candidates = db.query(Candidate).all()

    # Delete files from storage
    for candidate in candidates:
        try:
            storage.delete_file(candidate.file_path)
        except Exception as e:
            logger.error(f"Failed to delete file {candidate.file_path}: {e}")

    # Delete all jobs (cascade will handle candidates and evaluations)
    count = db.query(Job).delete()
    db.commit()
    logger.warning(f"Admin deleted ALL {count} jobs")
    return {"message": f"Deleted {count} jobs and {len(candidates)} candidates"}


@router.get("/candidates")
def list_all_candidates(
    db: Session = Depends(get_db),
    admin_user: User = Depends(get_admin_user)
):
    """List all candidates across all tenants."""
    candidates = db.query(Candidate).all()
    return [{
        "id": c.id,
        "job_id": c.job_id,
        "tenant_id": str(c.tenant_id),
        "original_filename": c.original_filename,
        "email": c.email,
        "status": c.status.value,
        "created_at": c.created_at
    } for c in candidates]


@router.delete("/candidates/{candidate_id}")
def delete_candidate_admin(
    candidate_id: UUID,
    db: Session = Depends(get_db),
    admin_user: User = Depends(get_admin_user)
):
    """
    Delete a candidate (admin version - bypasses tenant checks).

    This properly handles:
    - Deleting the evaluation first (foreign key constraint)
    - Deleting the candidate
    - Deleting the file from storage
    """
    candidate = db.query(Candidate).filter(Candidate.id == candidate_id).first()
    if not candidate:
        raise HTTPException(status_code=404, detail="Candidate not found")

    # Delete evaluation first (foreign key constraint)
    evaluation = db.query(Evaluation).filter(Evaluation.candidate_id == candidate_id).first()
    if evaluation:
        db.delete(evaluation)
        logger.info(f"Deleted evaluation for candidate {candidate_id}")

    # Delete file from storage
    try:
        storage.delete_file(candidate.file_path)
        logger.info(f"Deleted file {candidate.file_path}")
    except Exception as e:
        logger.error(f"Failed to delete file {candidate.file_path}: {e}")

    # Delete candidate
    db.delete(candidate)
    db.commit()
    logger.info(f"Admin deleted candidate {candidate_id}")
    return {"message": f"Candidate {candidate_id} deleted successfully"}


@router.delete("/candidates/delete-all")
def delete_all_candidates(
    db: Session = Depends(get_db),
    admin_user: User = Depends(get_admin_user)
):
    """
    DANGER: Delete ALL candidates from ALL tenants.
    Use with extreme caution!
    """
    # Get all candidates to delete their files
    candidates = db.query(Candidate).all()

    # Delete all evaluations first (foreign key constraint)
    eval_count = db.query(Evaluation).delete()

    # Delete files from storage
    for candidate in candidates:
        try:
            storage.delete_file(candidate.file_path)
        except Exception as e:
            logger.error(f"Failed to delete file {candidate.file_path}: {e}")

    # Delete all candidates
    candidate_count = db.query(Candidate).delete()
    db.commit()
    logger.warning(f"Admin deleted ALL {candidate_count} candidates and {eval_count} evaluations")
    return {"message": f"Deleted {candidate_count} candidates and {eval_count} evaluations"}


@router.get("/evaluations")
def list_all_evaluations(
    db: Session = Depends(get_db),
    admin_user: User = Depends(get_admin_user)
):
    """List all evaluations across all tenants."""
    evaluations = db.query(Evaluation).all()
    return [{
        "id": e.id,
        "candidate_id": e.candidate_id,
        "tenant_id": str(e.tenant_id),
        "match_score": e.match_score,
        "created_at": e.created_at
    } for e in evaluations]


@router.delete("/evaluations/{evaluation_id}")
def delete_evaluation(
    evaluation_id: UUID,
    db: Session = Depends(get_db),
    admin_user: User = Depends(get_admin_user)
):
    """Delete an evaluation."""
    evaluation = db.query(Evaluation).filter(Evaluation.id == evaluation_id).first()
    if not evaluation:
        raise HTTPException(status_code=404, detail="Evaluation not found")

    db.delete(evaluation)
    db.commit()
    logger.info(f"Admin deleted evaluation {evaluation_id}")
    return {"message": f"Evaluation {evaluation_id} deleted successfully"}


@router.get("/stats")
def get_system_stats(
    db: Session = Depends(get_db),
    admin_user: User = Depends(get_admin_user)
):
    """Get system-wide statistics."""
    return {
        "total_users": db.query(func.count(User.id)).scalar(),
        "total_jobs": db.query(func.count(Job.id)).scalar(),
        "total_candidates": db.query(func.count(Candidate.id)).scalar(),
        "total_evaluations": db.query(func.count(Evaluation.id)).scalar(),
        "total_subscriptions": db.query(func.count(Subscription.id)).scalar(),
        "active_subscriptions": db.query(func.count(Subscription.id)).filter(
            Subscription.status == "active"
        ).scalar()
    }
