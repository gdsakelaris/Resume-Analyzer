# User Deletion Guide

This guide explains how to safely delete user accounts while properly canceling their Stripe subscriptions to prevent unwanted charges.

## Important Background

**Why this matters:**
- When a user account is deleted from the database, the database record is removed
- However, this does NOT automatically cancel the Stripe subscription
- The Stripe subscription will continue to exist and charge the customer monthly
- **This would result in users being charged for a service they can no longer access**

## Solution

We've implemented proper Stripe subscription cancellation that happens automatically when a user is deleted.

---

## Option 1: Delete Individual User via API (Recommended)

Users can delete their own account using the DELETE endpoint:

### Endpoint
```
DELETE /api/v1/auth/me
Authorization: Bearer {access_token}
```

### What it does:
1. ✅ Cancels the user's Stripe subscription (they won't be charged anymore)
2. ✅ Deletes the user account from the database
3. ✅ Cascades to delete all related data (jobs, candidates, evaluations, subscription records)

### Example using curl:
```bash
curl -X DELETE https://starscreen.net/api/v1/auth/me \
  -H "Authorization: Bearer YOUR_ACCESS_TOKEN"
```

### Example using JavaScript:
```javascript
const response = await fetch('https://starscreen.net/api/v1/auth/me', {
  method: 'DELETE',
  headers: {
    'Authorization': `Bearer ${accessToken}`
  }
});

const result = await response.json();
console.log(result);
// { message: "Account deleted successfully", stripe_subscription_canceled: true }
```

---

## Option 2: Delete All Users via Script

For development/testing purposes, you can delete all users at once.

### Script: `delete_all_users.py`

Located at the project root, this script:
1. ✅ Cancels ALL Stripe subscriptions first
2. ✅ Deletes ALL user accounts and their data
3. ✅ Provides detailed logging of each operation
4. ✅ Requires explicit confirmation before proceeding

### How to run:

**From your local machine:**
```bash
python delete_all_users.py
```

**From the Docker container:**
```bash
docker-compose exec backend python delete_all_users.py
```

**On the EC2 server:**
```bash
ssh ubuntu@your-server
cd ~/Resume-Analyzer
docker-compose exec backend python delete_all_users.py
```

### Example output:
```
============================================================
Found 5 users to delete
============================================================

Are you sure you want to delete ALL 5 users? (yes/no): yes

Processing user: john@example.com (ID: 123e4567-e89b-12d3-a456-426614174000)
  → Canceling Stripe subscription: sub_1234567890
  ✓ Stripe subscription canceled
  ✓ User deleted from database

Processing user: jane@example.com (ID: 223e4567-e89b-12d3-a456-426614174001)
  → No Stripe subscription to cancel
  ✓ User deleted from database

...

============================================================
DELETION SUMMARY
============================================================
Users deleted: 5
Stripe subscriptions canceled: 3

✓ All operations completed successfully!
============================================================
```

---

## What Gets Deleted

When a user is deleted (either via API or script), the following data is removed:

### Database (Cascade Delete)
- ✅ User account
- ✅ Subscription record
- ✅ Email verification codes
- ✅ Jobs created by the user
- ✅ Candidates uploaded by the user
- ✅ Evaluations for those candidates

### Stripe (Manual Cancellation)
- ✅ Active subscription is canceled immediately
- ✅ User won't be charged again
- ❌ Stripe customer record remains (for historical billing records)
- ❌ Past invoices remain (for accounting purposes)

---

## Important Notes

### For Individual Deletions (API):
- Users must be authenticated to delete their own account
- The deletion is irreversible - all data is permanently lost
- If Stripe cancellation fails, the user is still deleted but may need manual Stripe cleanup

### For Bulk Deletions (Script):
- Requires "yes" confirmation (case-sensitive)
- Each user is processed individually with detailed logging
- If Stripe cancellation fails for some users, they are still deleted from the database
- Failed Stripe cancellations are logged - you can manually cancel in Stripe dashboard

### Stripe Behavior:
- **Test mode**: Subscriptions are immediately canceled
- **Live mode**: Subscriptions are immediately canceled (not at period end)
- Customer records remain in Stripe for audit/accounting purposes
- Historical invoices and payment records are preserved

---

## Testing

To verify proper cancellation:

1. **Delete a test user:**
   ```bash
   # Login to get access token
   curl -X POST https://starscreen.net/api/v1/auth/login \
     -H "Content-Type: application/json" \
     -d '{"username": "test@example.com", "password": "password123"}'

   # Delete account
   curl -X DELETE https://starscreen.net/api/v1/auth/me \
     -H "Authorization: Bearer YOUR_ACCESS_TOKEN"
   ```

2. **Check Stripe dashboard:**
   - Go to https://dashboard.stripe.com/test/subscriptions
   - Verify the subscription status is "Canceled"
   - Customer record should still exist but with no active subscription

3. **Check database:**
   ```bash
   docker-compose exec db psql -U starscreen_user -d starscreen_prod

   SELECT email FROM users WHERE email = 'test@example.com';
   -- Should return 0 rows
   ```

---

## Troubleshooting

### Stripe API Key Not Set
**Error:** `Stripe API key is not set!`

**Solution:** Check your .env file has `STRIPE_API_KEY` set:
```bash
grep STRIPE_API_KEY .env
```

### Subscription Cancellation Fails
**Error:** `Failed to cancel Stripe subscription: {error}`

**What happens:**
- The user is still deleted from the database
- The error is logged
- You'll need to manually cancel in Stripe dashboard

**Manual cancellation in Stripe:**
1. Go to https://dashboard.stripe.com/subscriptions
2. Search for the customer email
3. Click the subscription → Cancel subscription

### Database Connection Error
**Error:** `could not connect to server`

**Solution:** Ensure the database container is running:
```bash
docker-compose ps
docker-compose up -d db
```

---

## FAQ

**Q: What if I just want to reset my test environment?**
A: Run `delete_all_users.py` to remove all users and their Stripe subscriptions at once.

**Q: Can I recover a deleted user?**
A: No, deletion is permanent. Make sure to backup data if needed.

**Q: Will deleting a user also delete their S3 resume files?**
A: No, S3 files are not automatically deleted. You may want to implement S3 cleanup separately.

**Q: What happens to unpaid invoices when I cancel?**
A: Unpaid invoices remain in Stripe. Stripe will attempt to collect them according to your retry settings.

**Q: Can users delete their own accounts from the frontend?**
A: Not yet - you'll need to add a "Delete Account" button that calls `DELETE /api/v1/auth/me`.

---

## Next Steps

To add account deletion to your frontend:

1. Add a "Delete Account" button in user settings
2. Show a confirmation modal with warning
3. Call `DELETE /api/v1/auth/me` with user's access token
4. Logout and redirect to homepage on success
5. Show error message if deletion fails
