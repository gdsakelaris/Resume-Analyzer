# Delete Account UI Guide

## Where to Find It

The "Delete Account" button is located in the **top navigation bar** on the main dashboard (index.html), between "Manage Billing" and "Logout".

### Button Location
```
[Starscreen Logo] ... [Manage Billing] [Delete Account] [Logout]
                                         ^^^^^^^^^^^^^^^^
                                         Red colored button
```

## How It Works

### User Flow

1. **User clicks "Delete Account" button** (red colored for danger)

2. **First Confirmation Dialog:**
   ```
   ⚠️ WARNING: Delete Account?

   This will:
   • Cancel your Stripe subscription (you won't be charged again)
   • Delete ALL your data (jobs, candidates, evaluations)
   • This action is IRREVERSIBLE

   Are you absolutely sure you want to delete your account?

   [Cancel] [OK]
   ```

3. **Second Confirmation Dialog:**
   ```
   Final confirmation: Type YES in the next prompt to delete your account permanently.

   [Cancel] [OK]
   ```

4. **Third Confirmation - Text Input:**
   ```
   Type YES (in capital letters) to confirm account deletion:

   [Input field]
   [Cancel] [OK]
   ```
   - User must type exactly "YES" (capital letters)
   - Any other input cancels the deletion

5. **API Call:**
   - Sends `DELETE /api/v1/auth/me` request
   - Backend cancels Stripe subscription
   - Backend deletes user account and all data

6. **Success Message:**
   ```
   ✅ Account Deleted Successfully

   • Your Stripe subscription has been canceled
   • All your data has been deleted

   You will now be redirected to the login page.

   [OK]
   ```

7. **Automatic Redirect:**
   - User is logged out
   - Redirected to login page
   - All auth tokens cleared from browser

## Security Features

### Triple Confirmation
- **First dialog**: Explains consequences
- **Second dialog**: Confirms user intent
- **Third dialog**: Requires typing "YES" to prevent accidental clicks

### What Gets Protected
- Users cannot accidentally delete their account with a single click
- Clear warnings about Stripe subscription cancellation
- Clear warnings about data loss
- Must type "YES" exactly (case-sensitive)

## Visual Styling

### Button Design
```html
<button
    onclick="deleteAccount()"
    class="text-sm text-red-600 hover:text-red-900 font-medium px-3 py-2 rounded-lg hover:bg-red-50 transition"
>
    Delete Account
</button>
```

- **Color**: Red (text-red-600) to indicate danger
- **Hover**: Darker red (text-red-900) and light red background (bg-red-50)
- **Size**: Small text (text-sm), consistent with other nav buttons
- **Spacing**: Comfortable padding (px-3 py-2)

## Error Handling

### If Deletion Fails
```
❌ Failed to delete account:

[Error message from server]

[OK]
```

### If User Cancels
- At any confirmation step, user can click "Cancel"
- No API call is made
- User remains logged in
- Account is not deleted

### If User Types Wrong Confirmation
```
Account deletion canceled. You must type "YES" exactly to confirm.

[OK]
```

## Testing the Feature

### Test on Staging/Development

1. **Create a test account:**
   ```bash
   # Register at https://starscreen.net/static/register.html
   ```

2. **Login and go to dashboard:**
   ```bash
   # https://starscreen.net/static/index.html
   ```

3. **Click "Delete Account" button** (red button in top nav)

4. **Go through confirmation flow:**
   - Click OK on first warning
   - Click OK on second warning
   - Type "YES" in the prompt
   - Click OK

5. **Verify deletion:**
   - Check that success message appears
   - Check that you're redirected to login
   - Try to login with same credentials (should fail - user doesn't exist)
   - Check Stripe dashboard to verify subscription was canceled

### Verify Stripe Cancellation

1. Go to [Stripe Dashboard](https://dashboard.stripe.com/test/subscriptions)
2. Search for the test user's email
3. Verify subscription status is "Canceled"
4. Customer record should still exist (for audit purposes)

## Code Reference

### Frontend Code
- **Button**: [index.html:152-157](static/index.html#L152-L157)
- **JavaScript Function**: [index.html:1251-1314](static/index.html#L1251-L1314)

### Backend Code
- **API Endpoint**: [auth.py:217-269](app/api/endpoints/auth.py#L217-L269)
- **Stripe Cancellation**: [auth.py:243](app/api/endpoints/auth.py#L243)

## Browser Console Logs

When deletion is successful, you'll see these logs:

```
[DeleteAccount] Sending delete request...
[DeleteAccount] Account deleted successfully: { message: "Account deleted successfully", stripe_subscription_canceled: true }
[Auth] User logged out
```

## Troubleshooting

### Button Not Visible
- Make sure you're logged in
- Refresh the page (Ctrl+F5 / Cmd+Shift+R)
- Check browser console for JavaScript errors

### Delete Request Fails
- Check browser console for error details
- Verify you're still authenticated (token not expired)
- Check network tab to see the actual API response

### Stripe Not Canceled
- Check backend logs for Stripe API errors
- Verify STRIPE_API_KEY is set in .env
- User is still deleted from database even if Stripe fails
- Manually cancel in Stripe dashboard if needed

## Next Steps

### Future Enhancements

1. **Better UI Modal**
   - Replace browser `confirm()` and `prompt()` with custom modal
   - Better visual design matching site theme
   - Animated transitions

2. **Email Confirmation**
   - Send confirmation email before deletion
   - Require clicking link in email to confirm
   - Add cooldown period (e.g., 7 days) before permanent deletion

3. **Data Export**
   - Allow users to download their data before deletion
   - Export jobs, candidates, and evaluations as JSON/CSV
   - GDPR compliance feature

4. **Soft Delete**
   - Mark account as "deleted" instead of hard delete
   - Keep data for 30 days before permanent deletion
   - Allow account recovery within grace period

5. **Admin Override**
   - Admin can delete any user account
   - Admin dashboard with user management
   - Audit log of all account deletions
