"""
LinkedIn API service for job posting automation.

Uses LinkedIn's Job Posting API (v2) with OAuth 2.0 authentication.
API Documentation: https://learn.microsoft.com/en-us/linkedin/talent/job-postings/api/overview
"""

import logging
import secrets
import httpx
from datetime import datetime, timedelta
from typing import Dict, Optional, Tuple
from urllib.parse import urlencode
from app.core.config import settings
from app.services.job_board_base import JobBoardService, JobPostingError
from app.models.job import Job
from app.models.oauth_connection import OAuthConnection

logger = logging.getLogger(__name__)


class LinkedInService(JobBoardService):
    """
    LinkedIn API integration service.

    Handles:
    - OAuth 2.0 authorization flow
    - Job posting via simpleJobPostings API
    - Token refresh
    - Error handling
    """

    # LinkedIn API endpoints
    AUTH_URL = "https://www.linkedin.com/oauth/v2/authorization"
    TOKEN_URL = "https://www.linkedin.com/oauth/v2/accessToken"
    API_BASE = "https://api.linkedin.com/v2"

    # OAuth scopes for sharing posts (available in standard LinkedIn apps)
    SCOPES = [
        "w_member_social",        # Share content as member (personal)
        "r_basicprofile",         # Read basic profile info
        "r_liteprofile"           # Read lite profile (name, photo)
    ]

    def __init__(self):
        self.client_id = settings.LINKEDIN_CLIENT_ID
        self.client_secret = settings.LINKEDIN_CLIENT_SECRET
        self.redirect_uri = settings.LINKEDIN_REDIRECT_URI

    def get_authorization_url(self, user_id: str) -> Tuple[str, str]:
        """
        Generate LinkedIn OAuth authorization URL.

        Args:
            user_id: User ID for state parameter (CSRF protection)

        Returns:
            Tuple of (authorization_url, state)
        """
        state = secrets.token_urlsafe(32)  # CSRF protection

        params = {
            "response_type": "code",
            "client_id": self.client_id,
            "redirect_uri": self.redirect_uri,
            "scope": " ".join(self.SCOPES),
            "state": state
        }

        auth_url = f"{self.AUTH_URL}?{urlencode(params)}"
        return auth_url, state

    async def store_oauth_state(self, user_id: str, state: str) -> None:
        """
        Store OAuth state in Redis for CSRF validation (15 min expiry).

        Args:
            user_id: User ID
            state: State parameter to store
        """
        from app.core.celery_app import celery_app
        redis_client = celery_app.broker_connection().channel().client
        key = f"oauth_state:{user_id}"
        redis_client.setex(key, 900, state)  # 15 minutes

    async def validate_oauth_state(self, user_id: str, state: str) -> bool:
        """
        Validate OAuth state parameter.

        Args:
            user_id: User ID
            state: State parameter to validate

        Returns:
            bool: True if valid, False otherwise
        """
        from app.core.celery_app import celery_app
        redis_client = celery_app.broker_connection().channel().client
        key = f"oauth_state:{user_id}"
        stored_state = redis_client.get(key)

        if stored_state and stored_state.decode() == state:
            redis_client.delete(key)  # Single use
            return True
        return False

    async def exchange_code_for_token(self, code: str) -> Dict:
        """
        Exchange authorization code for access token.

        Args:
            code: Authorization code from LinkedIn callback

        Returns:
            Token data including access_token, refresh_token, expires_in

        Raises:
            JobPostingError: If token exchange fails
        """
        async with httpx.AsyncClient() as client:
            response = await client.post(
                self.TOKEN_URL,
                data={
                    "grant_type": "authorization_code",
                    "code": code,
                    "redirect_uri": self.redirect_uri,
                    "client_id": self.client_id,
                    "client_secret": self.client_secret
                },
                headers={"Content-Type": "application/x-www-form-urlencoded"},
                timeout=30.0
            )

            if response.status_code != 200:
                logger.error(f"Token exchange failed: {response.text}")
                raise JobPostingError(f"Failed to obtain access token: {response.text}")

            return response.json()

    async def refresh_token(self, oauth_connection: OAuthConnection) -> Dict:
        """
        Refresh expired access token.

        Args:
            oauth_connection: OAuth connection with refresh token

        Returns:
            New token data

        Raises:
            JobPostingError: If token refresh fails
        """
        if not oauth_connection.refresh_token:
            raise JobPostingError("No refresh token available")

        async with httpx.AsyncClient() as client:
            response = await client.post(
                self.TOKEN_URL,
                data={
                    "grant_type": "refresh_token",
                    "refresh_token": oauth_connection.refresh_token,
                    "client_id": self.client_id,
                    "client_secret": self.client_secret
                },
                headers={"Content-Type": "application/x-www-form-urlencoded"},
                timeout=30.0
            )

            if response.status_code != 200:
                logger.error(f"Token refresh failed: {response.text}")
                raise JobPostingError(f"Token refresh failed: {response.text}")

            return response.json()

    def is_token_expired(self, oauth_connection: OAuthConnection) -> bool:
        """
        Check if access token is expired or about to expire (5 min buffer).

        Args:
            oauth_connection: OAuth connection to check

        Returns:
            bool: True if token needs refresh
        """
        if not oauth_connection.token_expires_at:
            return False

        buffer = timedelta(minutes=5)
        return datetime.utcnow() + buffer >= oauth_connection.token_expires_at

    async def get_member_info(self, oauth_connection: OAuthConnection) -> Dict:
        """
        Get the authenticated member's LinkedIn profile info.

        Returns:
            Dict with member ID and profile data
        """
        async with httpx.AsyncClient() as client:
            response = await client.get(
                f"{self.API_BASE}/me",
                headers={
                    "Authorization": f"Bearer {oauth_connection.access_token}",
                },
                timeout=30.0
            )

            if response.status_code != 200:
                logger.error(f"Failed to get member info: {response.text}")
                raise JobPostingError(f"Failed to get member info: {response.text}")

            return response.json()

    async def post_job(self, job: Job, oauth_connection: OAuthConnection) -> Tuple[str, str]:
        """
        Share job to LinkedIn feed using UGC Posts API.

        NOTE: This shares the job as a LinkedIn post, NOT as a job listing.
        Full job posting requires LinkedIn Talent Solutions partnership.

        API Endpoint: POST https://api.linkedin.com/v2/ugcPosts
        Documentation: https://learn.microsoft.com/en-us/linkedin/consumer/integrations/self-serve/share-on-linkedin

        Args:
            job: Job model instance with title, description, location
            oauth_connection: OAuth connection with valid access token

        Returns:
            Tuple of (linkedin_post_id, post_url)

        Raises:
            JobPostingError: If posting fails
        """
        # Refresh token if expired
        if self.is_token_expired(oauth_connection):
            logger.info(f"Refreshing expired token for job {job.id}")
            new_tokens = await self.refresh_token(oauth_connection)
            # Note: Caller should update tokens in database

        # Get member info to get person URN
        member_info = await self.get_member_info(oauth_connection)
        person_id = member_info.get("id")
        if not person_id:
            raise JobPostingError("Could not get member ID from LinkedIn")

        author_urn = f"urn:li:person:{person_id}"

        # Build post content
        apply_url = f"{settings.FRONTEND_URL}/jobs/{job.id}/apply"

        # Create post text (max 3000 characters)
        location_text = f"\n📍 Location: {job.location}" if job.location else ""
        post_text = f"""🚀 New Job Opportunity: {job.title}

{job.description[:500]}{"..." if len(job.description) > 500 else ""}{location_text}

Apply now: {apply_url}

#hiring #jobs #careers
"""

        # Build UGC post payload
        payload = {
            "author": author_urn,
            "lifecycleState": "PUBLISHED",
            "specificContent": {
                "com.linkedin.ugc.ShareContent": {
                    "shareCommentary": {
                        "text": post_text
                    },
                    "shareMediaCategory": "ARTICLE",
                    "media": [
                        {
                            "status": "READY",
                            "description": {
                                "text": f"Apply for {job.title}"
                            },
                            "originalUrl": apply_url,
                            "title": {
                                "text": job.title
                            }
                        }
                    ]
                }
            },
            "visibility": {
                "com.linkedin.ugc.MemberNetworkVisibility": "PUBLIC"
            }
        }

        async with httpx.AsyncClient() as client:
            response = await client.post(
                f"{self.API_BASE}/ugcPosts",
                json=payload,
                headers={
                    "Authorization": f"Bearer {oauth_connection.access_token}",
                    "Content-Type": "application/json",
                    "X-Restli-Protocol-Version": "2.0.0"
                },
                timeout=30.0
            )

            if response.status_code not in [200, 201]:
                error_msg = f"LinkedIn API error: {response.status_code} - {response.text}"
                logger.error(error_msg)
                raise JobPostingError(error_msg)

            result = response.json()
            post_id = result.get("id")

            # Extract the activity ID for the URL
            if post_id:
                # Convert URN format to activity ID
                activity_id = post_id.split(":")[-1] if ":" in post_id else post_id
                post_url = f"https://www.linkedin.com/feed/update/{post_id}"
            else:
                post_url = "https://www.linkedin.com/feed/"

            logger.info(f"Successfully shared job {job.id} to LinkedIn (Post ID: {post_id})")
            return post_id or "shared", post_url

    async def close_job(self, external_job_id: str, oauth_connection: OAuthConnection) -> bool:
        """
        Close job posting on LinkedIn.

        Args:
            external_job_id: LinkedIn job ID
            oauth_connection: OAuth connection

        Returns:
            True if successful

        Raises:
            JobPostingError: If closing fails
        """
        payload = {
            "jobPostingOperationType": "CLOSE"
        }

        async with httpx.AsyncClient() as client:
            response = await client.post(
                f"{self.API_BASE}/simpleJobPostings/{external_job_id}",
                json=payload,
                headers={
                    "Authorization": f"Bearer {oauth_connection.access_token}",
                    "Content-Type": "application/json",
                    "X-Restli-Protocol-Version": "2.0.0"
                },
                timeout=30.0
            )

            if response.status_code not in [200, 204]:
                logger.error(f"Failed to close LinkedIn job {external_job_id}: {response.text}")
                raise JobPostingError(f"Failed to close job: {response.text}")

            return True


# Singleton instance
linkedin_service = LinkedInService()
