# Stripe Setup - Quick Reference

**Status**: Backend configured, awaiting Stripe product creation

---

## Current Pricing Structure

| Plan | Monthly | Annual | Candidates | Features |
|------|---------|--------|------------|----------|
| **Free** | $0 | $0 | 10* | Basic testing |
| **Recruiter** | $20 | $16/mo | 100 | Individual recruiters |
| **Small Business** | $149 | $119/mo | 1,000 | Growing teams, multi-user |
| **Enterprise** | $399 | $319/mo | Unlimited | +$0.25 per candidate |

*Currently set to 999999 for testing via `FREE_TIER_CANDIDATE_LIMIT` in `.env`

---

## Setup Steps

### 1. Create Stripe Products
Go to https://dashboard.stripe.com/products and create:

**Recruiter Plan**:
- Monthly: $20.00 USD (recurring)
- Annual: $192.00 USD ($16/month * 12)

**Small Business Plan**:
- Monthly: $149.00 USD (recurring)
- Annual: $1,428.00 USD ($119/month * 12)

**Enterprise Plan (Base)**:
- Monthly: $399.00 USD (recurring)
- Annual: $3,828.00 USD ($319/month * 12)

**Enterprise Plan (Usage)** - Metered billing:
- Price: $0.25 USD per candidate (usage-based)

### 2. Update Environment Variables
After creating prices, copy the price IDs to `.env`:

```bash
STRIPE_PRICE_ID_STARTER=price_xxxxxxxxxxxxx         # Recruiter monthly
STRIPE_PRICE_ID_SMALL_BUSINESS=price_xxxxxxxxxxxxx  # Small Business monthly
STRIPE_PRICE_ID_PROFESSIONAL=price_xxxxxxxxxxxxx    # Enterprise monthly
```

**Important**: Update `.env` on both local machine AND EC2 server.

### 3. Restart Services on EC2
```bash
ssh ubuntu@starscreen.net
docker-compose restart api
```

---

## Current Implementation

### ✅ Working
- Pricing page displays all plans correctly
- "Current Plan" badge shows for authenticated users
- Free plan redirects to registration
- Paid plans redirect to checkout
- Immediate billing (no trial period)
- Candidate limits enforced: 100, 1,000, unlimited

### ⚠️ Not Yet Implemented
- **Annual billing**: Frontend shows annual pricing, but backend only supports monthly
- **Enterprise metered billing**: $0.25 per candidate requires Stripe usage reporting

---

## Subscription Flow

### Free Plan
```
User clicks "Get Started"
→ /static/register.html
→ User creates account
→ Subscription: plan=FREE, status=ACTIVE, limit=FREE_TIER_CANDIDATE_LIMIT
```

### Paid Plans
```
User clicks "Choose Plan"
→ /static/checkout.html?plan=starter&billing=monthly
→ User enters payment info (Stripe Elements)
→ Backend creates Stripe customer + subscription
→ Subscription: plan=STARTER, status=ACTIVE (immediate charge, no trial)
→ Redirect to dashboard with updated plan
```

---

## Backend Files

### [app/api/endpoints/subscriptions.py](../app/api/endpoints/subscriptions.py)
- **Line 78-94**: Tier mapping (limits: 100, 1000, 999999)
- **Line 129-140**: Subscription creation (no trial, immediate charge)
- **Line 145**: Status set to `ACTIVE`

### [app/core/config.py](../app/core/config.py)
- **Line 46-52**: Stripe API key and price ID settings
- **Line 62**: `FREE_TIER_CANDIDATE_LIMIT` setting

### [app/models/subscription.py](../app/models/subscription.py)
- **Line 54**: FREE tier limit reads from `settings.FREE_TIER_CANDIDATE_LIMIT`
- **Line 131-135**: `can_upload_candidate` property checks limits and status

---

## Testing Checklist

- [ ] Create Stripe products in dashboard
- [ ] Update `.env` with live price IDs (local + EC2)
- [ ] Restart API on EC2
- [ ] Test Free plan signup
- [ ] Test Recruiter plan checkout
- [ ] Test Small Business plan checkout
- [ ] Test Enterprise plan checkout (note: metered billing not implemented yet)
- [ ] Verify candidate limits are enforced
- [ ] Test plan upgrades/downgrades via billing portal
- [ ] Verify webhooks receiving events at https://starscreen.net/api/v1/webhooks/stripe

---

## Enterprise Metered Billing (Future)

To implement $0.25 per candidate for Enterprise:

```python
# When a candidate is uploaded (app/api/endpoints/candidates.py):
if subscription.plan == SubscriptionPlan.ENTERPRISE:
    # Report usage to Stripe
    stripe.SubscriptionItem.create_usage_record(
        subscription_item_id,  # From subscription metadata
        quantity=1,  # 1 candidate processed
        timestamp=int(time.time())
    )
```

---

## Resources

- **Stripe Dashboard**: https://dashboard.stripe.com/
- **Webhooks**: https://dashboard.stripe.com/webhooks
- **Testing Cards**: https://stripe.com/docs/testing

---

**Last Updated**: 2026-01-01
