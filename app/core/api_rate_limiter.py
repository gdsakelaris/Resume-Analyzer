"""
API-wide rate limiting middleware.

Implements per-workspace and per-IP rate limiting to prevent API abuse.
"""

import logging
from typing import Optional
from fastapi import Request, HTTPException, status
from app.core.rate_limiter import rate_limiter

logger = logging.getLogger(__name__)


def check_workspace_rate_limit(tenant_id: str, endpoint: str = "api") -> None:
    """
    Check rate limit for a specific workspace (tenant).

    Limit: 100 requests per minute per workspace.
    This prevents a single workspace from overwhelming the API.

    Args:
        tenant_id: The tenant/workspace UUID
        endpoint: Optional endpoint identifier for more granular limits

    Raises:
        HTTPException: 429 if rate limit exceeded
    """
    rate_limiter.check_rate_limit(
        key=f"workspace:{tenant_id}:{endpoint}",
        max_requests=100,
        window_seconds=60,
        error_message="Workspace API rate limit exceeded"
    )


def check_ip_rate_limit(ip_address: str, endpoint: str = "api") -> None:
    """
    Check rate limit for a specific IP address.

    Limit: 300 requests per minute per IP.
    This prevents DDoS attacks and API abuse from a single source.

    Args:
        ip_address: Client IP address
        endpoint: Optional endpoint identifier for more granular limits

    Raises:
        HTTPException: 429 if rate limit exceeded
    """
    rate_limiter.check_rate_limit(
        key=f"ip:{ip_address}:{endpoint}",
        max_requests=300,
        window_seconds=60,
        error_message="IP rate limit exceeded. Too many requests from your IP address"
    )


def check_candidate_upload_rate_limit(tenant_id: str) -> None:
    """
    Check rate limit for candidate uploads.

    Limit: 50 uploads per minute per workspace.
    This prevents abuse of the expensive AI scoring endpoint.

    Args:
        tenant_id: The tenant/workspace UUID

    Raises:
        HTTPException: 429 if rate limit exceeded
    """
    rate_limiter.check_rate_limit(
        key=f"upload:{tenant_id}",
        max_requests=50,
        window_seconds=60,
        error_message="Too many candidate uploads. Please wait before uploading more resumes"
    )


def check_openai_rate_limit(tenant_id: str) -> None:
    """
    Check rate limit for OpenAI API calls.

    Limit: 100 calls per minute per workspace.
    This prevents cost explosions from runaway API usage.

    Args:
        tenant_id: The tenant/workspace UUID

    Raises:
        HTTPException: 429 if rate limit exceeded
    """
    rate_limiter.check_rate_limit(
        key=f"openai:{tenant_id}",
        max_requests=100,
        window_seconds=60,
        error_message="AI processing rate limit exceeded. Please wait before processing more candidates"
    )


def get_client_ip(request: Request) -> str:
    """
    Extract the client's IP address from the request.

    Handles X-Forwarded-For header for proxied requests.

    Args:
        request: FastAPI request object

    Returns:
        Client IP address as string
    """
    # Check for X-Forwarded-For header (when behind proxy/load balancer)
    forwarded_for = request.headers.get("X-Forwarded-For")
    if forwarded_for:
        # X-Forwarded-For can contain multiple IPs, take the first (client IP)
        return forwarded_for.split(",")[0].strip()

    # Fall back to direct connection IP
    return request.client.host if request.client else "unknown"
