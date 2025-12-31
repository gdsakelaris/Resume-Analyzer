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
    description: str = Field(..., min_length=10)
    location: Optional[str] = None
    work_authorization_required: bool = False


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
    created_at: datetime
    updated_at: Optional[datetime] = None

    class Config:
        from_attributes = True  # Allows conversion from SQLAlchemy models


class JobCreateResponse(BaseModel):
    """Schema for job creation response"""
    job_id: int
    status: JobStatusEnum
    message: str
