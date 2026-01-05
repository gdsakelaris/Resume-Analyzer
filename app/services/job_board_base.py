"""
Abstract base class for job board integrations.

Defines common interface for LinkedIn, Indeed, ZipRecruiter, etc.
All job board services must implement these methods for consistency.
"""

from abc import ABC, abstractmethod
from typing import Dict, Optional, Tuple
from app.models.job import Job
from app.models.oauth_connection import OAuthConnection


class JobPostingError(Exception):
    """Exception raised for job posting failures."""
    pass


class JobBoardService(ABC):
    """
    Abstract base class for job board integrations.

    This interface ensures all job board services (LinkedIn, Indeed, etc.)
    implement the same core methods, making it easy to add new platforms
    and manage multiple postings in parallel.
    """

    @abstractmethod
    async def post_job(self, job: Job, oauth_connection: OAuthConnection) -> Tuple[str, str]:
        """
        Post job to external platform.

        Args:
            job: Job model instance with title, description, location
            oauth_connection: OAuth connection with valid tokens

        Returns:
            Tuple of (external_job_id, external_url)
            - external_job_id: Platform's job ID (e.g., LinkedIn job ID)
            - external_url: URL to view job on platform

        Raises:
            JobPostingError: If posting fails
        """
        pass

    @abstractmethod
    async def close_job(self, external_job_id: str, oauth_connection: OAuthConnection) -> bool:
        """
        Close/remove job from platform.

        Args:
            external_job_id: Platform's job ID
            oauth_connection: OAuth connection with valid tokens

        Returns:
            bool: True if successfully closed, False otherwise

        Raises:
            JobPostingError: If closing fails
        """
        pass

    @abstractmethod
    async def refresh_token(self, oauth_connection: OAuthConnection) -> Dict:
        """
        Refresh OAuth access token.

        Args:
            oauth_connection: OAuth connection with refresh token

        Returns:
            dict: New token data with keys:
                - access_token: New access token
                - refresh_token: New refresh token (if provided)
                - expires_in: Token expiry in seconds

        Raises:
            JobPostingError: If token refresh fails
        """
        pass

    @abstractmethod
    def is_token_expired(self, oauth_connection: OAuthConnection) -> bool:
        """
        Check if access token is expired or about to expire.

        Args:
            oauth_connection: OAuth connection to check

        Returns:
            bool: True if token needs refresh, False otherwise
        """
        pass
