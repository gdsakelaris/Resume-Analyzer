# Resend Email Setup Guide

This guide will walk you through setting up Resend for email verification in Starscreen.

## Why Resend?

- **Modern & Easy**: Simple API, great developer experience
- **Generous Free Tier**: 3,000 emails/month free (100/day)
- **Fast Setup**: 5-10 minutes to get started
- **Excellent Deliverability**: High inbox placement rates
- **No Domain Verification Initially**: Can start with their test domain

## Step 1: Create Resend Account

1. Go to [https://resend.com/signup](https://resend.com/signup)
2. Sign up with your email address
3. Verify your email address

## Step 2: Get Your API Key

1. Log in to your Resend dashboard
2. Navigate to **API Keys** in the sidebar
3. Click **Create API Key**
4. Give it a name (e.g., "Starscreen Production")
5. Select **Full Access** (for sending emails)
6. Click **Add**
7. **Copy the API key** - you'll only see it once!

## Step 3: Configure Your Application

1. Open your `.env` file
2. Paste your Resend API key:

```env
RESEND_API_KEY=re_your_api_key_here
RESEND_FROM_EMAIL=noreply@starscreen.net
RESEND_FROM_NAME=Starscreen
```

## Step 4: Domain Setup (Optional but Recommended)

### Option A: Use Resend's Test Domain (Quick Start)

For immediate testing, Resend provides a test domain `onboarding@resend.dev`. Update your `.env`:

```env
RESEND_FROM_EMAIL=onboarding@resend.dev
```

**Note**: Test emails only work with verified recipient addresses in your Resend account.

### Option B: Add Your Own Domain (Production)

For production use, you should verify your own domain:

1. In Resend dashboard, go to **Domains**
2. Click **Add Domain**
3. Enter your domain: `starscreen.net`
4. Add the DNS records shown to your domain registrar:
   - **SPF Record** (TXT)
   - **DKIM Record** (TXT)
   - **DMARC Record** (TXT - optional but recommended)
5. Wait for DNS propagation (5-30 minutes)
6. Click **Verify Domain** in Resend

Once verified, you can send from any address at your domain (e.g., `noreply@starscreen.net`).

## Step 5: Test Email Verification

### Test with Test Domain

If using `onboarding@resend.dev`, first add your email as a verified recipient:

1. In Resend dashboard, go to **Verified Recipients**
2. Add your email address
3. Verify it via the confirmation email

### Test Registration Flow

1. Start your application:
```bash
docker-compose up -d
```

2. Register a new account at your application
3. Check your email for the verification code
4. Verify your account with the 6-digit code

### Check Email Logs

View sent emails in your Resend dashboard:
1. Go to **Emails** in the sidebar
2. See delivery status, open rates, and email content
3. Click any email to see details

## Step 6: Monitor Usage

Track your email usage in the Resend dashboard:

- **Dashboard**: Shows daily/monthly email counts
- **Free Tier**: 3,000 emails/month (100/day)
- **Billing**: Automatic upgrade if you exceed free tier

## Troubleshooting

### Email Not Received

1. **Check Spam Folder**: Verification emails may go to spam
2. **Verify API Key**: Ensure `RESEND_API_KEY` is correct in `.env`
3. **Check Resend Dashboard**: Look for failed deliveries in **Emails** section
4. **Check Application Logs**: Look for Resend API errors
   ```bash
   docker-compose logs backend
   ```

### "Invalid API Key" Error

- Double-check your API key in `.env`
- Ensure no extra spaces or quotes
- Generate a new API key if needed

### "Domain Not Verified" Error

- Use `onboarding@resend.dev` for testing
- Complete domain verification for your own domain
- Wait for DNS propagation

### Rate Limit Exceeded

- Free tier: 100 emails/day, 3,000/month
- Upgrade plan if needed
- Check for email loops or spam

## Email Template Customization

The verification email template is in [app/services/email_service.py](../app/services/email_service.py).

To customize:
1. Edit the `_build_verification_html()` method
2. Modify HTML/CSS as needed
3. Test changes by registering a new account

## Production Checklist

- [ ] Create Resend account
- [ ] Get API key
- [ ] Add and verify your domain (`starscreen.net`)
- [ ] Update `.env` with API key and domain email
- [ ] Test email delivery
- [ ] Monitor usage in dashboard
- [ ] Set up billing alerts (optional)

## Pricing

- **Free Tier**: 3,000 emails/month, 100/day
- **Pro Plan**: $20/month for 50,000 emails/month
- **Business Plan**: Custom pricing for higher volumes

For your use case (verification emails), the free tier should be sufficient for hundreds of new users per month.

## Support

- **Resend Docs**: [https://resend.com/docs](https://resend.com/docs)
- **Resend Support**: [support@resend.com](mailto:support@resend.com)
- **Resend Discord**: [https://resend.com/discord](https://resend.com/discord)

## Migration from AWS SES

The application has been updated to use Resend instead of AWS SES. AWS SES settings are now deprecated but remain in `.env` for reference.

To fully remove AWS SES:
1. Remove `boto3` dependency (if not used for S3)
2. Delete AWS SES documentation files
3. Remove AWS SES environment variables from `.env`

**Note**: Keep `boto3` if you're using AWS S3 for file storage.
