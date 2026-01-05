"""
Resend webhook handler for receiving incoming support emails.

Listens to Resend email.received webhooks to process support emails sent to support@starscreen.net.
Forwards emails to admin email and optionally stores for tracking.
"""

import logging
import resend
import httpx
from fastapi import APIRouter, Request, HTTPException
from typing import Dict, Any
import hmac
import hashlib

from app.core.config import settings

router = APIRouter(prefix="/webhooks", tags=["Resend Webhooks"])
logger = logging.getLogger(__name__)

# Initialize Resend API
resend.api_key = settings.RESEND_API_KEY


@router.post("/resend")
async def resend_webhook(request: Request):
    """
    Handle Resend webhook events for incoming emails.

    This endpoint is called by Resend when emails are received at support@starscreen.net.

    Event types handled:
    - email.received: When someone sends an email to support@starscreen.net

    The webhook receives email metadata (from, to, subject, attachments list)
    but NOT the email body. You must call the Resend API to retrieve the full content.
    """
    # Get webhook payload
    payload = await request.json()

    event_type = payload.get("type")
    logger.info(f"Received Resend webhook: {event_type}")

    try:
        if event_type == "email.received":
            await handle_email_received(payload)
            return {"status": "success"}
        else:
            logger.info(f"Unhandled event type: {event_type}")
            return {"status": "ignored"}

    except Exception as e:
        logger.error(f"Error processing Resend webhook {event_type}: {e}")
        raise HTTPException(status_code=500, detail=f"Webhook processing failed: {str(e)}")


async def handle_email_received(payload: Dict[str, Any]):
    """
    Process incoming support email.

    Workflow:
    1. Extract email metadata from webhook
    2. Fetch full email content via Resend API
    3. Forward to admin/support team email
    4. Optionally log to database for support ticket tracking
    """
    data = payload.get("data", {})

    email_id = data.get("email_id")
    from_email = data.get("from")
    to_emails = data.get("to", [])
    subject = data.get("subject", "(No Subject)")

    logger.info(f"Received support email from {from_email}: {subject}")

    # Fetch full email content (body, HTML, attachments) via Resend API
    # Note: Webhooks only include metadata - you must fetch the content separately
    try:
        # Get email content using Resend Receiving API via direct HTTP request
        # The Python SDK doesn't support the receiving API yet, so we make a raw HTTP call
        async with httpx.AsyncClient() as client:
            response = await client.get(
                f"https://api.resend.com/emails/receiving/{email_id}",
                headers={"Authorization": f"Bearer {settings.RESEND_API_KEY}"}
            )
            response.raise_for_status()
            email_content = response.json()

        # Extract email body (try HTML first, fallback to plain text)
        html_body = email_content.get("html")
        text_body = email_content.get("text")
        body = html_body or text_body or "(No content)"

        # Forward to your personal/admin email
        forward_to = settings.SUPPORT_FORWARD_EMAIL

        # Build forwarded email
        forward_subject = f"[Starscreen Support] {subject}"
        forward_body = f"""
<html>
<body style="font-family: Arial, sans-serif; max-width: 800px; margin: 0 auto; padding: 20px;">
    <div style="background-color: #f3f4f6; padding: 15px; border-radius: 8px; margin-bottom: 20px;">
        <h3 style="margin: 0 0 10px 0; color: #374151;">New Support Email Received</h3>
        <p style="margin: 5px 0; color: #6b7280;"><strong>From:</strong> {from_email}</p>
        <p style="margin: 5px 0; color: #6b7280;"><strong>To:</strong> {', '.join(to_emails)}</p>
        <p style="margin: 5px 0; color: #6b7280;"><strong>Subject:</strong> {subject}</p>
    </div>

    <div style="border-left: 4px solid #8b5cf6; padding-left: 15px;">
        <h4 style="color: #374151; margin-top: 0;">Message:</h4>
        {body if html_body else f'<pre style="white-space: pre-wrap; font-family: Arial, sans-serif;">{body}</pre>'}
    </div>

    <hr style="border: none; border-top: 1px solid #e5e7eb; margin: 30px 0;">

    <p style="color: #9ca3af; font-size: 12px; margin: 0;">
        To reply, send an email directly to {from_email}
    </p>
</body>
</html>
"""

        # Send forwarded email via Resend
        params = {
            "from": f"Starscreen Support <{settings.RESEND_FROM_EMAIL}>",
            "to": [forward_to],
            "subject": forward_subject,
            "html": forward_body,
            "reply_to": from_email  # Allow you to click reply and respond directly to the customer
        }

        response = resend.Emails.send(params)

        if response and 'id' in response:
            logger.info(f"Support email forwarded to {forward_to} (Email ID: {response['id']})")
        else:
            logger.error(f"Failed to forward support email: {response}")

    except Exception as e:
        logger.error(f"Error fetching/forwarding email {email_id}: {e}")
        # Don't raise exception - webhook should still return 200 to Resend
        # Otherwise Resend will retry the webhook repeatedly


# Optional: Verify webhook signature (if Resend adds this feature in the future)
def verify_webhook_signature(payload: bytes, signature: str, secret: str) -> bool:
    """
    Verify Resend webhook signature to ensure authenticity.

    Note: As of 2026, Resend doesn't provide webhook signature verification.
    This is a placeholder for future security enhancement.
    """
    expected_signature = hmac.new(
        secret.encode('utf-8'),
        payload,
        hashlib.sha256
    ).hexdigest()

    return hmac.compare_digest(signature, expected_signature)