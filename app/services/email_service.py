"""
Resend Email Service for sending verification emails.

Handles email formatting, template rendering, and Resend API integration.
"""

import logging
from typing import Optional
import resend
from app.core.config import settings

logger = logging.getLogger(__name__)


class EmailService:
    """
    Service for sending emails via Resend.

    Resend provides a modern, developer-friendly email API with excellent deliverability.
    """

    def __init__(self):
        """Initialize Resend API client"""
        # Set Resend API key
        resend.api_key = settings.RESEND_API_KEY

    def send_verification_email(
        self,
        to_email: str,
        verification_code: str,
        user_name: Optional[str] = None
    ) -> bool:
        """
        Send a verification code email to a user via Resend.

        Args:
            to_email: Recipient email address
            verification_code: 6-digit verification code
            user_name: Optional user's full name for personalization

        Returns:
            bool: True if email sent successfully, False otherwise
        """
        subject = "Verify Your Email - Starscreen"

        # Build HTML email body
        html_body = self._build_verification_html(verification_code, user_name)

        try:
            params = {
                "from": f"{settings.RESEND_FROM_NAME} <{settings.RESEND_FROM_EMAIL}>",
                "to": [to_email],
                "subject": subject,
                "html": html_body,
            }

            response = resend.Emails.send(params)

            # Resend returns a dict with 'id' on success
            if response and 'id' in response:
                email_id = response['id']
                logger.info(f"Verification email sent to {to_email} (Email ID: {email_id})")
                return True
            else:
                logger.error(f"Unexpected Resend response: {response}")
                return False

        except Exception as e:
            logger.error(f"Error sending email via Resend: {str(e)}")
            return False

    def send_password_reset_email(
        self,
        to_email: str,
        reset_token: str,
        user_name: Optional[str] = None
    ) -> bool:
        """
        Send a password reset email to a user via Resend.

        Args:
            to_email: Recipient email address
            reset_token: Password reset token
            user_name: Optional user's full name for personalization

        Returns:
            bool: True if email sent successfully, False otherwise
        """
        subject = "Reset Your Password - Starscreen"

        # Build reset URL
        reset_url = f"{settings.FRONTEND_URL}/reset-password?token={reset_token}"

        # Build HTML email body
        html_body = self._build_password_reset_html(reset_url, user_name)

        try:
            params = {
                "from": f"{settings.RESEND_FROM_NAME} <{settings.RESEND_FROM_EMAIL}>",
                "to": [to_email],
                "subject": subject,
                "html": html_body,
            }

            response = resend.Emails.send(params)

            # Resend returns a dict with 'id' on success
            if response and 'id' in response:
                email_id = response['id']
                logger.info(f"Password reset email sent to {to_email} (Email ID: {email_id})")
                return True
            else:
                logger.error(f"Unexpected Resend response: {response}")
                return False

        except Exception as e:
            logger.error(f"Error sending password reset email via Resend: {str(e)}")
            return False

    def _build_verification_html(self, code: str, user_name: Optional[str] = None) -> str:
        """
        Build HTML email body for verification code.

        Args:
            code: 6-digit verification code
            user_name: Optional user name

        Returns:
            str: HTML email content
        """
        greeting = f"Hi {user_name}," if user_name else "Hi there,"

        html = f"""
<!DOCTYPE html>
<html>
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Email Verification</title>
</head>
<body style="margin: 0; padding: 0; font-family: Arial, sans-serif; background-color: #f4f4f4;">
    <table role="presentation" style="width: 100%; border-collapse: collapse;">
        <tr>
            <td align="center" style="padding: 40px 0;">
                <table role="presentation" style="width: 600px; border-collapse: collapse; background-color: #ffffff; border-radius: 8px; box-shadow: 0 2px 4px rgba(0,0,0,0.1);">
                    <!-- Header -->
                    <tr>
                        <td style="padding: 40px 40px 20px 40px; text-align: center;">
                            <h1 style="margin: 0; color: #333333; font-size: 28px; font-weight: 600;">
                                Verify Your Email Address
                            </h1>
                        </td>
                    </tr>

                    <!-- Body -->
                    <tr>
                        <td style="padding: 0 40px 40px 40px;">
                            <p style="margin: 0 0 20px 0; color: #666666; font-size: 16px; line-height: 1.5;">
                                {greeting}
                            </p>
                            <p style="margin: 0 0 30px 0; color: #666666; font-size: 16px; line-height: 1.5;">
                                Thank you for signing up for Starscreen! To complete your registration, please use the verification code below:
                            </p>

                            <!-- Verification Code -->
                            <div style="background-color: #f8f9fa; border-radius: 8px; padding: 30px; text-align: center; margin: 0 0 30px 0;">
                                <div style="font-size: 36px; font-weight: 700; letter-spacing: 8px; color: #8b5cf6; font-family: 'Courier New', monospace;">
                                    {code}
                                </div>
                            </div>

                            <p style="margin: 0 0 20px 0; color: #666666; font-size: 14px; line-height: 1.5;">
                                This code will expire in <strong>15 minutes</strong>.
                            </p>

                            <p style="margin: 0; color: #999999; font-size: 13px; line-height: 1.5;">
                                If you didn't create an account with Starscreen, you can safely ignore this email.
                            </p>
                        </td>
                    </tr>

                    <!-- Footer -->
                    <tr>
                        <td style="padding: 20px 40px; background-color: #f8f9fa; border-top: 1px solid #e5e7eb; border-radius: 0 0 8px 8px;">
                            <p style="margin: 0; color: #999999; font-size: 12px; text-align: center;">
                                &copy; 2026 Starscreen. All rights reserved.
                            </p>
                        </td>
                    </tr>
                </table>
            </td>
        </tr>
    </table>
</body>
</html>
"""
        return html

    def _build_password_reset_html(self, reset_url: str, user_name: Optional[str] = None) -> str:
        """
        Build HTML email body for password reset.

        Args:
            reset_url: Password reset URL with token
            user_name: Optional user name

        Returns:
            str: HTML email content
        """
        greeting = f"Hi {user_name}," if user_name else "Hi there,"

        html = f"""
<!DOCTYPE html>
<html>
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Password Reset</title>
</head>
<body style="margin: 0; padding: 0; font-family: Arial, sans-serif; background-color: #f4f4f4;">
    <table role="presentation" style="width: 100%; border-collapse: collapse;">
        <tr>
            <td align="center" style="padding: 40px 0;">
                <table role="presentation" style="width: 600px; border-collapse: collapse; background-color: #ffffff; border-radius: 8px; box-shadow: 0 2px 4px rgba(0,0,0,0.1);">
                    <!-- Header -->
                    <tr>
                        <td style="padding: 40px 40px 20px 40px; text-align: center;">
                            <h1 style="margin: 0; color: #333333; font-size: 28px; font-weight: 600;">
                                Reset Your Password
                            </h1>
                        </td>
                    </tr>

                    <!-- Body -->
                    <tr>
                        <td style="padding: 0 40px 40px 40px;">
                            <p style="margin: 0 0 20px 0; color: #666666; font-size: 16px; line-height: 1.5;">
                                {greeting}
                            </p>
                            <p style="margin: 0 0 30px 0; color: #666666; font-size: 16px; line-height: 1.5;">
                                We received a request to reset your password for your Starscreen account. Click the button below to create a new password:
                            </p>

                            <!-- Reset Button -->
                            <div style="text-align: center; margin: 0 0 30px 0;">
                                <a href="{reset_url}" style="display: inline-block; padding: 14px 32px; background-color: #8b5cf6; color: #ffffff; text-decoration: none; border-radius: 6px; font-weight: 600; font-size: 16px;">
                                    Reset Password
                                </a>
                            </div>

                            <p style="margin: 0 0 20px 0; color: #666666; font-size: 14px; line-height: 1.5;">
                                This link will expire in <strong>1 hour</strong>.
                            </p>

                            <p style="margin: 0 0 20px 0; color: #666666; font-size: 14px; line-height: 1.5;">
                                If the button doesn't work, copy and paste this link into your browser:
                            </p>
                            <p style="margin: 0 0 30px 0; color: #8b5cf6; font-size: 13px; word-break: break-all;">
                                {reset_url}
                            </p>

                            <p style="margin: 0; color: #999999; font-size: 13px; line-height: 1.5;">
                                If you didn't request a password reset, you can safely ignore this email. Your password will not be changed.
                            </p>
                        </td>
                    </tr>

                    <!-- Footer -->
                    <tr>
                        <td style="padding: 20px 40px; background-color: #f8f9fa; border-top: 1px solid #e5e7eb; border-radius: 0 0 8px 8px;">
                            <p style="margin: 0; color: #999999; font-size: 12px; text-align: center;">
                                &copy; 2026 Starscreen. All rights reserved.
                            </p>
                        </td>
                    </tr>
                </table>
            </td>
        </tr>
    </table>
</body>
</html>
"""
        return html


# Singleton instance
email_service = EmailService()
