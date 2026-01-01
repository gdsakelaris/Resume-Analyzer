# Subscription System Testing Guide

**Date**: 2026-01-01
**Status**: Ready for End-to-End Testing

---

## ✅ Completed Implementation Tasks

All items from the immediate action plan have been completed:

1. ✅ **Fixed database access** - Fresh database with proper credentials
2. ✅ **Switched to Stripe test keys** - Using test mode for safe testing
3. ✅ **Decided on final pricing** - Option A pricing finalized across all files
4. ✅ **Documented tier names** - STARTER (code) = Recruiter (UI)
5. ✅ **Added usage display** - Dashboard shows plan, usage, and limits
6. ✅ **Added upgrade prompts** - Modal appears when limit is reached

---

## 🎯 Test Subscription Flow (Step-by-Step)

### Prerequisites

You need to complete these steps in Stripe Dashboard first:

#### 1. Create Test Mode Products in Stripe

Go to https://dashboard.stripe.com/test/products

**Product 1: Recruiter Plan**
- Name: "Recruiter Plan"
- Description: "For individual recruiters"
- Create two prices:
  - Monthly: $20.00 USD recurring
  - Annual: $192.00 USD recurring ($16/month)
- Copy both price IDs to `.env`

**Product 2: Small Business Plan**
- Name: "Small Business Plan"
- Description: "For small teams"
- Create two prices:
  - Monthly: $149.00 USD recurring
  - Annual: $1,428.00 USD recurring ($119/month)
- Copy both price IDs to `.env`

**Product 3: Professional Plan**
- Name: "Professional Plan"
- Description: "For growing companies"
- Create two prices:
  - Monthly: $399.00 USD recurring
  - Annual: $3,828.00 USD recurring ($319/month)
- Copy both price IDs to `.env`

#### 2. Update .env File

```bash
# Update these with your actual test mode price IDs from Stripe:
STRIPE_PRICE_ID_RECRUITER_MONTHLY=price_xxxxxxxxxxxxx
STRIPE_PRICE_ID_RECRUITER_YEARLY=price_xxxxxxxxxxxxx
STRIPE_PRICE_ID_SMALL_BUSINESS_MONTHLY=price_xxxxxxxxxxxxx
STRIPE_PRICE_ID_SMALL_BUSINESS_YEARLY=price_xxxxxxxxxxxxx
STRIPE_PRICE_ID_PROFESSIONAL_MONTHLY=price_xxxxxxxxxxxxx
STRIPE_PRICE_ID_PROFESSIONAL_YEARLY=price_xxxxxxxxxxxxx
```

#### 3. Restart API

```bash
docker-compose restart api
```

---

### Test Scenario 1: Free Tier Registration

**Goal**: Verify new users get FREE subscription automatically

```bash
# 1. Open browser
http://localhost:8000/static/register.html

# 2. Register new user
Email: test-free@example.com
Password: Test123!@#
Full Name: Free User
Company: Test Co

# 3. Expected results:
- Redirected to dashboard
- Top navigation shows "Free" badge
- Usage shows "10 left" (or current FREE_TIER_CANDIDATE_LIMIT)
```

**Verify in Database**:
```bash
docker-compose exec api python -c "from app.core.database import SessionLocal; from app.models.user import User; from app.models.subscription import Subscription; db = SessionLocal(); user = db.query(User).filter(User.email == 'test-free@example.com').first(); print(f'User: {user.email}'); print(f'Subscription Plan: {user.subscription.plan}'); print(f'Subscription Status: {user.subscription.status}'); print(f'Monthly Limit: {user.subscription.monthly_candidate_limit}'); db.close()"
```

**Expected Output**:
```
User: test-free@example.com
Subscription Plan: free
Subscription Status: active
Monthly Limit: 10
```

---

### Test Scenario 2: Paid Subscription (Recruiter Plan)

**Goal**: Test full payment flow with Stripe test card

```bash
# 1. From dashboard, click "Manage Billing" or go to:
http://localhost:8000/static/pricing.html

# 2. Click "Choose Plan" on Recruiter card
# 3. Redirected to checkout page
# 4. Fill payment form:

# Test Card Details (Stripe Test Mode):
Card Number: 4242 4242 4242 4242
Expiry: Any future date (e.g., 12/25)
CVC: Any 3 digits (e.g., 123)
ZIP: Any 5 digits (e.g., 12345)

# 5. Click "Subscribe Now"
```

**Expected Results**:
- Payment succeeds
- Redirected to dashboard
- Badge changes to "Recruiter"
- Usage shows "100 left"
- No errors in browser console

**Verify in Stripe Dashboard**:
1. Go to https://dashboard.stripe.com/test/customers
2. Find customer by email
3. Verify subscription is active
4. Check payment successful

**Verify in Database**:
```bash
docker-compose exec api python -c "from app.core.database import SessionLocal; from app.models.user import User; db = SessionLocal(); user = db.query(User).filter(User.email == 'test-free@example.com').first(); s = user.subscription; print(f'Plan: {s.plan}'); print(f'Status: {s.status}'); print(f'Stripe Customer ID: {s.stripe_customer_id}'); print(f'Stripe Subscription ID: {s.stripe_subscription_id}'); print(f'Limit: {s.monthly_candidate_limit}'); db.close()"
```

**Expected Output**:
```
Plan: starter
Status: active
Stripe Customer ID: cus_xxxxxxxxxxxxx
Stripe Subscription ID: sub_xxxxxxxxxxxxx
Limit: 100
```

---

### Test Scenario 3: Usage Tracking

**Goal**: Verify candidate uploads increment usage counter

```bash
# 1. Create a job from dashboard
Title: Test Job
Description: Looking for experienced developer

# 2. Upload a test resume
# Create test file first:
echo "John Doe - Software Engineer\n5 years Python experience" > test-resume.txt

# 3. Upload via UI or API:
curl -X POST http://localhost:8000/api/v1/jobs/1/candidates/upload \
  -H "Authorization: Bearer YOUR_ACCESS_TOKEN" \
  -F "file=@test-resume.txt"

# 4. Check usage updated in nav bar
# Should show "99 left" (if started at 100)
```

**Verify Usage Counter**:
```bash
docker-compose exec api python -c "from app.core.database import SessionLocal; from app.models.subscription import Subscription; db = SessionLocal(); s = db.query(Subscription).first(); print(f'Used: {s.candidates_used_this_month}/{s.monthly_candidate_limit}'); print(f'Remaining: {s.remaining_candidates}'); db.close()"
```

---

### Test Scenario 4: Limit Enforcement & Upgrade Modal

**Goal**: Verify upgrade modal appears when limit is reached

**Setup**: Set free tier to 1 candidate for quick testing
```bash
# Edit .env
FREE_TIER_CANDIDATE_LIMIT=1

# Restart API
docker-compose restart api

# Register new user or update existing FREE user
```

**Test Steps**:
1. Upload 1 resume (should succeed)
2. Try to upload 2nd resume
3. **Expected**: Upgrade modal appears with:
   - Warning icon
   - "Monthly Limit Reached" title
   - Error message from API
   - List of upgrade options (Recruiter, Small Business, Professional)
   - "View Plans" button → links to pricing page
   - "Cancel" button → closes modal

**Reset for Production**:
```bash
# Edit .env
FREE_TIER_CANDIDATE_LIMIT=10

# Restart
docker-compose restart api
```

---

### Test Scenario 5: Subscription API Endpoints

Test all subscription management endpoints:

**Get Current Subscription**:
```bash
curl -X GET http://localhost:8000/api/v1/subscriptions/current \
  -H "Authorization: Bearer YOUR_ACCESS_TOKEN"
```

**Expected Response**:
```json
{
  "id": "uuid-here",
  "user_id": "uuid-here",
  "plan": "starter",
  "status": "active",
  "monthly_candidate_limit": 100,
  "candidates_used_this_month": 5,
  "remaining_candidates": 95,
  "usage_percentage": 5.0,
  "stripe_customer_id": "cus_xxxxx",
  "stripe_subscription_id": "sub_xxxxx",
  "current_period_start": "2026-01-01T00:00:00",
  "current_period_end": "2026-02-01T00:00:00"
}
```

**Access Billing Portal**:
```bash
curl -X POST http://localhost:8000/api/v1/subscriptions/portal \
  -H "Authorization: Bearer YOUR_ACCESS_TOKEN"
```

**Expected Response**:
```json
{
  "url": "https://billing.stripe.com/session/xxxxx"
}
```

---

## 🔍 Webhook Testing

### Setup Stripe Webhook

#### Option 1: Use Stripe CLI (Recommended for Local Testing)

```bash
# Install Stripe CLI: https://stripe.com/docs/stripe-cli

# Login to Stripe
stripe login

# Forward webhooks to local server
stripe listen --forward-to localhost:8000/api/v1/webhooks/stripe

# Copy the webhook signing secret (starts with whsec_)
# Update .env:
STRIPE_WEBHOOK_SECRET=whsec_xxxxxxxxxxxxx

# Restart API
docker-compose restart api
```

#### Option 2: Use ngrok for Public URL

```bash
# Install ngrok: https://ngrok.com/

# Start ngrok tunnel
ngrok http 8000

# Copy the HTTPS URL (e.g., https://abc123.ngrok.io)

# Go to Stripe Dashboard → Developers → Webhooks
# Add endpoint: https://abc123.ngrok.io/api/v1/webhooks/stripe
# Select events:
- customer.subscription.created
- customer.subscription.updated
- customer.subscription.deleted
- invoice.payment_succeeded
- invoice.payment_failed

# Copy webhook signing secret
# Update .env with the secret
# Restart API
```

### Verify Webhook Events

**Test Payment Success**:
1. Subscribe to a plan (Scenario 2 above)
2. Check Stripe Dashboard → Developers → Webhooks → Your endpoint
3. Verify these events were received:
   - ✅ `customer.subscription.created`
   - ✅ `invoice.payment_succeeded`

**Check API Logs**:
```bash
docker-compose logs api | grep "webhook"
```

**Look for**:
```
Received Stripe webhook: customer.subscription.created
Processing subscription created event
Subscription status updated to: active
```

**Test Payment Failure** (Optional):
Use Stripe test card that declines: `4000 0000 0000 0002`

**Test Subscription Cancellation**:
```bash
# Via Stripe Dashboard:
1. Go to Customers → Find your test customer
2. Click on subscription
3. Click "Cancel subscription"
4. Select "Cancel immediately"

# Verify webhook received: customer.subscription.deleted
# Verify database updated: status = canceled
```

---

## 🎨 UI Features to Test

### Navigation Bar Usage Display

**Verify These Elements Appear**:
- [x] Plan badge (Free, Recruiter, Small Business, etc.)
- [x] Usage indicator ("X left") - color changes based on usage:
  - Green: < 70% used
  - Yellow: 70-90% used
  - Red: ≥ 90% used
- [x] Tooltip on hover showing:
  - Usage this month: X/100
  - Progress bar
  - Reset date OR warning if near limit
- [x] "∞ Unlimited" badge for Professional/Enterprise plans

### Upgrade Modal

**Trigger Conditions**:
- 402 status code from candidate upload
- Stops processing remaining files in multi-upload

**Modal Content**:
- Yellow warning icon
- "Monthly Limit Reached" title
- Custom error message from API
- List of upgrade tiers with prices
- "View Plans" CTA button
- "Cancel" button

---

## ⚠️ Common Issues & Solutions

### Issue: Price ID Not Found

**Error**: "No such price: 'price_TEST_RECRUITER_MONTHLY'"

**Solution**:
1. Verify price IDs in `.env` match Stripe Dashboard
2. Make sure you're using TEST mode price IDs (start with `price_`)
3. Restart API after updating `.env`

### Issue: Webhook Signature Verification Failed

**Error**: "Invalid signature"

**Solution**:
1. Verify `STRIPE_WEBHOOK_SECRET` in `.env` matches Stripe Dashboard
2. If using Stripe CLI, use the secret from `stripe listen` output
3. If using ngrok/production webhook, use secret from Stripe Dashboard

### Issue: Usage Not Updating

**Symptoms**: Uploaded resume but counter still shows same number

**Debug**:
```bash
# Check API logs
docker-compose logs api | grep "candidates_used"

# Verify database
docker-compose exec api python -c "from app.core.database import SessionLocal; from app.models.subscription import Subscription; db = SessionLocal(); s = db.query(Subscription).first(); print(f'Used: {s.candidates_used_this_month}'); db.close()"

# Check endpoint response
curl -X GET http://localhost:8000/api/v1/subscriptions/current \
  -H "Authorization: Bearer TOKEN" | jq '.candidates_used_this_month'
```

### Issue: Upgrade Modal Not Appearing

**Debug**:
1. Check browser console for JavaScript errors
2. Verify `upgradeModal` state in Alpine DevTools
3. Test 402 response manually:
```bash
# Should return 402 if at limit
curl -X POST http://localhost:8000/api/v1/jobs/1/candidates/upload \
  -H "Authorization: Bearer TOKEN" \
  -F "file=@test.txt" \
  -v
```

---

## 📊 Success Criteria Checklist

Before considering testing complete, verify ALL of these:

### Registration & Authentication
- [ ] New user registration creates FREE subscription
- [ ] User can login and see dashboard
- [ ] JWT tokens work and refresh properly

### Subscription Management
- [ ] Can view current subscription via API
- [ ] Can subscribe to Recruiter plan
- [ ] Can subscribe to Small Business plan
- [ ] Can subscribe to Professional plan
- [ ] Stripe customer record created
- [ ] Stripe subscription record created
- [ ] Database subscription record updated with Stripe IDs
- [ ] Subscription status is "active"

### Usage Tracking
- [ ] Uploading resume increments counter
- [ ] Counter displays correctly in nav bar
- [ ] Usage percentage calculates correctly
- [ ] Tooltip shows correct information

### Limit Enforcement
- [ ] Cannot upload beyond monthly limit
- [ ] 402 error returned when limit reached
- [ ] Upgrade modal appears automatically
- [ ] Modal shows correct error message
- [ ] "View Plans" button links to pricing page

### Webhooks
- [ ] `customer.subscription.created` event received
- [ ] `invoice.payment_succeeded` event received
- [ ] Subscription status updated via webhook
- [ ] Usage counter resets on new billing period (simulated)

### UI/UX
- [ ] Plan badge shows correct tier name (Recruiter, not STARTER)
- [ ] Usage colors change based on percentage (green/yellow/red)
- [ ] Unlimited badge shows for Professional/Enterprise
- [ ] No JavaScript errors in console
- [ ] Mobile responsive design works

---

## 🚀 Next Steps After Testing

Once all tests pass:

1. **Create Live Mode Products** in Stripe (repeat setup with live keys)
2. **Update Production .env** with live keys and price IDs
3. **Deploy to EC2** with updated configuration
4. **Set up Production Webhook** pointing to https://starscreen.net
5. **Test Production Flow** with real card (small charge, then refund)
6. **Monitor Logs** for first few days
7. **Set up Stripe Email Notifications** for failed payments

---

## 📞 Support Resources

- **Stripe Test Cards**: https://stripe.com/docs/testing
- **Stripe Webhook Testing**: https://stripe.com/docs/webhooks/test
- **Stripe CLI Docs**: https://stripe.com/docs/stripe-cli
- **API Documentation**: http://localhost:8000/docs

---

**Status**: Ready for comprehensive testing
**Updated**: 2026-01-01
