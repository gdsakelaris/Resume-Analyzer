"""
Pydantic schemas for email verification endpoints.
"""

from pydantic import BaseModel, Field, field_validator
import re


class VerifyCodeRequest(BaseModel):
    """Request to verify a 6-digit code"""
    code: str = Field(..., min_length=6, max_length=6, description="6-digit verification code")

    @field_validator('code')
    @classmethod
    def validate_code_format(cls, v: str) -> str:
        """Ensure code is exactly 6 digits"""
        if not re.match(r'^\d{6}$', v):
            raise ValueError('Code must be exactly 6 digits')
        return v


class ResendCodeRequest(BaseModel):
    """Request to resend verification code (can be empty body)"""
    pass


class VerificationResponse(BaseModel):
    """Response after verification attempt"""
    success: bool
    message: str
    is_verified: bool = False

    class Config:
        from_attributes = True


class SendCodeResponse(BaseModel):
    """Response after sending verification code"""
    success: bool
    message: str
    expires_in_minutes: int = 15

    class Config:
        from_attributes = True
