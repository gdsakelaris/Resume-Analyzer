"""
Health check and monitoring endpoints.

Provides detailed health status for database, storage, and other dependencies.
"""

import logging
from typing import Dict, Any
from fastapi import APIRouter, Depends, status
from sqlalchemy.orm import Session
from sqlalchemy import text
from datetime import datetime

from app.core.database import get_db
from app.core.storage import storage

router = APIRouter(tags=["Health"])
logger = logging.getLogger(__name__)


@router.get("/health", status_code=status.HTTP_200_OK)
async def health_check() -> Dict[str, str]:
    """
    Basic health check endpoint.

    Returns 200 OK if the service is running.
    Use this for simple uptime monitoring and load balancer health checks.
    """
    return {
        "status": "healthy",
        "timestamp": datetime.utcnow().isoformat() + "Z"
    }


@router.get("/health/detailed", status_code=status.HTTP_200_OK)
async def detailed_health_check(db: Session = Depends(get_db)) -> Dict[str, Any]:
    """
    Detailed health check with dependency status.

    Checks:
    - Database connectivity
    - Storage (S3) availability
    - Service uptime

    Returns 200 if all systems operational, with detailed status for each component.
    """
    health_status = {
        "status": "healthy",
        "timestamp": datetime.utcnow().isoformat() + "Z",
        "checks": {}
    }

    # Check database connectivity
    try:
        db.execute(text("SELECT 1"))
        health_status["checks"]["database"] = {
            "status": "healthy",
            "message": "Database connection successful"
        }
    except Exception as e:
        logger.error(f"Database health check failed: {e}")
        health_status["status"] = "unhealthy"
        health_status["checks"]["database"] = {
            "status": "unhealthy",
            "message": f"Database error: {str(e)}"
        }

    # Check S3 storage availability
    try:
        # Simple check - attempt to list bucket (with max 1 item)
        # This validates credentials and bucket access
        storage.s3_client.list_objects_v2(
            Bucket=storage.bucket_name,
            MaxKeys=1
        )
        health_status["checks"]["storage"] = {
            "status": "healthy",
            "message": "S3 storage accessible"
        }
    except Exception as e:
        logger.error(f"Storage health check failed: {e}")
        health_status["status"] = "unhealthy"
        health_status["checks"]["storage"] = {
            "status": "unhealthy",
            "message": f"Storage error: {str(e)}"
        }

    return health_status


@router.get("/metrics", status_code=status.HTTP_200_OK)
async def get_metrics(db: Session = Depends(get_db)) -> Dict[str, Any]:
    """
    Application metrics endpoint.

    Returns basic operational metrics:
    - Total users
    - Active subscriptions
    - Jobs and candidates processed

    Note: For production, consider using Prometheus metrics format
    and integrating with a monitoring system like Grafana.
    """
    from sqlalchemy import func
    from app.models.user import User
    from app.models.job import Job
    from app.models.candidate import Candidate
    from app.models.subscription import Subscription

    try:
        metrics = {
            "timestamp": datetime.utcnow().isoformat() + "Z",
            "metrics": {
                "total_users": db.query(func.count(User.id)).scalar() or 0,
                "verified_users": db.query(func.count(User.id)).filter(User.is_verified == True).scalar() or 0,
                "total_jobs": db.query(func.count(Job.id)).scalar() or 0,
                "total_candidates": db.query(func.count(Candidate.id)).scalar() or 0,
                "active_subscriptions": db.query(func.count(Subscription.id)).filter(
                    Subscription.status == "active"
                ).scalar() or 0,
            }
        }

        return metrics
    except Exception as e:
        logger.error(f"Failed to retrieve metrics: {e}")
        return {
            "error": "Failed to retrieve metrics",
            "message": str(e)
        }
