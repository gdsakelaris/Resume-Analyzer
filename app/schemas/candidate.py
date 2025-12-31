"""
Pydantic schemas for Candidate API requests/responses.
"""

from datetime import datetime
from typing import Optional
from pydantic import BaseModel, Field, EmailStr
from app.models.candidate import CandidateStatus


class CandidateBase(BaseModel):
    """Base candidate schema with common fields."""
    first_name: Optional[str] = Field(None, description="Candidate first name (optional for blind screening)")
    last_name: Optional[str] = Field(None, description="Candidate last name (optional for blind screening)")
    email: Optional[EmailStr] = Field(None, description="Candidate email (optional for blind screening)")
    phone: Optional[str] = Field(None, description="Candidate phone number (optional for blind screening)")
    location: Optional[str] = Field(None, description="Candidate location (optional for blind screening)")


class CandidateUploadResponse(BaseModel):
    """Response after uploading a resume."""
    candidate_id: int
    job_id: int
    status: str
    task_id: str
    message: str


class CandidateResponse(CandidateBase):
    """Full candidate response including processing status and results."""
    id: int
    job_id: int
    original_filename: str
    status: CandidateStatus
    error_message: Optional[str] = None
    resume_text: Optional[str] = Field(None, description="Extracted resume text")
    anonymized_text: Optional[str] = Field(None, description="PII-redacted text for blind screening")
    created_at: datetime

    class Config:
        from_attributes = True


class CandidateListResponse(BaseModel):
    """Simplified candidate info for list endpoints."""
    id: int
    job_id: int
    first_name: Optional[str]
    last_name: Optional[str]
    email: Optional[str]
    phone: Optional[str]
    location: Optional[str]
    original_filename: str
    status: CandidateStatus
    error_message: Optional[str] = None
    score: Optional[float] = Field(None, description="Relevance indicator (0-100) - guidance only, not a hiring decision")
    created_at: datetime

    class Config:
        from_attributes = True
