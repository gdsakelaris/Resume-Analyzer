from pydantic import BaseModel, Field
from typing import List, Optional, Dict
from datetime import datetime
from enum import Enum


class JobStatusEnum(str, Enum):
    """Job processing status"""
    PENDING = "PENDING"
    PROCESSING = "PROCESSING"
    COMPLETED = "COMPLETED"
    FAILED = "FAILED"


class JobCategory(BaseModel):
    """Schema for a single job category with importance scoring"""
    category_id: str
    name: str
    importance: int = Field(..., ge=1, le=5, description="Importance from 1 (low) to 5 (critical)")
    description: str
    examples_of_evidence: List[str]


class JobConfigSchema(BaseModel):
    """
    AI-generated job configuration schema.
    This is the structure that the AI service produces.
    """
    job_id: Optional[int] = None
    title: str
    seniority_level: str
    role_summary: str
    core_responsibilities: List[str]
    categories: List[JobCategory]
    desired_background_patterns: Dict
    education_preferences: Dict


class JobCreateRequest(BaseModel):
    """Schema for creating a new job"""
    title: str = Field(..., min_length=1, max_length=200)
    description: str = Field(..., min_length=10, max_length=15000, description="Job description (max 15,000 characters)")
    location: Optional[str] = None
    work_authorization_required: bool = False
    post_to_linkedin: bool = Field(False, description="Automatically post job to LinkedIn (requires paid subscription and LinkedIn connection)")


class JobUpdateRequest(BaseModel):
    """Schema for updating an existing job"""
    title: Optional[str] = Field(None, min_length=1, max_length=200)
    description: Optional[str] = Field(None, min_length=10, max_length=15000, description="Job description (max 15,000 characters)")
    location: Optional[str] = None
    work_authorization_required: Optional[bool] = None


class ExternalPostingResponse(BaseModel):
    """Schema for external job posting status"""
    provider: str = Field(..., description="Job board provider (e.g., 'linkedin', 'indeed')")
    status: str = Field(..., description="Posting status (pending, posting, active, failed, closed, expired)")
    external_url: Optional[str] = Field(None, description="URL to job on external platform")
    posted_at: Optional[datetime] = Field(None, description="When job was successfully posted")
    error_message: Optional[str] = Field(None, description="Error message if posting failed")

    class Config:
        from_attributes = True


class JobResponse(BaseModel):
    """Schema for job response"""
    id: int
    title: str
    description: str
    location: Optional[str]
    work_authorization_required: bool
    status: JobStatusEnum
    error_message: Optional[str] = None
    job_config: Optional[Dict] = None
    external_postings: List[ExternalPostingResponse] = Field(default_factory=list, description="External job board postings")
    created_at: datetime
    updated_at: Optional[datetime] = None

    class Config:
        from_attributes = True  # Allows conversion from SQLAlchemy models


class JobCreateResponse(BaseModel):
    """Schema for job creation response"""
    job_id: int
    status: JobStatusEnum
    message: str
