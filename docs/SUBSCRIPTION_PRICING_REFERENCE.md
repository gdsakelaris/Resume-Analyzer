# Subscription Pricing Reference

**Last Updated**: 2026-01-01
**Status**: ✅ Finalized and Consistent Across All Files

---

## Official Pricing Structure

This is the **authoritative source** for all pricing information. All code, documentation, and UI must match these values.

### Pricing Tiers

| Tier | Code Name | Display Name | Monthly Price | Annual Price | Candidates/Month | Cost Per Candidate |
|------|-----------|--------------|---------------|--------------|------------------|-------------------|
| 1 | `FREE` | **Free** | $0 | $0 | 10 | Free |
| 2 | `STARTER` | **Recruiter** | $20 | $16/mo ($192/yr) | 100 | $0.20 |
| 3 | `SMALL_BUSINESS` | **Small Business** | $149 | $119/mo ($1,428/yr) | 1,000 | $0.149 |
| 4 | `PROFESSIONAL` | **Professional** | $399 | $319/mo ($3,828/yr) | Unlimited | $0 |
| 5 | `ENTERPRISE` | **Enterprise** | $500 base + $0.25/candidate | $400 base + $0.25/candidate | Unlimited | Variable |

**Annual Discount**: 20% off monthly price

---

## Naming Conventions

### Code (Database Enums)
```python
class SubscriptionPlan(str, enum.Enum):
    FREE = "free"
    STARTER = "starter"
    SMALL_BUSINESS = "small_business"
    PROFESSIONAL = "professional"
    ENTERPRISE = "enterprise"
```

### User-Facing (UI Display Names)
- `FREE` → **Free**
- `STARTER` → **Recruiter**
- `SMALL_BUSINESS` → **Small Business**
- `PROFESSIONAL` → **Professional**
- `ENTERPRISE` → **Enterprise**

**Why the difference?**
- Database uses lowercase with underscores for consistency (SQL naming convention)
- UI uses marketing-friendly names that are clear to users
- The `display_name` property in the model handles the conversion

---

## Files Updated with Correct Pricing

### Backend
- ✅ [app/models/subscription.py](../app/models/subscription.py)
  - `base_price_usd` property
  - `per_candidate_price_usd` property
  - `monthly_limit` property
  - `display_name` property (NEW)

### Frontend
- ✅ [static/pricing.html](../static/pricing.html)
  - Free: $0/mo
  - Recruiter: $20/mo or $16/mo annual
  - Small Business: $149/mo or $119/mo annual
  - Professional: $399/mo or $319/mo annual

### Configuration
- ✅ [.env](.env)
  - `FREE_TIER_CANDIDATE_LIMIT=10`
  - Stripe test keys configured
  - Price IDs placeholder (need to create in Stripe)

---

## Stripe Configuration Required

### Test Mode Products to Create

Go to Stripe Dashboard → Products → Create Product

#### 1. Recruiter Plan
**Product Name**: Recruiter Plan
**Description**: For individual recruiters - 100 candidates/month

**Prices**:
- **Monthly**: $20.00 USD recurring → Save price ID to `STRIPE_PRICE_ID_RECRUITER_MONTHLY`
- **Annual**: $192.00 USD recurring → Save price ID to `STRIPE_PRICE_ID_RECRUITER_YEARLY`

#### 2. Small Business Plan
**Product Name**: Small Business Plan
**Description**: For small teams - 1,000 candidates/month

**Prices**:
- **Monthly**: $149.00 USD recurring → Save price ID to `STRIPE_PRICE_ID_SMALL_BUSINESS_MONTHLY`
- **Annual**: $1,428.00 USD recurring → Save price ID to `STRIPE_PRICE_ID_SMALL_BUSINESS_YEARLY`

#### 3. Professional Plan
**Product Name**: Professional Plan
**Description**: For growing companies - Unlimited candidates

**Prices**:
- **Monthly**: $399.00 USD recurring → Save price ID to `STRIPE_PRICE_ID_PROFESSIONAL_MONTHLY`
- **Annual**: $3,828.00 USD recurring → Save price ID to `STRIPE_PRICE_ID_PROFESSIONAL_YEARLY`

#### 4. Enterprise Plan (Optional - Complex Setup)
**Product Name**: Enterprise Plan
**Description**: High-volume recruiting with metered billing

**Prices**:
- **Monthly Base**: $500.00 USD recurring → Save price ID to `STRIPE_PRICE_ID_ENTERPRISE_MONTHLY`
- **Annual Base**: $4,800.00 USD recurring → Save price ID to `STRIPE_PRICE_ID_ENTERPRISE_YEARLY`
- **Usage**: $0.25 USD per candidate (metered billing) → Requires Stripe usage reporting API integration

**Note**: Enterprise metered billing is NOT fully implemented yet. For now, just create the base subscription price.

---

## Implementation Details

### Free Tier
- **Default for new signups** via [app/api/endpoints/auth.py](../app/api/endpoints/auth.py:75)
- Limit configured in `.env` as `FREE_TIER_CANDIDATE_LIMIT`
- Currently set to `10` (production value)
- Can be increased to `999999` for testing

### Candidate Limits Enforcement
Location: [app/api/endpoints/candidates.py](../app/api/endpoints/candidates.py)

```python
# Before each upload:
if not subscription.can_upload_candidate:
    raise HTTPException(
        status_code=402,
        detail=f"Monthly candidate limit reached ({subscription.candidates_used_this_month}/{subscription.monthly_candidate_limit})"
    )

# After successful upload:
subscription.candidates_used_this_month += 1
db.commit()
```

### Usage Reset
- Should happen automatically via Stripe webhook: `invoice.payment_succeeded`
- Location: [app/api/endpoints/stripe_webhooks.py](../app/api/endpoints/stripe_webhooks.py)
- Resets `candidates_used_this_month = 0` at the start of each billing period

### Unlimited Plans
- `PROFESSIONAL` and `ENTERPRISE` have `monthly_limit = 999999`
- The `can_upload_candidate` property returns `True` automatically for these plans

---

## Testing Checklist

### Before Going to Production

- [ ] Create all test mode products in Stripe dashboard
- [ ] Update `.env` with all test mode price IDs
- [ ] Restart API: `docker-compose restart api`
- [ ] Test signup flow (creates FREE subscription)
- [ ] Test upgrade to Recruiter plan with test card `4242 4242 4242 4242`
- [ ] Verify Stripe customer created
- [ ] Verify Stripe subscription created
- [ ] Verify database record updated with Stripe IDs
- [ ] Test candidate upload with limit enforcement
- [ ] Test webhook receives payment events
- [ ] Test usage counter increments
- [ ] Create live mode products in Stripe
- [ ] Update production `.env` with live keys and price IDs
- [ ] Deploy to EC2 with `docker-compose restart api`

---

## Common Issues

### Pricing Inconsistencies
**Problem**: Different prices shown in different files
**Solution**: Use this document as the single source of truth. Update all files to match.

### Tier Name Confusion
**Problem**: Code says "STARTER" but UI says "Recruiter"
**Solution**: This is intentional! Database uses `STARTER`, UI displays "Recruiter" via the `display_name` property.

### Free Tier Limit
**Problem**: FREE tier shows different limits (5, 10, 999999)
**Solution**: Production should be `10`. Testing can use `999999`. Check `.env` file.

### Stripe Price IDs Not Found
**Problem**: Subscription creation fails with "Price not found"
**Solution**: Create products in Stripe dashboard (test mode or live mode) and copy the price IDs to `.env`

---

## Migration from Old Pricing

If you had old pricing documented anywhere:

### Old Pricing (DEPRECATED)
- ~~STARTER: $50/mo~~
- ~~SMALL_BUSINESS: $100/mo for 250 candidates~~
- ~~PROFESSIONAL: $200/mo for 1,000 candidates~~
- ~~ENTERPRISE: $500/mo base + $0.50/candidate~~

### New Pricing (CURRENT)
- STARTER (Recruiter): $20/mo for 100 candidates
- SMALL_BUSINESS: $149/mo for 1,000 candidates
- PROFESSIONAL: $399/mo unlimited
- ENTERPRISE: $500/mo base + $0.25/candidate

All code and documentation has been updated to reflect the new pricing.

---

## Quick Reference for AI Assistants

When asked about pricing:
1. FREE: $0/mo, 10 candidates
2. Recruiter (code: STARTER): $20/mo, 100 candidates
3. Small Business: $149/mo, 1,000 candidates
4. Professional: $399/mo, unlimited
5. Enterprise: $500/mo + $0.25/candidate, unlimited

All annual plans: 20% discount (divide monthly by 1.25)

Files to check for pricing:
- `app/models/subscription.py` (authoritative source)
- `static/pricing.html` (user-facing)
- `.env` (Stripe price IDs)
