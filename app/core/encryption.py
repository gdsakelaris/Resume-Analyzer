"""
Token encryption utilities for OAuth tokens.

Uses Fernet (symmetric encryption) to encrypt OAuth tokens at rest.
Tokens are encrypted before storage and decrypted when needed for API calls.
"""

import logging
from cryptography.fernet import Fernet
from app.core.config import settings

logger = logging.getLogger(__name__)


class TokenEncryption:
    """
    Encrypt/decrypt OAuth tokens using Fernet symmetric encryption.

    Fernet guarantees that a message encrypted using it cannot be
    manipulated or read without the key. Uses AES 128 in CBC mode.
    """

    def __init__(self):
        """Initialize encryption with key from settings."""
        if not settings.ENCRYPTION_KEY:
            logger.warning(
                "ENCRYPTION_KEY not set. OAuth tokens will be stored unencrypted. "
                "Generate a key with: python -c \"from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())\""
            )
            self.cipher = None
        else:
            try:
                self.cipher = Fernet(settings.ENCRYPTION_KEY.encode())
            except Exception as e:
                logger.error(f"Invalid ENCRYPTION_KEY: {e}")
                self.cipher = None

    def encrypt(self, token: str) -> str:
        """
        Encrypt token for storage.

        Args:
            token: Plain text token

        Returns:
            Encrypted token (base64 encoded)
        """
        if not self.cipher:
            # No encryption key set, return token as-is (not recommended for production)
            return token

        try:
            encrypted = self.cipher.encrypt(token.encode())
            return encrypted.decode()
        except Exception as e:
            logger.error(f"Token encryption failed: {e}")
            raise

    def decrypt(self, encrypted_token: str) -> str:
        """
        Decrypt token for use.

        Args:
            encrypted_token: Encrypted token (base64 encoded)

        Returns:
            Plain text token
        """
        if not self.cipher:
            # No encryption key set, return token as-is (not recommended for production)
            return encrypted_token

        try:
            decrypted = self.cipher.decrypt(encrypted_token.encode())
            return decrypted.decode()
        except Exception as e:
            logger.error(f"Token decryption failed: {e}")
            raise


# Singleton instance
token_encryption = TokenEncryption()
