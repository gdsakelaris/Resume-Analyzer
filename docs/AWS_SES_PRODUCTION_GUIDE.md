# AWS SES Production Access Guide

## Current Status

⚠️ **AWS SES is currently in SANDBOX MODE**

This means:
- ✅ Can send emails to verified email addresses only
- ❌ Cannot send emails to unverified recipients
- ❌ Sending limit: 200 emails/day
- ❌ Sending rate: 1 email/second

## Why Move to Production?

Production access removes these restrictions:
- ✅ Send to ANY email address (no verification required)
- ✅ Higher sending limits (50,000 emails/day default)
- ✅ Higher sending rate (14 emails/second)
- ✅ Professional deliverability and reputation management

## Prerequisites

Before requesting production access, ensure:

1. **Valid Use Case**: Transactional emails (verification codes, notifications)
2. **Email Authentication**: SPF, DKIM, DMARC configured
3. **Bounce/Complaint Handling**: Set up SNS notifications
4. **Clean Email Practices**: No spam, valid opt-out mechanisms

## Step 1: Configure Email Authentication

### SPF Record

Add to your DNS (e.g., `starscreen.ai` or your domain):

```
TXT record for your-domain.com:
v=spf1 include:amazonses.com ~all
```

### DKIM (DomainKeys Identified Mail)

1. **Generate DKIM tokens in AWS SES**:
   ```bash
   aws ses verify-domain-dkim --domain your-domain.com
   ```

2. **Add CNAME records to DNS**:
   AWS will provide 3 CNAME records - add all to your DNS:
   ```
   xxx._domainkey.your-domain.com → xxx.dkim.amazonses.com
   yyy._domainkey.your-domain.com → yyy.dkim.amazonses.com
   zzz._domainkey.your-domain.com → zzz.dkim.amazonses.com
   ```

### DMARC (Domain-based Message Authentication)

Add to DNS:
```
TXT record for _dmarc.your-domain.com:
v=DMARC1; p=quarantine; rua=mailto:dmarc@your-domain.com
```

### Verify Configuration

```bash
# Check SPF
dig TXT your-domain.com

# Check DKIM
dig TXT xxx._domainkey.your-domain.com

# Check DMARC
dig TXT _dmarc.your-domain.com
```

## Step 2: Configure Bounce and Complaint Handling

### Create SNS Topics

```bash
# Create bounce notification topic
aws sns create-topic --name ses-bounces

# Create complaint notification topic
aws sns create-topic --name ses-complaints

# Subscribe your email
aws sns subscribe \
  --topic-arn arn:aws:sns:us-east-1:YOUR_ACCOUNT:ses-bounces \
  --protocol email \
  --notification-endpoint admin@your-domain.com
```

### Configure SES to Use SNS

```bash
# Set bounce notifications
aws ses set-identity-notification-topic \
  --identity your-domain.com \
  --notification-type Bounce \
  --sns-topic arn:aws:sns:us-east-1:YOUR_ACCOUNT:ses-bounces

# Set complaint notifications
aws ses set-identity-notification-topic \
  --identity your-domain.com \
  --notification-type Complaint \
  --sns-topic arn:aws:sns:us-east-1:YOUR_ACCOUNT:ses-complaints
```

## Step 3: Request Production Access

### Via AWS Console

1. **Navigate to SES Console**:
   - Go to https://console.aws.amazon.com/ses/
   - Click "Account Dashboard"

2. **Click "Request Production Access"**

3. **Fill Out the Form**:

   **Use Case Description** (example):
   ```
   We are Starscreen, an AI-powered resume screening SaaS platform.

   We need to send transactional emails for:
   1. Email verification codes (6-digit OTP)
   2. Password reset links
   3. Subscription notifications
   4. System alerts

   Expected volume: 500-1,000 emails/day
   All emails are opt-in, transactional, and GDPR-compliant.
   ```

   **Website URL**: https://starscreen.ai (or your domain)

   **Email Type**: Transactional

   **Compliance**:
   ```
   - Users explicitly sign up and provide email
   - All emails include unsubscribe link
   - We honor all unsubscribe requests immediately
   - We monitor bounce and complaint rates
   - GDPR/CCPA compliant privacy policy in place
   ```

   **Process for Handling Bounces**:
   ```
   - SNS notifications configured for bounces
   - Hard bounces: Remove from mailing list immediately
   - Soft bounces: Retry 3 times, then remove
   - Monitor bounce rate monthly (target < 5%)
   ```

   **Process for Handling Complaints**:
   ```
   - SNS notifications configured for complaints
   - Investigate each complaint within 24 hours
   - Remove complainant from all future emails
   - Monitor complaint rate (target < 0.1%)
   ```

4. **Submit Request**

5. **Wait for Approval** (typically 24-48 hours)

### Via AWS CLI

```bash
aws sesv2 put-account-details \
  --production-access-enabled \
  --mail-type TRANSACTIONAL \
  --website-url https://starscreen.ai \
  --use-case-description "Transactional emails for SaaS platform..." \
  --contact-language EN
```

## Step 4: Post-Approval Configuration

Once approved:

1. **Update Environment Variables**:
   ```bash
   # In .env or AWS Secrets Manager
   AWS_SES_PRODUCTION_MODE=true
   AWS_SES_REGION=us-east-1
   AWS_SES_FROM_EMAIL=noreply@your-domain.com
   ```

2. **Test Email Sending**:
   ```bash
   # Send test email
   python test_email.py
   ```

3. **Monitor Metrics**:
   - Bounce rate (keep < 5%)
   - Complaint rate (keep < 0.1%)
   - Send rate
   - Reputation dashboard

## Monitoring and Maintenance

### CloudWatch Metrics

Monitor these metrics:
- `Delivery`: Successful deliveries
- `Bounce`: Hard and soft bounces
- `Complaint`: Spam complaints
- `Reject`: Rejected by SES (bad recipient)

```bash
# Get bounce rate
aws cloudwatch get-metric-statistics \
  --namespace AWS/SES \
  --metric-name Bounce \
  --start-time 2025-01-01T00:00:00Z \
  --end-time 2025-01-02T00:00:00Z \
  --period 86400 \
  --statistics Sum
```

### Reputation Dashboard

Check weekly:
- Bounce rate: Should be < 5%
- Complaint rate: Should be < 0.1%
- Sending reputation: Should be "High"

Access at: https://console.aws.amazon.com/ses/home?region=us-east-1#/reputation

### Best Practices

1. ✅ **Warm Up Your IP**: Gradually increase sending volume
2. ✅ **Clean Email List**: Remove bounces and complaints immediately
3. ✅ **Monitor Daily**: Check bounce/complaint rates
4. ✅ **Use Verified Domains**: Don't send from @gmail.com
5. ✅ **Include Unsubscribe**: Even for transactional emails
6. ✅ **Respect Preferences**: Honor unsubscribe requests instantly

## Troubleshooting

### Request Denied

Common reasons:
- Incomplete bounce/complaint handling
- Unclear use case description
- No website URL provided
- Suspicious sending patterns in sandbox

**Solution**: Address the issues and resubmit with more details.

### High Bounce Rate

If bounce rate > 10%:
1. Pause sending immediately
2. Clean email list
3. Investigate bounce reasons
4. Fix validation issues
5. Request review from AWS

### Sending Paused

If AWS pauses your account:
1. Check email for notification
2. Review bounce/complaint rates
3. Submit explanation and remediation plan
4. Wait for manual review (1-2 business days)

## Current Configuration

File: `.env` (line 49)
```bash
# AWS SES Configuration (Currently in SANDBOX - request production access)
AWS_SES_REGION=us-east-1
AWS_SES_FROM_EMAIL=noreply@starscreen.ai  # TODO: Replace with verified domain
```

## Action Required

- [ ] Configure SPF, DKIM, DMARC records
- [ ] Set up SNS bounce/complaint notifications
- [ ] Submit production access request
- [ ] Wait for approval (24-48 hours)
- [ ] Test email sending in production
- [ ] Set up CloudWatch alarms for bounce rate

## Support

- AWS SES Documentation: https://docs.aws.amazon.com/ses/
- AWS Support: Submit case via AWS Console
- Reputation Monitoring: https://console.aws.amazon.com/ses/home#/reputation
