"""
Test script to verify Resend email integration.

Run this to test if Resend is configured correctly and can send emails.
"""

import os
from dotenv import load_dotenv
import resend

# Load environment variables
load_dotenv()

# Get Resend configuration
RESEND_API_KEY = os.getenv("RESEND_API_KEY")
RESEND_FROM_EMAIL = os.getenv("RESEND_FROM_EMAIL")
RESEND_FROM_NAME = os.getenv("RESEND_FROM_NAME")

print("=" * 60)
print("RESEND EMAIL CONFIGURATION TEST")
print("=" * 60)

# Check if API key is configured
if not RESEND_API_KEY:
    print("❌ ERROR: RESEND_API_KEY not found in .env file")
    print("\nPlease add your Resend API key to .env:")
    print("RESEND_API_KEY=re_your_api_key_here")
    exit(1)

print(f"✓ API Key found: {RESEND_API_KEY[:15]}...")
print(f"✓ From Email: {RESEND_FROM_EMAIL}")
print(f"✓ From Name: {RESEND_FROM_NAME}")

# Set API key
resend.api_key = RESEND_API_KEY

# Prompt for test email
print("\n" + "=" * 60)
test_email = input("Enter your email address to send a test verification code: ").strip()

if not test_email or "@" not in test_email:
    print("❌ Invalid email address")
    exit(1)

# Generate test verification code
test_code = "123456"

# Build test HTML email
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
                                Hi there,
                            </p>
                            <p style="margin: 0 0 30px 0; color: #666666; font-size: 16px; line-height: 1.5;">
                                This is a test email from Starscreen. Your verification code is:
                            </p>

                            <!-- Verification Code -->
                            <div style="background-color: #f8f9fa; border-radius: 8px; padding: 30px; text-align: center; margin: 0 0 30px 0;">
                                <div style="font-size: 36px; font-weight: 700; letter-spacing: 8px; color: #8b5cf6; font-family: 'Courier New', monospace;">
                                    {test_code}
                                </div>
                            </div>

                            <p style="margin: 0 0 20px 0; color: #666666; font-size: 14px; line-height: 1.5;">
                                This is a test email to verify Resend integration.
                            </p>

                            <p style="margin: 0; color: #999999; font-size: 13px; line-height: 1.5;">
                                If you didn't request this test, you can safely ignore this email.
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

# Send test email
print(f"\n📧 Sending test email to {test_email}...")

try:
    params = {
        "from": f"{RESEND_FROM_NAME} <{RESEND_FROM_EMAIL}>",
        "to": [test_email],
        "subject": "Test Verification Code - Starscreen",
        "html": html,
    }

    response = resend.Emails.send(params)

    if response and 'id' in response:
        print(f"✅ SUCCESS! Email sent successfully")
        print(f"   Email ID: {response['id']}")
        print(f"\n📬 Check your inbox at {test_email}")
        print("   (Also check spam/junk folder)")
        print(f"\n🔗 View in Resend Dashboard:")
        print(f"   https://resend.com/emails/{response['id']}")
    else:
        print(f"❌ Unexpected response from Resend:")
        print(f"   {response}")

except Exception as e:
    print(f"❌ ERROR: Failed to send email")
    print(f"   {str(e)}")
    print("\n🔍 Common issues:")
    print("   1. Invalid API key - check your RESEND_API_KEY in .env")
    print("   2. Domain not verified - use onboarding@resend.dev for testing")
    print("   3. Recipient email not verified (if using test domain)")
    print("\n💡 To fix:")
    print("   - Go to https://resend.com/domains to verify your domain")
    print("   - OR use RESEND_FROM_EMAIL=onboarding@resend.dev for testing")
    exit(1)

print("\n" + "=" * 60)
print("Test complete!")
print("=" * 60)
