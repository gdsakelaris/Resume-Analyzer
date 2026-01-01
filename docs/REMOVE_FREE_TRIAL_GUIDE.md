# Remove Free Trial & Add Current Plan Display Guide

## Summary of Changes Needed

To remove free trials and show users their current plan, we need to make changes across multiple files:

---

## 1. Frontend Changes

### A. [static/pricing.html](../static/pricing.html)

**Changes Made:**
- ✅ Added Subscription button back to navbar
- ✅ Added current plan indicator in hero section

**Changes Still Needed:**
- Replace all "Start Free Trial" / "Get Started Free" buttons with:
  - "Current Plan" (disabled) if user is on that plan
  - "Select Plan" for other plans
- Remove "14-day free trial" messaging from card descriptions
- Update JavaScript to:
  - Fetch user's current subscription from `/api/v1/subscriptions/current`
  - Store current plan in Alpine.js state
  - Conditionally render button text/state based on current plan

**Button Logic:**
```javascript
// For each pricing tier card:
- If tier === currentPlan: Show "Current Plan" button (disabled, different styling)
- Else: Show "Select Plan" button (clickable, goes to checkout)
```

### B. [static/checkout.html](../static/checkout.html)

**Changes Needed:**
- Remove "Free Trial" messaging from:
  - Order summary section
  - Payment information banner ("You won't be charged today...")
  - Any "Start Free Trial" button text → change to "Subscribe Now" or "Confirm Subscription"
- Update checkout flow to charge immediately instead of after 14 days

---

## 2. Backend Changes

### A. [app/api/endpoints/subscriptions.py](../app/api/endpoints/subscriptions.py)

**Line ~135:** Remove trial period from subscription creation

**Current code:**
```python
stripe_subscription = stripe.Subscription.create(
    customer=subscription.stripe_customer_id,
    items=[{'price': tier_config['price_id']}],
    trial_period_days=14,  # ← REMOVE THIS LINE
    metadata={...}
)
```

**Updated code:**
```python
stripe_subscription = stripe.Subscription.create(
    customer=subscription.stripe_customer_id,
    items=[{'price': tier_config['price_id']}],
    # No trial period - charge immediately
    metadata={...}
)
```

**Line ~146:** Update status from TRIALING to ACTIVE

**Current code:**
```python
subscription.status = SubscriptionStatus.TRIALING  # ← CHANGE THIS
```

**Updated code:**
```python
subscription.status = SubscriptionStatus.ACTIVE
```

---

## 3. Step-by-Step Implementation

### Step 1: Update Backend (Do this first!)

```bash
# Edit app/api/endpoints/subscriptions.py
# Remove trial_period_days=14 from line ~135
# Change TRIALING to ACTIVE on line ~146

# Restart API
docker-compose restart api
```

### Step 2: Update Pricing Page Buttons

Edit `static/pricing.html` and replace all button sections:

**Free Plan:**
```html
<button @click="selectPlan('free', billingPeriod)"
        :disabled="currentPlan === 'FREE'"
        :class="currentPlan === 'FREE' ? 'bg-slate-400 cursor-not-allowed' : 'bg-brand-600 hover:bg-brand-700'"
        class="w-full text-white font-semibold py-3 rounded-lg transition">
    <span x-text="currentPlan === 'FREE' ? 'Current Plan' : 'Select Plan'"></span>
</button>
```

**Starter Plan:**
```html
<button @click="selectPlan('starter', billingPeriod)"
        :disabled="currentPlan === 'STARTER'"
        :class="currentPlan === 'STARTER' ? 'bg-slate-400 cursor-not-allowed' : 'bg-brand-600 hover:bg-brand-700'"
        class="w-full text-white font-semibold py-3 rounded-lg transition">
    <span x-text="currentPlan === 'STARTER' ? 'Current Plan' : 'Select Plan'"></span>
</button>
```

**Small Business Plan:**
```html
<button @click="selectPlan('small_business', billingPeriod)"
        :disabled="currentPlan === 'SMALL_BUSINESS'"
        :class="currentPlan === 'SMALL_BUSINESS' ? 'bg-slate-400 cursor-not-allowed' : 'bg-brand-600 hover:bg-brand-700'"
        class="w-full text-white font-semibold py-3 rounded-lg transition">
    <span x-text="currentPlan === 'SMALL_BUSINESS' ? 'Current Plan' : 'Select Plan'"></span>
</button>
```

**Professional Plan:**
```html
<button @click="selectPlan('professional', billingPeriod)"
        :disabled="currentPlan === 'PROFESSIONAL'"
        :class="currentPlan === 'PROFESSIONAL' ? 'bg-slate-400 cursor-not-allowed' : 'bg-brand-600 hover:bg-brand-700'"
        class="w-full text-white font-semibold py-3 rounded-lg transition">
    <span x-text="currentPlan === 'PROFESSIONAL' ? 'Current Plan' : 'Select Plan'"></span>
</button>
```

### Step 3: Update Pricing Page JavaScript

In the `pricingPage()` function, add:

```javascript
function pricingPage() {
    return {
        billingPeriod: 'monthly',
        isAuthenticated: false,
        currentPlan: null,  // Add this

        async init() {
            this.isAuthenticated = Auth.isAuthenticated();

            // Fetch current subscription if authenticated
            if (this.isAuthenticated) {
                await this.fetchCurrentSubscription();
            }
        },

        async fetchCurrentSubscription() {
            try {
                const response = await Auth.fetch('/api/v1/subscriptions/current');
                if (response.ok) {
                    const data = await response.json();
                    this.currentPlan = data.plan;  // 'FREE', 'STARTER', etc.
                }
            } catch (error) {
                console.error('Failed to fetch subscription:', error);
            }
        },

        selectPlan(tier, period = 'monthly') {
            // Don't allow selecting current plan
            if (tier.toUpperCase() === this.currentPlan) {
                return;
            }

            if (tier === 'free') {
                window.location.href = '/static/register.html';
            } else {
                const params = new URLSearchParams({
                    plan: tier,
                    billing: period
                });
                window.location.href = `/static/checkout.html?${params.toString()}`;
            }
        }
    }
}
```

### Step 4: Update Checkout Page

Search for and replace in `static/checkout.html`:

**Find:** "14-day free trial"
**Replace with:** Remove this messaging entirely

**Find:** "You won't be charged today"
**Replace with:** "Your subscription will begin immediately"

**Find:** "Start Free Trial" (button text)
**Replace with:** "Subscribe Now"

**Find:** "trial_end" or similar references
**Replace/Remove:** These are no longer needed

### Step 5: Test the Flow

1. Log in as a user
2. Go to `/static/pricing.html`
3. Verify current plan shows at top
4. Verify current plan button shows "Current Plan" and is disabled
5. Click "Select Plan" on another tier
6. Verify checkout shows immediate billing (no trial messaging)
7. Complete checkout
8. Verify subscription is ACTIVE immediately
9. Return to pricing page - verify new plan shows as current

---

## 4. Quick Reference: Files to Modify

1. ✅ `static/pricing.html` - Partially done (navbar + current plan indicator)
2. ❌ `static/pricing.html` - Need to update buttons and JavaScript
3. ❌ `static/checkout.html` - Remove trial messaging
4. ❌ `app/api/endpoints/subscriptions.py` - Remove `trial_period_days=14`
5. ❌ `app/api/endpoints/subscriptions.py` - Change TRIALING to ACTIVE

---

## 5. Expected Behavior After Changes

**For authenticated users:**
- See their current plan at the top of pricing page
- Current plan button is disabled and shows "Current Plan"
- Other plans show "Select Plan" button
- Clicking "Select Plan" goes to checkout
- Checkout charges immediately (no trial)
- Subscription becomes ACTIVE right away

**For unauthenticated users:**
- See all plans with "Select Plan" buttons
- Free plan shows "Get Started" → goes to registration
- Paid plans go to checkout (which handles registration)

---

**Status**: Guide created - ready for implementation
**Last Updated**: 2026-01-01
