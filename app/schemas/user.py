"""
Pydantic schemas for User authentication and registration.
"""

from pydantic import BaseModel, EmailStr, Field, UUID4, field_validator
from typing import Optional
from datetime import datetime
import re


class UserRegisterRequest(BaseModel):
    """Request schema for user registration."""
    email: EmailStr
    password: str = Field(
        ...,
        min_length=8,
        max_length=72,  # bcrypt limit
        description="Password must be 8-72 characters with uppercase, lowercase, number, and special character"
    )
    full_name: Optional[str] = None
    company_name: Optional[str] = None

    @field_validator('password')
    @classmethod
    def validate_password_strength(cls, v: str) -> str:
        """Validate password contains required character types."""
        if len(v) < 8:
            raise ValueError('Password must be at least 8 characters long')
        if len(v) > 72:
            raise ValueError('Password cannot exceed 72 characters (bcrypt limitation)')
        if not re.search(r'[a-z]', v):
            raise ValueError('Password must contain at least one lowercase letter')
        if not re.search(r'[A-Z]', v):
            raise ValueError('Password must contain at least one uppercase letter')
        if not re.search(r'\d', v):
            raise ValueError('Password must contain at least one number')
        if not re.search(r'[!@#$%^&*(),.?":{}|<>]', v):
            raise ValueError('Password must contain at least one special character (!@#$%^&*(),.?":{}|<>)')
        return v


class UserLoginRequest(BaseModel):
    """Request schema for user login (OAuth2 compatible)."""
    username: EmailStr  # OAuth2 spec uses 'username', but we accept email
    password: str


class TokenResponse(BaseModel):
    """JWT token response."""
    access_token: str
    refresh_token: str
    token_type: str = "bearer"


class TokenRefreshRequest(BaseModel):
    """Request schema for refreshing access token."""
    refresh_token: str


class UserResponse(BaseModel):
    """User profile response (no sensitive data)."""
    id: UUID4
    tenant_id: UUID4
    email: str
    full_name: Optional[str]
    company_name: Optional[str]
    is_active: bool
    is_verified: bool
    created_at: datetime

    class Config:
        from_attributes = True
