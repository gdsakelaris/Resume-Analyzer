# LinkedIn Integration - Frontend Implementation Guide

## ✅ What's Already Done

### Backend (100% Complete)
- ✅ OAuth connection storage (encrypted tokens)
- ✅ External job posting tracking
- ✅ LinkedIn API integration
- ✅ Celery background tasks
- ✅ API endpoints (`/linkedin/auth/*`, `/linkedin/status`, `/linkedin/disconnect`)
- ✅ Database migration completed
- ✅ LinkedIn credentials configured on EC2

### Frontend (33% Complete)
- ✅ Settings page created (`/static/settings.html`)
- ✅ Navigation link added to dashboard dropdown
- ✅ LinkedIn connection status check
- ✅ OAuth flow initiation
- ✅ Disconnect functionality

---

## 🔧 Remaining Frontend Work

### 1. **Job Creation Form** - Add "Post to LinkedIn" Checkbox

**File to modify:** Find your job creation page (likely in `static/` or dashboard)

**What to add:**
```html
<!-- Add this checkbox to your job creation form -->
<div class="flex items-start gap-3 p-4 bg-blue-50 border border-blue-200 rounded-lg"
     x-data="{ linkedInConnected: false }"
     x-init="checkLinkedInConnection()">

    <input type="checkbox"
           id="post_to_linkedin"
           name="post_to_linkedin"
           x-model="postToLinkedIn"
           :disabled="!linkedInConnected"
           class="mt-1 w-4 h-4 text-brand-600 border-slate-300 rounded focus:ring-brand-500 disabled:opacity-50 disabled:cursor-not-allowed">

    <label for="post_to_linkedin" class="flex-1">
        <span class="font-medium text-slate-900 flex items-center gap-2">
            <svg class="w-5 h-5 text-blue-600" fill="currentColor" viewBox="0 0 24 24">
                <path d="M20.447 20.452h-3.554v-5.569c0-1.328-.027-3.037-1.852-3.037-1.853 0-2.136 1.445-2.136 2.939v5.667H9.351V9h3.414v1.561h.046c.477-.9 1.637-1.85 3.37-1.85 3.601 0 4.267 2.37 4.267 5.455v6.286zM5.337 7.433c-1.144 0-2.063-.926-2.063-2.065 0-1.138.92-2.063 2.063-2.063 1.14 0 2.064.925 2.064 2.063 0 1.139-.925 2.065-2.064 2.065zm1.782 13.019H3.555V9h3.564v11.452zM22.225 0H1.771C.792 0 0 .774 0 1.729v20.542C0 23.227.792 24 1.771 24h20.451C23.2 24 24 23.227 24 22.271V1.729C24 .774 23.2 0 22.222 0h.003z"/>
            </svg>
            Post to LinkedIn automatically
        </span>

        <p class="text-sm text-slate-600 mt-1" x-show="linkedInConnected">
            Your job will be posted to LinkedIn after AI configuration completes
        </p>

        <p class="text-sm text-orange-600 mt-1" x-show="!linkedInConnected">
            <a href="/static/settings.html" class="underline hover:text-orange-700">
                Connect LinkedIn in Settings
            </a> to enable automatic posting
        </p>
    </label>
</div>

<script>
function checkLinkedInConnection() {
    fetch('/api/v1/linkedin/status', {
        headers: {
            'Authorization': `Bearer ${localStorage.getItem('starscreen_access_token')}`
        }
    })
    .then(res => res.json())
    .then(data => {
        this.linkedInConnected = data.connected;
    })
    .catch(err => console.error('LinkedIn status check failed:', err));
}
</script>
```

**Then update your job submission logic:**
```javascript
// When creating a job, include the checkbox value
const jobData = {
    title: formData.title,
    description: formData.description,
    location: formData.location,
    work_authorization_required: formData.work_authorization_required,
    post_to_linkedin: document.getElementById('post_to_linkedin').checked  // Add this
};

fetch('/api/v1/jobs/', {
    method: 'POST',
    headers: {
        'Content-Type': 'application/json',
        'Authorization': `Bearer ${token}`
    },
    body: JSON.stringify(jobData)
})
```

---

### 2. **Job Details Page** - Show LinkedIn Posting Status

**File to modify:** Your job details/view page

**What to add:**
```html
<!-- Add this section to show external posting status -->
<div x-show="job.external_postings && job.external_postings.length > 0"
     class="mt-6">

    <h3 class="text-lg font-semibold text-slate-900 mb-3">External Postings</h3>

    <template x-for="posting in job.external_postings" :key="posting.id">
        <div class="bg-white border border-slate-200 rounded-lg p-4 mb-3">

            <!-- LinkedIn Header -->
            <div class="flex items-center justify-between mb-2">
                <div class="flex items-center gap-2">
                    <svg class="w-6 h-6 text-blue-600" fill="currentColor" viewBox="0 0 24 24">
                        <path d="M20.447 20.452h-3.554v-5.569c0-1.328-.027-3.037-1.852-3.037-1.853 0-2.136 1.445-2.136 2.939v5.667H9.351V9h3.414v1.561h.046c.477-.9 1.637-1.85 3.37-1.85 3.601 0 4.267 2.37 4.267 5.455v6.286zM5.337 7.433c-1.144 0-2.063-.926-2.063-2.065 0-1.138.92-2.063 2.063-2.063 1.14 0 2.064.925 2.064 2.063 0 1.139-.925 2.065-2.064 2.065zm1.782 13.019H3.555V9h3.564v11.452zM22.225 0H1.771C.792 0 0 .774 0 1.729v20.542C0 23.227.792 24 1.771 24h20.451C23.2 24 24 23.227 24 22.271V1.729C24 .774 23.2 0 22.222 0h.003z"/>
                    </svg>
                    <span class="font-medium text-slate-900" x-text="posting.provider.toUpperCase()"></span>
                </div>

                <!-- Status Badge -->
                <span class="px-2 py-1 rounded-full text-xs font-medium"
                      :class="{
                          'bg-green-100 text-green-800': posting.status === 'active',
                          'bg-yellow-100 text-yellow-800': posting.status === 'posting' || posting.status === 'pending',
                          'bg-red-100 text-red-800': posting.status === 'failed',
                          'bg-slate-100 text-slate-800': posting.status === 'closed' || posting.status === 'expired'
                      }"
                      x-text="posting.status.toUpperCase()">
                </span>
            </div>

            <!-- Active State - Show Link -->
            <div x-show="posting.status === 'active' && posting.external_url">
                <a :href="posting.external_url"
                   target="_blank"
                   class="inline-flex items-center gap-1 text-sm text-blue-600 hover:text-blue-700 font-medium">
                    View on LinkedIn
                    <svg class="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                        <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M10 6H6a2 2 0 00-2 2v10a2 2 0 002 2h10a2 2 0 002-2v-4M14 4h6m0 0v6m0-6L10 14"></path>
                    </svg>
                </a>
                <p class="text-xs text-slate-500 mt-1" x-show="posting.posted_at">
                    Posted <span x-text="new Date(posting.posted_at).toLocaleString()"></span>
                </p>
            </div>

            <!-- Pending/Posting State -->
            <div x-show="posting.status === 'pending' || posting.status === 'posting'"
                 class="flex items-center gap-2 text-sm text-yellow-700">
                <svg class="animate-spin h-4 w-4" fill="none" viewBox="0 0 24 24">
                    <circle class="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" stroke-width="4"></circle>
                    <path class="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4zm2 5.291A7.962 7.962 0 014 12H0c0 3.042 1.135 5.824 3 7.938l3-2.647z"></path>
                </svg>
                <span x-text="posting.status === 'pending' ? 'Waiting to post...' : 'Posting to LinkedIn...'"></span>
            </div>

            <!-- Failed State -->
            <div x-show="posting.status === 'failed'" class="space-y-2">
                <p class="text-sm text-red-700 font-medium">❌ Posting failed</p>
                <p class="text-xs text-red-600" x-show="posting.error_message" x-text="posting.error_message"></p>
                <button @click="retryLinkedInPosting(job.id)"
                        class="text-xs text-red-700 hover:text-red-800 font-medium underline">
                    Retry Posting
                </button>
            </div>

        </div>
    </template>
</div>

<script>
async function retryLinkedInPosting(jobId) {
    if (!confirm('Retry posting this job to LinkedIn?')) return;

    try {
        const response = await fetch(`/api/v1/jobs/${jobId}/retry-linkedin`, {
            method: 'POST',
            headers: {
                'Authorization': `Bearer ${localStorage.getItem('starscreen_access_token')}`
            }
        });

        if (response.ok) {
            alert('Job queued for LinkedIn posting!');
            location.reload(); // Reload to see updated status
        } else {
            const error = await response.json();
            alert(`Failed to retry: ${error.detail}`);
        }
    } catch (err) {
        alert('Network error. Please try again.');
    }
}
</script>
```

---

### 3. **Job List/Dashboard** - Show LinkedIn Badge (Optional Enhancement)

**Add a small LinkedIn badge to jobs that are posted:**

```html
<!-- In your job list item template -->
<template x-for="job in jobs">
    <div class="job-card">
        <h3 x-text="job.title"></h3>

        <!-- LinkedIn Badge -->
        <template x-if="job.external_postings && job.external_postings.some(p => p.status === 'active')">
            <span class="inline-flex items-center gap-1 bg-blue-50 text-blue-700 text-xs px-2 py-0.5 rounded-full">
                <svg class="w-3 h-3" fill="currentColor" viewBox="0 0 24 24">
                    <path d="M20.447 20.452h-3.554v-5.569c0-1.328-.027-3.037-1.852-3.037-1.853 0-2.136 1.445-2.136 2.939v5.667H9.351V9h3.414v1.561h.046c.477-.9 1.637-1.85 3.37-1.85 3.601 0 4.267 2.37 4.267 5.455v6.286zM5.337 7.433c-1.144 0-2.063-.926-2.063-2.065 0-1.138.92-2.063 2.063-2.063 1.14 0 2.064.925 2.064 2.063 0 1.139-.925 2.065-2.064 2.065zm1.782 13.019H3.555V9h3.564v11.452zM22.225 0H1.771C.792 0 0 .774 0 1.729v20.542C0 23.227.792 24 1.771 24h20.451C23.2 24 24 23.227 24 22.271V1.729C24 .774 23.2 0 22.222 0h.003z"/>
                </svg>
                Posted on LinkedIn
            </span>
        </template>
    </div>
</template>
```

---

## 🧪 Testing Checklist

### Settings Page
- [ ] Navigate to Settings from dashboard dropdown
- [ ] See "Not Connected" status for new users
- [ ] Click "Connect LinkedIn" (should redirect to LinkedIn OAuth)
- [ ] After OAuth, redirect back and see "Connected" status
- [ ] Click "Disconnect" and confirm it works
- [ ] FREE tier users see upgrade message

### Job Creation
- [ ] "Post to LinkedIn" checkbox appears
- [ ] Checkbox is disabled if LinkedIn not connected
- [ ] Link to Settings works when not connected
- [ ] Creating job with checkbox checked includes `post_to_linkedin: true` in API call
- [ ] FREE tier users get 403 error if they try to post to LinkedIn

### Job Details
- [ ] Jobs show external_postings section
- [ ] PENDING status shows spinner
- [ ] ACTIVE status shows LinkedIn link
- [ ] FAILED status shows error message and retry button
- [ ] LinkedIn URL opens in new tab

---

## 📝 Summary

**Total Integration Progress: 60% Complete**

✅ **Done:**
- Backend API (100%)
- Database & migrations (100%)
- Settings page (100%)
- Navigation link (100%)

🔧 **Remaining:**
- Job creation form checkbox (30 min)
- Job details page status display (30 min)
- Job list badges (15 min, optional)

**Estimated time to complete:** ~1 hour

---

## 🚀 Quick Start

1. **Deploy frontend changes:**
   ```bash
   git add .
   git commit -m "Add LinkedIn job creation and status display"
   git push origin main
   ```

2. **Test the flow:**
   - Login as paid user
   - Go to Settings → Connect LinkedIn
   - Create a job with "Post to LinkedIn" checked
   - Watch status change from PENDING → POSTING → ACTIVE
   - Click the LinkedIn link to view your job

3. **Handle errors:**
   - If posting fails, error message shows on job details page
   - User can click "Retry Posting" button
   - Or manually re-post by editing the job

---

## 🔗 API Endpoints Reference

| Endpoint | Method | Purpose |
|----------|--------|---------|
| `/api/v1/linkedin/status` | GET | Check connection status |
| `/api/v1/linkedin/auth/initiate` | GET | Start OAuth flow |
| `/api/v1/linkedin/auth/callback` | GET | OAuth callback |
| `/api/v1/linkedin/disconnect` | DELETE | Disconnect LinkedIn |
| `/api/v1/jobs/` | POST | Create job (with `post_to_linkedin` flag) |
| `/api/v1/jobs/{id}` | GET | Get job (includes `external_postings`) |

---

## 💡 Tips

- **Error Handling:** The API is designed for graceful degradation - job creation always succeeds even if LinkedIn posting fails
- **Retry Logic:** Failed postings can be retried manually by the user
- **Status Updates:** Poll the job endpoint to see real-time posting status updates
- **Free Tier:** Make sure to show upgrade prompts for FREE tier users trying to use LinkedIn features

