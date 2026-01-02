"""
AWS SES Email Service for sending verification emails.

Handles email formatting, template rendering, and AWS SES integration.
"""

import logging
from typing import Optional
import boto3
from botocore.exceptions import ClientError, BotoCoreError
from app.core.config import settings

logger = logging.getLogger(__name__)


class EmailService:
    """
    Service for sending emails via AWS SES.

    Supports both development (sandbox) and production modes.
    """

    def __init__(self):
        """Initialize AWS SES client"""
        # Configure boto3 client
        session_kwargs = {
            'region_name': settings.AWS_REGION,
        }

        # Add credentials if provided (otherwise uses IAM role)
        if settings.AWS_ACCESS_KEY_ID and settings.AWS_SECRET_ACCESS_KEY:
            session_kwargs['aws_access_key_id'] = settings.AWS_ACCESS_KEY_ID
            session_kwargs['aws_secret_access_key'] = settings.AWS_SECRET_ACCESS_KEY

        self.ses_client = boto3.client('ses', **session_kwargs)

    def send_verification_email(
        self,
        to_email: str,
        verification_code: str,
        user_name: Optional[str] = None
    ) -> bool:
        """
        Send a verification code email to a user.

        Args:
            to_email: Recipient email address
            verification_code: 6-digit verification code
            user_name: Optional user's full name for personalization

        Returns:
            bool: True if email sent successfully, False otherwise
        """
        subject = "Verify Your Email - Resume Analyzer"

        # Build HTML email body
        html_body = self._build_verification_html(verification_code, user_name)
        text_body = self._build_verification_text(verification_code, user_name)

        try:
            response = self.ses_client.send_email(
                Source=f"{settings.AWS_SES_FROM_NAME} <{settings.AWS_SES_FROM_EMAIL}>",
                Destination={'ToAddresses': [to_email]},
                Message={
                    'Subject': {'Data': subject, 'Charset': 'UTF-8'},
                    'Body': {
                        'Html': {'Data': html_body, 'Charset': 'UTF-8'},
                        'Text': {'Data': text_body, 'Charset': 'UTF-8'}
                    }
                }
            )

            message_id = response.get('MessageId')
            logger.info(f"Verification email sent to {to_email} (MessageId: {message_id})")
            return True

        except ClientError as e:
            error_code = e.response['Error']['Code']
            error_message = e.response['Error']['Message']
            logger.error(f"AWS SES ClientError: {error_code} - {error_message}")

            if error_code == 'MessageRejected':
                logger.error(f"Email rejected: {error_message}")
            elif error_code == 'MailFromDomainNotVerified':
                logger.error("Sender email not verified in SES")
            elif error_code == 'ConfigurationSetDoesNotExist':
                logger.error("SES configuration set not found")

            return False

        except BotoCoreError as e:
            logger.error(f"AWS BotoCoreError: {str(e)}")
            return False

        except Exception as e:
            logger.error(f"Unexpected error sending email: {str(e)}")
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
                                Thank you for signing up for Resume Analyzer! To complete your registration, please use the verification code below:
                            </p>

                            <!-- Verification Code -->
                            <div style="background-color: #f8f9fa; border-radius: 8px; padding: 30px; text-align: center; margin: 0 0 30px 0;">
                                <div style="font-size: 36px; font-weight: 700; letter-spacing: 8px; color: #4F46E5; font-family: 'Courier New', monospace;">
                                    {code}
                                </div>
                            </div>

                            <p style="margin: 0 0 20px 0; color: #666666; font-size: 14px; line-height: 1.5;">
                                This code will expire in <strong>15 minutes</strong>.
                            </p>

                            <p style="margin: 0; color: #999999; font-size: 13px; line-height: 1.5;">
                                If you didn't create an account with Resume Analyzer, you can safely ignore this email.
                            </p>
                        </td>
                    </tr>

                    <!-- Footer -->
                    <tr>
                        <td style="padding: 20px 40px; background-color: #f8f9fa; border-top: 1px solid #e5e7eb; border-radius: 0 0 8px 8px;">
                            <p style="margin: 0; color: #999999; font-size: 12px; text-align: center;">
                                &copy; 2026 Resume Analyzer. All rights reserved.
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

    def _build_verification_text(self, code: str, user_name: Optional[str] = None) -> str:
        """
        Build plain text email body for verification code (fallback).

        Args:
            code: 6-digit verification code
            user_name: Optional user name

        Returns:
            str: Plain text email content
        """
        greeting = f"Hi {user_name}," if user_name else "Hi there,"

        text = f"""{greeting}

Thank you for signing up for Resume Analyzer!

To complete your registration, please use the verification code below:

{code}

This code will expire in 15 minutes.

If you didn't create an account with Resume Analyzer, you can safely ignore this email.

---
Resume Analyzer
© 2026 All rights reserved.
"""
        return text


# Singleton instance
email_service = EmailService()
