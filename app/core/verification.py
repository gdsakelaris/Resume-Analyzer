"""
Core email verification logic.

Handles generation, validation, and lifecycle management of 6-digit verification codes.
"""

import secrets
import uuid
from datetime import datetime, timedelta, timezone
from typing import Optional, Tuple
from sqlalchemy.orm import Session
from fastapi import HTTPException, status

from app.models.email_verification import EmailVerification
from app.models.user import User


# Security constants
CODE_EXPIRATION_MINUTES = 15
MAX_VERIFICATION_ATTEMPTS = 5
CODE_LENGTH = 6


def generate_verification_code() -> str:
    """
    Generate a secure 6-digit verification code.

    Uses secrets module for cryptographic randomness to prevent
    prediction attacks.

    Returns:
        str: 6-digit numeric code (e.g., "123456")
    """
    # Generate random 6-digit number using cryptographically secure random
    code = ''.join(secrets.choice('0123456789') for _ in range(CODE_LENGTH))
    return code


def create_verification_code(db: Session, user_id: uuid.UUID) -> EmailVerification:
    """
    Create a new verification code for a user.

    - Invalidates any previous unused codes for the user
    - Generates a new 6-digit code
    - Sets 15-minute expiration

    Args:
        db: Database session
        user_id: UUID of the user

    Returns:
        EmailVerification: The newly created verification record
    """
    # Invalidate previous unused codes by marking them as used
    db.query(EmailVerification).filter(
        EmailVerification.user_id == user_id,
        EmailVerification.is_used == False
    ).update({"is_used": True})
    db.commit()

    # Generate new code
    code = generate_verification_code()
    expires_at = datetime.now(timezone.utc) + timedelta(minutes=CODE_EXPIRATION_MINUTES)

    # Create verification record
    verification = EmailVerification(
        id=uuid.uuid4(),
        user_id=user_id,
        code=code,
        expires_at=expires_at,
        created_at=datetime.now(timezone.utc),
        attempts=0,
        is_used=False
    )

    db.add(verification)
    db.commit()
    db.refresh(verification)

    return verification


def verify_code(db: Session, user_id: uuid.UUID, code: str) -> Tuple[bool, str]:
    """
    Verify a 6-digit code for a user.

    Security checks:
    - Code must exist and belong to the user
    - Code must not be expired
    - Code must not already be used
    - Maximum 5 attempts per code
    - Marks user as verified on success

    Args:
        db: Database session
        user_id: UUID of the user
        code: 6-digit verification code

    Returns:
        Tuple[bool, str]: (success, message)

    Raises:
        HTTPException: For various error conditions
    """
    # Find the verification record
    verification = db.query(EmailVerification).filter(
        EmailVerification.user_id == user_id,
        EmailVerification.code == code,
        EmailVerification.is_used == False
    ).first()

    if not verification:
        return False, "Invalid verification code"

    # Increment attempt counter
    verification.attempts += 1
    db.commit()

    # Check if too many attempts
    if verification.attempts > MAX_VERIFICATION_ATTEMPTS:
        verification.is_used = True
        db.commit()
        return False, "Too many attempts. Please request a new code."

    # Check expiration
    if datetime.now(timezone.utc) > verification.expires_at:
        verification.is_used = True
        db.commit()
        return False, "Verification code has expired. Please request a new code."

    # Code is valid - mark as used and verify user
    verification.is_used = True

    # Update user verification status
    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        db.commit()
        return False, "User not found"

    user.is_verified = True
    db.commit()

    return True, "Email verified successfully"


def cleanup_expired_codes(db: Session) -> int:
    """
    Clean up expired verification codes.

    This should be run periodically via a Celery task to prevent
    database bloat.

    Args:
        db: Database session

    Returns:
        int: Number of codes deleted
    """
    # Delete codes older than 24 hours
    cutoff_time = datetime.now(timezone.utc) - timedelta(hours=24)

    deleted = db.query(EmailVerification).filter(
        EmailVerification.created_at < cutoff_time
    ).delete()

    db.commit()
    return deleted


def get_active_verification(db: Session, user_id: uuid.UUID) -> Optional[EmailVerification]:
    """
    Get the active (non-expired, unused) verification code for a user.

    Args:
        db: Database session
        user_id: UUID of the user

    Returns:
        Optional[EmailVerification]: Active verification or None
    """
    return db.query(EmailVerification).filter(
        EmailVerification.user_id == user_id,
        EmailVerification.is_used == False,
        EmailVerification.expires_at > datetime.now(timezone.utc)
    ).order_by(EmailVerification.created_at.desc()).first()
