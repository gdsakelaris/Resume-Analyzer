"""
CRUD operations (Create, Read, Update, Delete) for database models.

This layer provides a clean separation between API routes and database operations,
following the Repository pattern.
"""

from app.crud import job

__all__ = ["job"]
