# Setting Up support@starscreen.net with Resend

This guide walks you through configuring incoming email support using Resend's receiving feature.

## Overview

When someone sends an email to `support@starscreen.net`, Resend will:
1. Receive the email
2. Send a webhook POST request to your API
3. Your API fetches the full email content
4. Your API forwards it to your personal email
5. You can reply directly from your email client

---

## Step 1: Update Your Personal Email (2 mins)

Edit the `.env` file and replace the placeholder with your actual email:

```bash
# Change this line:
SUPPORT_FORWARD_EMAIL=your_personal_email@gmail.com

# To something like:
SUPPORT_FORWARD_EMAIL=george@yourdomain.com
```

---

## Step 2: Add MX Records to Your DNS (5 mins)

Go to wherever you manage DNS for `starscreen.net` (Namecheap, GoDaddy, Route 53, Cloudflare, etc.)

**Add this DNS record:**

```
Type:     MX
Name:     @          (or leave blank, depending on your DNS provider)
Value:    inbound-smtp.resend.com
Priority: 10
TTL:      Auto (or 3600)
```

**Save the record.** DNS changes can take 1-48 hours to propagate (usually 15 minutes).

### Verify DNS propagation:
```bash
# On Windows:
nslookup -type=MX starscreen.net

# You should see:
# starscreen.net MX preference = 10, mail exchanger = inbound-smtp.resend.com
```

---

## Step 3: Configure Webhook in Resend Dashboard (3 mins)

1. Go to https://resend.com/webhooks
2. Click **"Add Webhook"**
3. Fill in the form:

   - **Endpoint URL:** `https://starscreen.net/api/v1/webhooks/resend`
   - **Event types:** Check `email.received`
   - **Description:** "Forward support emails"

4. Click **"Add"**

Resend will now POST to your API whenever an email is received.

---

## Step 4: Deploy the Code (10 mins)

### Option A: Deploy via SSH

```bash
# From your local machine:
ssh ubuntu@54.158.113.25

# On the EC2 instance:
cd Resume-Analyzer
git pull origin main

# Restart the API container to load new code:
docker-compose restart api

# Check logs to verify it's running:
docker-compose logs -f api
```

### Option B: Deploy from your local machine

```bash
# Make sure you've committed your changes:
git add .
git commit -m "Add support email receiving webhook"
git push origin main

# Then SSH in and pull:
ssh ubuntu@54.158.113.25 "cd Resume-Analyzer && git pull && docker-compose restart api"
```

---

## Step 5: Test It (2 mins)

1. Send a test email to `support@starscreen.net` from your personal email
2. Check your inbox (the email you set in `SUPPORT_FORWARD_EMAIL`)
3. You should receive a nicely formatted email with:
   - Original sender's email
   - Subject line
   - Message body
   - A "Reply-To" header set to the original sender

4. Click **Reply** in your email client - it should automatically address the original sender

---

## Troubleshooting

### "Email not being received"

**Check DNS:**
```bash
nslookup -type=MX starscreen.net
```
Should return `inbound-smtp.resend.com`

**Check Resend Logs:**
- Go to https://resend.com/emails
- Click the "Receiving" tab
- Look for your test email

**Check API Logs:**
```bash
ssh ubuntu@54.158.113.25
cd Resume-Analyzer
docker-compose logs --tail=50 api | grep "Resend webhook"
```

---

### "Webhook not being called"

**Verify webhook URL is correct:**
- Go to https://resend.com/webhooks
- Make sure URL is: `https://starscreen.net/api/v1/webhooks/resend`
- Make sure `email.received` event is checked

**Test webhook manually:**
```bash
# From your local machine, simulate a webhook:
curl -X POST https://starscreen.net/api/v1/webhooks/resend \
  -H "Content-Type: application/json" \
  -d '{
    "type": "email.received",
    "data": {
      "email_id": "test-123",
      "from": "test@example.com",
      "to": ["support@starscreen.net"],
      "subject": "Test Subject"
    }
  }'
```

---

### "Email forwarded but has no content"

This is expected on the first test! The test webhook above won't have actual content.

When a real email comes in, Resend fetches the content via their API using the `email_id`.

---

## How It Works

```
Customer sends email to support@starscreen.net
              ↓
Resend receives email (via MX record)
              ↓
Resend sends webhook to your API: POST /api/v1/webhooks/resend
              ↓
Your API fetches full email content via Resend API
              ↓
Your API forwards email to SUPPORT_FORWARD_EMAIL
              ↓
You receive email in your personal inbox
              ↓
You click Reply and respond directly to customer
```

---

## Next Steps (Optional Enhancements)

### 1. **Database Support Ticket Tracking**
Store support emails in your database for tracking:

```python
# Add a SupportTicket model:
class SupportTicket(Base):
    id = Column(UUID, primary_key=True, default=uuid.uuid4)
    email_id = Column(String, unique=True)  # Resend email ID
    from_email = Column(String)
    subject = Column(String)
    body = Column(Text)
    status = Column(Enum('open', 'closed'))  # Track if resolved
    created_at = Column(DateTime, default=datetime.utcnow)
```

### 2. **Auto-Reply to Support Emails**
Send an automated "We received your message" email:

```python
# In handle_email_received():
resend.Emails.send({
    "from": "Starscreen Support <support@starscreen.net>",
    "to": [from_email],
    "subject": f"Re: {subject}",
    "html": "Thanks for contacting Starscreen! We'll respond within 24 hours."
})
```

### 3. **Support Dashboard**
Add a page to your admin panel to view all support tickets:

```
GET /api/v1/admin/support-tickets
```

Shows list of all emails received, their status, etc.

---

## Cost

Resend's free tier includes:
- **3,000 emails/month** (sending)
- **Unlimited receiving** (no charge for incoming emails)

You're well within the free tier for support emails.

---

## Security Notes

- Resend doesn't currently provide webhook signature verification
- Your webhook endpoint is public (anyone can POST to it)
- Consider adding IP allowlisting for Resend's webhook IPs (ask Resend support for their IP ranges)
- Or add a secret token in the webhook URL: `/api/v1/webhooks/resend?token=SECRET`

---

## Questions?

If you run into issues, check:
1. Resend dashboard → Receiving tab (see if emails are arriving)
2. Docker logs: `docker-compose logs -f api`
3. DNS propagation: `nslookup -type=MX starscreen.net`
