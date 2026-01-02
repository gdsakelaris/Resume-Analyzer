"""
BACKUP OF ORIGINAL rate_limiter.py - DO NOT USE THIS FILE

This is the original version before the Redis connection fix.
Kept for reference only.

Redis-based rate limiting for email verification endpoints.

Prevents abuse of send/resend/verify operations.
"""

import redis
from typing import Optional
from datetime import timedelta
from fastapi import HTTPException, status
from app.core.config import settings


class RateLimiter:
    """
    Redis-based rate limiter for protecting endpoints.

    Uses sliding window rate limiting with automatic expiration.
    """

    def __init__(self):
        """Initialize Redis connection"""
        self.redis_client = redis.Redis(
            host=settings.REDIS_HOST,
            port=settings.REDIS_PORT,
            db=settings.REDIS_DB,
            decode_responses=True
        )

    def check_rate_limit(
        self,
        key: str,
        max_requests: int,
        window_seconds: int,
        error_message: str = "Rate limit exceeded"
    ) -> None:
        """
        Check if a request is within rate limits.

        Args:
            key: Unique identifier for this rate limit (e.g., "verify_email:user123")
            max_requests: Maximum number of requests allowed
            window_seconds: Time window in seconds
            error_message: Custom error message if rate limit exceeded

        Raises:
            HTTPException: 429 Too Many Requests if rate limit exceeded
        """
        try:
            # Get current request count
            current_count = self.redis_client.get(key)

            if current_count is None:
                # First request - set counter with expiration
                self.redis_client.setex(key, window_seconds, 1)
            else:
                # Increment counter
                count = int(current_count)
                if count >= max_requests:
                    # Rate limit exceeded
                    ttl = self.redis_client.ttl(key)
                    raise HTTPException(
                        status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                        detail=f"{error_message}. Try again in {ttl} seconds."
                    )
                self.redis_client.incr(key)

        except redis.RedisError as e:
            # If Redis is down, log error but don't block the request
            # (Fail open for better user experience)
            print(f"Redis rate limiter error: {e}")
            pass

    def reset_limit(self, key: str) -> None:
        """
        Reset the rate limit for a key.

        Useful for testing or manual intervention.

        Args:
            key: Rate limit key to reset
        """
        try:
            self.redis_client.delete(key)
        except redis.RedisError as e:
            print(f"Redis reset error: {e}")
            pass


# Singleton instance
rate_limiter = RateLimiter()


# Convenience functions for common rate limits
def check_send_verification_limit(user_id: str) -> None:
    """
    Rate limit for sending verification emails.

    Limit: 1 request per minute per user.
    """
    rate_limiter.check_rate_limit(
        key=f"send_verification:{user_id}",
        max_requests=1,
        window_seconds=60,
        error_message="Too many verification emails sent. Please wait before requesting another code"
    )


def check_resend_verification_limit(user_id: str) -> None:
    """
    Rate limit for resending verification emails.

    Limit: 1 request per 2 minutes per user.
    """
    rate_limiter.check_rate_limit(
        key=f"resend_verification:{user_id}",
        max_requests=1,
        window_seconds=120,
        error_message="Too many resend requests. Please wait before requesting another code"
    )


def check_verify_code_limit(user_id: str) -> None:
    """
    Rate limit for code verification attempts.

    Limit: 10 attempts per 10 minutes per user.
    Prevents brute force attacks.
    """
    rate_limiter.check_rate_limit(
        key=f"verify_code:{user_id}",
        max_requests=10,
        window_seconds=600,
        error_message="Too many verification attempts. Please wait before trying again"
    )
