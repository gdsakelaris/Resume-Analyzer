# Pricing & Subscription Implementation Guide

## ✅ What's Been Implemented

### 1. Pricing Page ([static/pricing.html](../static/pricing.html))
A beautiful, professional pricing page with:

**Pricing Tiers:**
- **Free**: $0/month - 10 candidates, basic features
- **Recruiter**: $49/mo ($39 annual) - 100 candidates
- **Small Business**: $149/mo ($119 annual) - 250 candidates ⭐ POPULAR
- **Professional**: $399/mo ($319 annual) - 1,000 candidates
- **Enterprise**: Custom pricing - Unlimited candidates

**Features:**
- Annual/monthly billing toggle (20% savings on annual)
- Responsive design matching your brand
- Feature comparison for each tier
- FAQ section
- Direct links to checkout or registration

**Access**: `http://your-domain.com/static/pricing.html`

---

### 2. Checkout Page ([static/checkout.html](../static/checkout.html))

Complete Stripe checkout integration with:

**Features:**
- Account creation OR login for existing users
- Stripe card element for secure payment
- 14-day free trial messaging
- Order summary with selected plan
- Terms & conditions checkbox
- Loading states and error handling

**Flow:**
1. User selects plan from pricing page
2. Redirected to checkout with plan pre-selected
3. Creates account (if new) or logs in
4. Enters payment information
5. Creates Stripe subscription with trial
6. Redirects to dashboard

**Access**: `/static/checkout.html?plan=starter&billing=monthly` (note: `starter` is the internal API value; displays as "Recruiter" to users)

---

### 3. Subscription Management API ([app/api/endpoints/subscriptions.py](../app/api/endpoints/subscriptions.py))

Complete backend for subscription management:

#### Endpoints Created:

**POST `/api/v1/subscriptions/create`**
- Creates Stripe customer and subscription
- Handles 14-day free trial
- Maps tiers to Stripe price IDs
- Updates local subscription record

**GET `/api/v1/subscriptions/current`**
- Returns user's current subscription details
- Shows usage (candidates used/remaining)
- Includes billing period info

**POST `/api/v1/subscriptions/portal`**
- Generates Stripe Customer Portal URL
- Allows users to self-manage:
  - Update payment methods
  - View invoices
  - Cancel subscription
  - Change plans

**POST `/api/v1/subscriptions/cancel`**
- Cancels subscription at period end
- Doesn't charge immediately

**POST `/api/v1/subscriptions/upgrade`**
- Upgrades or downgrades plan
- Prorates charges automatically
- Takes effect immediately

---

### 4. Configuration Updates ([app/core/config.py](../app/core/config.py))

Added new setting:
```python
FRONTEND_URL: str = "http://localhost:8000"  # For Stripe redirects
```

---

## ⏳ What You Need to Do Next

### 1. Set Up Stripe Account

1. **Create Stripe Account**: https://stripe.com
2. **Get API Keys**:
   - Dashboard → Developers → API Keys
   - Copy "Publishable key" (starts with `pk_`)
   - Copy "Secret key" (starts with `sk_`)

3. **Create Products & Prices**:
   ```
   Dashboard → Products → Create product

   Create 3 products:

   Product 1: "Recruiter Plan"
   - Monthly: $49 → Copy price ID
   - Annual: $468 ($39/mo × 12) → Copy price ID

   Product 2: "Small Business Plan"
   - Monthly: $149 → Copy price ID
   - Annual: $1,428 ($119/mo × 12) → Copy price ID

   Product 3: "Professional Plan"
   - Monthly: $399 → Copy price ID
   - Annual: $3,828 ($319/mo × 12) → Copy price ID
   ```

4. **Set Up Webhook**:
   ```
   Dashboard → Developers → Webhooks → Add endpoint

   Endpoint URL: https://your-domain.com/api/v1/webhooks/stripe

   Events to listen for:
   - customer.subscription.created
   - customer.subscription.updated
   - customer.subscription.deleted
   - invoice.payment_succeeded
   - invoice.payment_failed

   Copy "Signing secret" (starts with `whsec_`)
   ```

---

### 2. Update Environment Variables

Add to your `.env` file:

```bash
# Stripe Configuration
STRIPE_API_KEY=sk_test_YOUR_SECRET_KEY_HERE
STRIPE_WEBHOOK_SECRET=whsec_YOUR_WEBHOOK_SECRET_HERE

# Stripe Price IDs (Monthly)
STRIPE_PRICE_ID_STARTER=price_YOUR_STARTER_MONTHLY_PRICE_ID
STRIPE_PRICE_ID_SMALL_BUSINESS=price_YOUR_SMALL_BUSINESS_MONTHLY_PRICE_ID
STRIPE_PRICE_ID_PROFESSIONAL=price_YOUR_PROFESSIONAL_MONTHLY_PRICE_ID

# Frontend URL (for Stripe redirects)
FRONTEND_URL=http://44.223.41.116:8000  # Or your domain

# Enterprise pricing (optional)
STRIPE_PRICE_ID_ENTERPRISE=price_YOUR_ENTERPRISE_PRICE_ID
```

**On EC2**: Update `.env` on the server with production values

---

### 3. Update Checkout Page

Replace the Stripe publishable key in [static/checkout.html](../static/checkout.html):

**Line 167** (approximately):
```javascript
// Change this:
this.stripe = Stripe('pk_test_YOUR_STRIPE_PUBLISHABLE_KEY');

// To:
this.stripe = Stripe('pk_test_YOUR_ACTUAL_PUBLISHABLE_KEY');
// Or for production:
this.stripe = Stripe('pk_live_YOUR_LIVE_PUBLISHABLE_KEY');
```

---

### 4. Deploy to Production

```bash
# SSH into EC2
ssh starscreen-ec2

# Pull latest changes
cd ~/Resume-Analyzer
git pull

# Update .env with Stripe keys (see section 2 above)
nano .env

# Restart API to load new environment variables
docker-compose restart api
```

---

## 🎯 Testing the Flow

### Test Locally (Development)

1. **Start the app**:
   ```bash
   docker-compose up
   ```

2. **Visit pricing page**:
   ```
   http://localhost:8000/static/pricing.html
   ```

3. **Select a plan** → Click "Start Free Trial"

4. **Use Stripe test cards**:
   ```
   Success: 4242 4242 4242 4242
   Decline: 4000 0000 0000 0002

   Any future date, any 3-digit CVC
   ```

5. **Verify subscription created**:
   - Check database: `subscriptions` table
   - Check Stripe Dashboard: Customers & Subscriptions

### Test on Production

Same flow, but use:
- `http://44.223.41.116:8000/static/pricing.html`
- Real credit card for testing (Stripe test mode safe)

---

## 📋 Remaining Tasks

### Immediate (Required for Launch):

1. ✅ **Pricing page** - DONE
2. ✅ **Checkout page** - DONE
3. ✅ **Subscription API** - DONE
4. ⏳ **Add Stripe keys** - YOU DO THIS
5. ⏳ **Test subscription creation** - YOU DO THIS
6. ⏳ **Add subscription UI to main dashboard** - Optional but recommended
7. ⏳ **Add upgrade prompts when limit hit** - Optional but recommended

### Nice to Have:

8. Update registration flow to show pricing first
9. Add "Manage Billing" button in dashboard
10. Add usage meter showing "X/100 candidates used"
11. Email notifications for:
    - Trial ending soon
    - Payment failed
    - Subscription canceled

---

## 🔧 Integration with Main App

### Show Subscription Status in Dashboard

Add to [static/index.html](../static/index.html) header:

```html
<!-- In the navigation bar, after the "Connected" badge -->
<div x-data="{ subscription: null }" x-init="
    fetch('/api/v1/subscriptions/current', { headers: Auth.getAuthHeaders() })
        .then(r => r.json())
        .then(data => subscription = data)
">
    <template x-if="subscription">
        <a href="/static/pricing.html"
           class="text-sm px-3 py-1 rounded-full border"
           :class="subscription.plan === 'FREE' ? 'bg-slate-100 border-slate-300' : 'bg-brand-100 border-brand-300'">
            <span x-text="subscription.plan"></span>
            <span x-show="subscription.plan !== 'FREE'"
                  x-text="`(${subscription.remaining_candidates} left)`"></span>
        </a>
    </template>
</div>
```

### Add Upgrade Prompt When Limit Hit

In candidate upload handler (when 402 status returned):

```javascript
if (response.status === 402) {
    // Show upgrade modal
    const upgrade = confirm('You've reached your monthly limit. Upgrade your plan?');
    if (upgrade) {
        window.location.href = '/static/pricing.html';
    }
}
```

---

## 🎨 Customization Options

### Change Pricing:
Edit [static/pricing.html](../static/pricing.html) - search for price values

### Change Trial Period:
Edit [app/api/endpoints/subscriptions.py](../app/api/endpoints/subscriptions.py) line ~129:
```python
trial_period_days=14,  # Change to 7, 30, etc.
```

### Change Plan Features:
Edit [static/pricing.html](../static/pricing.html) - find the feature lists (`<ul>` tags)

### Change Candidate Limits:
Edit [app/api/endpoints/subscriptions.py](../app/api/endpoints/subscriptions.py):
```python
tier_mapping = {
    "STARTER": {
        "limit": 100,  # Change this
    },
    # ... etc
}
```

---

## 📚 Additional Resources

**Stripe Documentation:**
- https://stripe.com/docs/billing/subscriptions/trials
- https://stripe.com/docs/payments/save-and-reuse
- https://stripe.com/docs/billing/subscriptions/webhooks

**Testing:**
- https://stripe.com/docs/testing

---

## 🚀 Quick Start Checklist

- [ ] Create Stripe account
- [ ] Get API keys (publishable + secret)
- [ ] Create 3 products with pricing in Stripe
- [ ] Copy all price IDs
- [ ] Set up webhook endpoint
- [ ] Update `.env` with all Stripe values
- [ ] Update `checkout.html` with publishable key
- [ ] Deploy to production (git pull + restart)
- [ ] Test with Stripe test card
- [ ] Verify webhook receives events
- [ ] Test billing portal access
- [ ] Go live! 🎉

---

**Status**: Ready for Stripe Configuration
**Last Updated**: 2026-01-01
**Next Step**: Configure Stripe account and add API keys

