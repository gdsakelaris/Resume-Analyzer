# Stripe Pricing Setup Guide

This guide will walk you through setting up your Stripe pricing to match your pricing page.

## Current Pricing Structure

- **Free**: $0/month - 10 candidates
- **Recruiter**: $20/month ($16 annual) - 100 candidates
- **Small Business**: $149/month ($119 annual) - 1,000 candidates
- **Enterprise**: $399/month ($319 annual) + $0.25 per candidate - Unlimited

## Step 1: Create Stripe Products & Prices

You need to create price IDs in Stripe for each plan. Here's what you need:

### 1. Recruiter Plan
- **Product Name**: Recruiter
- **Monthly Price**: $20.00 USD
- **Annual Price**: $192.00 USD ($16/month billed annually)
- **Billing**: Recurring subscription

### 2. Small Business Plan
- **Product Name**: Small Business
- **Monthly Price**: $149.00 USD
- **Annual Price**: $1,428.00 USD ($119/month billed annually)
- **Billing**: Recurring subscription

### 3. Enterprise Plan (Base)
- **Product Name**: Enterprise (Base)
- **Monthly Price**: $399.00 USD
- **Annual Price**: $3,828.00 USD ($319/month billed annually)
- **Billing**: Recurring subscription

### 4. Enterprise Plan (Usage)
For the per-candidate charge on Enterprise, you'll need a **metered billing** price:
- **Product Name**: Enterprise Usage
- **Price**: $0.25 USD per candidate
- **Billing**: Usage-based/metered

## Step 2: Update Your .env File

After creating the prices in Stripe, update your `.env` file with the new price IDs:

```bash
# Stripe Price IDs
STRIPE_PRICE_ID_STARTER=price_xxxxxxxxxxxxx         # Recruiter monthly price
STRIPE_PRICE_ID_SMALL_BUSINESS=price_xxxxxxxxxxxxx  # Small Business monthly price
STRIPE_PRICE_ID_PROFESSIONAL=price_xxxxxxxxxxxxx    # Enterprise monthly price
```

**Note**: The current setup uses monthly prices. Annual billing would require additional logic to handle billing periods.

## Step 3: How to Create Prices in Stripe Dashboard

1. **Go to Stripe Dashboard** → https://dashboard.stripe.com/
2. **Navigate to Products** → Click "Products" in the left sidebar
3. **Create Each Product**:
   - Click "+ Add product"
   - Enter product name (e.g., "Recruiter")
   - Choose "Recurring" pricing model
   - Set the price and billing interval (monthly/yearly)
   - Click "Add product"
4. **Copy the Price ID**:
   - Click on the product you just created
   - Under "Pricing", you'll see the price ID (starts with `price_`)
   - Copy this ID to your `.env` file

## Step 4: Current Implementation Status

### ✅ What's Working:
- Pricing page displays all plans correctly
- "Current Plan" badge shows for authenticated users
- Button logic (Choose Plan vs Current Plan)
- Free plan signup redirects to registration
- Paid plans redirect to checkout

### ⚠️ What Needs Configuration:

#### A. Stripe Product/Price Setup
You need to create the actual products and prices in Stripe Dashboard and update the price IDs in `.env`.

#### B. Annual Billing Logic
Currently, the frontend shows annual pricing, but the backend only uses monthly prices. To support annual billing:

1. **Update the checkout page** to pass the billing period to the backend
2. **Create annual prices in Stripe** for each plan
3. **Update the backend** to select the correct price ID based on billing period

#### C. Enterprise Metered Billing
The Enterprise plan's per-candidate charge requires **Stripe metered billing**:

1. Create a metered price in Stripe for $0.25 per candidate
2. Update the subscription creation to include both:
   - Base subscription (monthly fee)
   - Metered price (per-candidate usage)
3. Implement usage reporting when candidates are processed

## Step 5: Testing the Flow

### Test Free Plan:
1. Go to pricing page (not logged in)
2. Click "Get Started" on Free plan
3. Should redirect to `/static/register.html`
4. Complete registration
5. User should have FREE plan with 10 candidates/month limit

### Test Paid Plans:
1. Go to pricing page (logged in)
2. Click "Choose Plan" on any paid tier
3. Should redirect to `/static/checkout.html?plan=TIER&billing=monthly`
4. Enter payment details
5. Complete checkout
6. Subscription should be created with ACTIVE status (no trial)
7. User should see updated candidate limit

## Step 6: What Happens After User Selects a Plan

### For Free Plan:
```
User clicks "Get Started"
  → Redirects to /static/register.html
  → User creates account
  → Subscription created with FREE plan (10 candidates)
```

### For Paid Plans:
```
User clicks "Choose Plan"
  → Redirects to /static/checkout.html?plan=starter&billing=monthly
  → User enters payment info
  → Stripe creates customer + payment method
  → Backend creates subscription (ACTIVE status, no trial)
  → User redirected back with updated plan
```

## Step 7: Verify Backend Configuration

Check these files are correctly configured:

### [app/api/endpoints/subscriptions.py](../app/api/endpoints/subscriptions.py)
- ✅ Candidate limits updated (100, 1000, 999999)
- ✅ Trial period removed (charges immediately)
- ✅ Status set to ACTIVE (not TRIALING)

### [app/core/config.py](../app/core/config.py)
- ✅ Stripe API keys configured
- ✅ Price ID environment variables defined

### [.env](../.env)
- ⚠️ Need to update with actual Stripe price IDs
- ✅ Webhook secret configured
- ✅ Frontend URL set to https://starscreen.net

## Step 8: Deployment Checklist

Before deploying to production:

1. ✅ Create all Stripe products and prices
2. ✅ Update `.env` with live price IDs
3. ✅ Verify webhook is receiving events at https://starscreen.net/api/v1/webhooks/stripe
4. ✅ Test complete signup flow for each plan
5. ✅ Verify candidate limits are enforced
6. ✅ Test plan upgrades/downgrades
7. ⚠️ Implement annual billing (if needed)
8. ⚠️ Implement Enterprise metered billing (if needed)

## Enterprise Plan Implementation (Advanced)

The Enterprise plan with per-candidate billing requires additional setup:

### Option 1: Track Usage Manually
- Base subscription: $399/month
- At billing cycle end, calculate total candidates used
- Create an invoice item for usage: `candidates_used * $0.25`
- Charge customer

### Option 2: Stripe Metered Billing (Recommended)
1. Create a subscription with two items:
   - Item 1: Base price ($399/month)
   - Item 2: Metered price ($0.25 per unit)
2. Report usage to Stripe each time a candidate is processed:
   ```python
   stripe.SubscriptionItem.create_usage_record(
       subscription_item_id,
       quantity=1,  # 1 candidate processed
       timestamp=int(time.time())
   )
   ```

## Next Steps

1. **Create Stripe Products**: Go to Stripe Dashboard and create all products/prices
2. **Update .env**: Add the price IDs to your local and EC2 `.env` files
3. **Restart Services**: On EC2, run `docker-compose restart api`
4. **Test Flow**: Try signing up for each plan and verify it works
5. **Monitor Webhooks**: Check Stripe Dashboard → Developers → Webhooks to see events

## Support Resources

- **Stripe Products**: https://dashboard.stripe.com/products
- **Stripe Webhooks**: https://dashboard.stripe.com/webhooks
- **Stripe Testing**: Use test cards from https://stripe.com/docs/testing

---

**Status**: Backend updated, awaiting Stripe product creation
**Last Updated**: 2026-01-01
