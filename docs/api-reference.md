# Starscreen API Reference

> **LLM Context**: This document provides complete API endpoint documentation for the Starscreen resume screening platform. Use this for understanding API contracts, request/response formats, authentication requirements, and error handling patterns.

**Base URL**: `http://localhost:8000` (development)

**API Version**: v1

**Authentication**: JWT Bearer tokens (access_token from login/register)

**Content Type**: `application/json` (except file uploads: `multipart/form-data`)

---

## Table of Contents

1. [Authentication Endpoints](#authentication-endpoints)
2. [Job Management Endpoints](#job-management-endpoints)
3. [Candidate Management Endpoints](#candidate-management-endpoints)
4. [Stripe Webhook Endpoints](#stripe-webhook-endpoints)
5. [Common Response Formats](#common-response-formats)
6. [Error Handling](#error-handling)
7. [Rate Limiting & Billing Constraints](#rate-limiting--billing-constraints)

---

## Authentication Endpoints

Base path: `/api/v1/auth`

### POST /api/v1/auth/register

Create a new user account with FREE tier subscription.

**Authentication**: None (public endpoint)

**Request Body**:
```json
{
  "email": "user@example.com",
  "password": "SecurePass123!",
  "full_name": "John Doe",          // Optional
  "company_name": "Acme Corp"       // Optional
}
```

**Password Requirements** (validated by Pydantic):
- Length: 8-72 characters (bcrypt limitation)
- Must contain: lowercase letter, uppercase letter, number, special character
- Special characters allowed: `!@#$%^&*(),.?":{}|<>`

**Response** (201 Created):
```json
{
  "access_token": "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9...",
  "refresh_token": "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9...",
  "token_type": "bearer"
}
```

**Side Effects**:
1. Creates User record with unique `tenant_id`
2. Creates Subscription record:
   - `plan`: FREE
   - `status`: TRIALING
   - `monthly_candidate_limit`: 5
   - `candidates_used_this_month`: 0

**Errors**:
- `400 Bad Request`: Invalid email format or password doesn't meet requirements
- `400 Bad Request`: Email already registered

**Example**:
```bash
curl -X POST http://localhost:8000/api/v1/auth/register \
  -H "Content-Type: application/json" \
  -d '{
    "email": "test@example.com",
    "password": "Test123!@#",
    "full_name": "Test User",
    "company_name": "Test Co"
  }'
```

---

### POST /api/v1/auth/login

Authenticate user and receive JWT tokens.

**Authentication**: None (public endpoint)

**Request Body** (OAuth2 password flow):
```json
{
  "username": "user@example.com",    // OAuth2 spec uses "username" for email
  "password": "SecurePass123!"
}
```

**Response** (200 OK):
```json
{
  "access_token": "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9...",
  "refresh_token": "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9...",
  "token_type": "bearer"
}
```

**Token Details**:
- **Access Token**: 30-minute expiration, contains `sub` (user_id) and `tenant_id`
- **Refresh Token**: 7-day expiration, contains `type: "refresh"` claim

**Side Effects**:
- Updates `last_login_at` timestamp on User record

**Errors**:
- `401 Unauthorized`: Invalid email or password
- `401 Unauthorized`: User account is inactive (`is_active = False`)

**Example**:
```bash
curl -X POST http://localhost:8000/api/v1/auth/login \
  -H "Content-Type: application/json" \
  -d '{
    "username": "test@example.com",
    "password": "Test123!@#"
  }'
```

---

### POST /api/v1/auth/refresh

Exchange refresh token for new access token and refresh token pair.

**Authentication**: Refresh token in request body

**Request Body**:
```json
{
  "refresh_token": "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9..."
}
```

**Response** (200 OK):
```json
{
  "access_token": "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9...",   // NEW token
  "refresh_token": "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9...",  // NEW token
  "token_type": "bearer"
}
```

**Behavior**:
- Validates refresh token signature and expiration
- Issues BOTH new access token AND new refresh token
- Old tokens are NOT invalidated (stateless JWT system)

**Errors**:
- `401 Unauthorized`: Invalid or expired refresh token
- `401 Unauthorized`: Token missing `type: "refresh"` claim

**Example**:
```bash
curl -X POST http://localhost:8000/api/v1/auth/refresh \
  -H "Content-Type: application/json" \
  -d '{
    "refresh_token": "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9..."
  }'
```

---

### GET /api/v1/auth/me

Get current authenticated user's profile.

**Authentication**: Required (`Authorization: Bearer <access_token>`)

**Request**: No body

**Response** (200 OK):
```json
{
  "id": "123e4567-e89b-12d3-a456-426614174000",
  "tenant_id": "987fcdeb-51a2-43d7-8c9f-123456789abc",
  "email": "user@example.com",
  "full_name": "John Doe",
  "company_name": "Acme Corp",
  "is_active": true,
  "is_verified": false,
  "created_at": "2025-12-31T10:30:00Z",
  "updated_at": "2025-12-31T10:30:00Z",
  "last_login_at": "2025-12-31T11:00:00Z"
}
```

**Errors**:
- `401 Unauthorized`: Missing or invalid access token
- `401 Unauthorized`: Token expired

**Example**:
```bash
curl -X GET http://localhost:8000/api/v1/auth/me \
  -H "Authorization: Bearer eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9..."
```

---

## Job Management Endpoints

Base path: `/api/v1/jobs`

All endpoints require authentication and enforce tenant isolation via `tenant_id`.

---

### POST /api/v1/jobs/

Create a new job posting and generate AI-powered scoring rubric.

**Authentication**: Required + Active Subscription (ACTIVE or TRIALING status)

**Request Body**:
```json
{
  "title": "Senior Python Developer",
  "description": "5+ years Python experience. FastAPI, PostgreSQL, AWS. Remote work available.",
  "location": "San Francisco, CA",        // Optional
  "work_authorization_required": false    // Optional, default: false
}
```

**Field Constraints**:
- `title`: 1-200 characters
- `description`: 1-15,000 characters (enforced for OpenAI API cost control)
- `location`: Optional, 1-200 characters
- `work_authorization_required`: Boolean

**Response** (201 Created):
```json
{
  "id": 1,
  "tenant_id": "987fcdeb-51a2-43d7-8c9f-123456789abc",
  "title": "Senior Python Developer",
  "description": "5+ years Python experience...",
  "location": "San Francisco, CA",
  "work_authorization_required": false,
  "status": "PENDING",
  "job_config": null,                     // Generated asynchronously by Celery
  "error_message": null,
  "created_at": "2025-12-31T11:00:00Z",
  "updated_at": "2025-12-31T11:00:00Z"
}
```

**Async Processing**:
1. Job record created with `status: PENDING`
2. Celery task `generate_job_config_task(job_id)` starts
3. GPT-4o analyzes job description and generates rubric:
   ```json
   {
     "categories": [
       {
         "name": "Python",
         "importance": 5,
         "keywords": ["python", "django", "flask", "fastapi"]
       },
       {
         "name": "Databases",
         "importance": 4,
         "keywords": ["postgresql", "sql", "database"]
       }
     ]
   }
   ```
4. Job updated: `status: COMPLETED`, `job_config: {...}`

**Status Flow**: `PENDING` → `PROCESSING` → `COMPLETED` (or `FAILED`)

**Subscription Enforcement**:
- Requires `subscription.is_active == True` (ACTIVE or TRIALING)
- Blocked if subscription status is PAST_DUE, CANCELED, or UNPAID

**Errors**:
- `400 Bad Request`: Validation errors (description too long, etc.)
- `402 Payment Required`: Subscription is not active
- `401 Unauthorized`: Invalid token

**Example**:
```bash
curl -X POST http://localhost:8000/api/v1/jobs/ \
  -H "Authorization: Bearer YOUR_ACCESS_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "title": "Senior Python Developer",
    "description": "5+ years Python, FastAPI, PostgreSQL",
    "location": "Remote"
  }'
```

---

### GET /api/v1/jobs/

List all jobs for the authenticated user's tenant.

**Authentication**: Required

**Query Parameters**:
- `skip`: Offset for pagination (default: 0)
- `limit`: Number of results (default: 100, max: 100)

**Response** (200 OK):
```json
[
  {
    "id": 1,
    "tenant_id": "987fcdeb-51a2-43d7-8c9f-123456789abc",
    "title": "Senior Python Developer",
    "description": "5+ years Python experience...",
    "location": "San Francisco, CA",
    "work_authorization_required": false,
    "status": "COMPLETED",
    "job_config": {
      "categories": [...]
    },
    "error_message": null,
    "created_at": "2025-12-31T11:00:00Z",
    "updated_at": "2025-12-31T11:05:00Z"
  }
]
```

**Tenant Isolation**:
- Automatically filters by `tenant_id` from JWT token
- Users can ONLY see their own jobs

**Example**:
```bash
curl -X GET "http://localhost:8000/api/v1/jobs/?skip=0&limit=10" \
  -H "Authorization: Bearer YOUR_ACCESS_TOKEN"
```

---

### GET /api/v1/jobs/{job_id}

Get details for a specific job.

**Authentication**: Required

**Path Parameters**:
- `job_id`: Integer job ID

**Response** (200 OK):
```json
{
  "id": 1,
  "tenant_id": "987fcdeb-51a2-43d7-8c9f-123456789abc",
  "title": "Senior Python Developer",
  "description": "5+ years Python experience...",
  "location": "San Francisco, CA",
  "work_authorization_required": false,
  "status": "COMPLETED",
  "job_config": {
    "categories": [
      {
        "name": "Python",
        "importance": 5,
        "keywords": ["python", "fastapi", "django"]
      }
    ]
  },
  "error_message": null,
  "created_at": "2025-12-31T11:00:00Z",
  "updated_at": "2025-12-31T11:05:00Z"
}
```

**Errors**:
- `404 Not Found`: Job doesn't exist OR belongs to different tenant

**Example**:
```bash
curl -X GET http://localhost:8000/api/v1/jobs/1 \
  -H "Authorization: Bearer YOUR_ACCESS_TOKEN"
```

---

### DELETE /api/v1/jobs/{job_id}

Delete a job and all associated candidates/evaluations (CASCADE).

**Authentication**: Required

**Path Parameters**:
- `job_id`: Integer job ID

**Response** (204 No Content): Empty body

**Side Effects**:
- Deletes Job record
- CASCADE deletes all Candidate records for this job
- CASCADE deletes all Evaluation records for those candidates
- Deletes resume files from `uploads/` directory

**Errors**:
- `404 Not Found`: Job doesn't exist OR belongs to different tenant

**Example**:
```bash
curl -X DELETE http://localhost:8000/api/v1/jobs/1 \
  -H "Authorization: Bearer YOUR_ACCESS_TOKEN"
```

---

## Candidate Management Endpoints

Base path: `/api/v1/jobs/{job_id}/candidates` or `/api/v1/candidates`

---

### POST /api/v1/jobs/{job_id}/candidates

Upload a resume for a specific job.

**Authentication**: Required + Active Subscription + Under Monthly Limit

**Path Parameters**:
- `job_id`: Integer job ID

**Request Body** (multipart/form-data):
- `file`: Resume file (PDF or DOCX, max 10MB)

**Supported Formats**:
- PDF: Up to 6 pages extracted, max 25,000 characters
- DOCX: Max 25,000 characters
- DOC: Rejected (must convert to DOCX or PDF)

**Response** (201 Created):
```json
{
  "id": 1,
  "tenant_id": "987fcdeb-51a2-43d7-8c9f-123456789abc",
  "job_id": 1,
  "first_name": null,                     // Populated by AI after scoring
  "last_name": null,
  "email": null,
  "phone": null,
  "location": null,
  "linkedin_url": null,
  "github_url": null,
  "portfolio_url": null,
  "other_urls": [],
  "file_path": "uploads/resume.pdf",
  "original_filename": "resume.pdf",
  "resume_text": "John Doe\nSenior Python Developer...",
  "anonymized_text": null,
  "status": "UPLOADED",
  "error_message": null,
  "created_at": "2025-12-31T11:10:00Z",
  "updated_at": "2025-12-31T11:10:00Z",
  "remaining_candidates": 4              // How many uploads left this month
}
```

**Async Processing Flow**:
1. File uploaded → `status: UPLOADED`
2. Celery task `parse_resume_task(candidate_id)` extracts text → `status: PARSED`
3. Auto-chains to `score_candidate_task(candidate_id)`:
   - AI grades candidate against job rubric
   - AI extracts contact info (name, email, phone, location, URLs)
   - Python calculates weighted score
   - Updates candidate contact fields
   - Creates Evaluation record
   - `status: SCORED`

**Status Flow**: `UPLOADED` → `PROCESSING` → `PARSED` → `SCORED` (or `FAILED`)

**Subscription Enforcement**:
1. Checks `subscription.can_upload_candidate` (active + under limit)
2. Increments `subscription.candidates_used_this_month += 1`
3. Returns `remaining_candidates` in response

**Errors**:
- `400 Bad Request`: Invalid file format (not PDF/DOCX)
- `400 Bad Request`: File too large (>10MB)
- `402 Payment Required`: Monthly candidate limit reached
- `402 Payment Required`: Subscription inactive
- `404 Not Found`: Job doesn't exist or belongs to different tenant

**Example**:
```bash
curl -X POST http://localhost:8000/api/v1/jobs/1/candidates \
  -H "Authorization: Bearer YOUR_ACCESS_TOKEN" \
  -F "file=@/path/to/resume.pdf"
```

---

### POST /api/v1/jobs/{job_id}/candidates/bulk-upload-zip

Upload multiple resumes in a ZIP file.

**Authentication**: Required + Active Subscription

**Path Parameters**:
- `job_id`: Integer job ID

**Request Body** (multipart/form-data):
- `file`: ZIP file containing PDF/DOCX resumes

**Response** (200 OK):
```json
{
  "processed_count": 8,
  "limit_reached": true,
  "remaining_candidates": 0,
  "results": [
    {
      "filename": "candidate1.pdf",
      "status": "success",
      "candidate_id": 1
    },
    {
      "filename": "candidate2.pdf",
      "status": "success",
      "candidate_id": 2
    },
    {
      "filename": "candidate9.pdf",
      "status": "limit_reached",
      "candidate_id": null
    }
  ]
}
```

**Behavior**:
- Processes files sequentially
- Checks limit BEFORE each file upload
- Stops gracefully when limit reached
- Partially successful (processes files until limit)

**Errors**:
- `400 Bad Request`: File is not a ZIP
- `402 Payment Required`: Subscription inactive (checked at start)
- `404 Not Found`: Job doesn't exist

**Example**:
```bash
curl -X POST http://localhost:8000/api/v1/jobs/1/candidates/bulk-upload-zip \
  -H "Authorization: Bearer YOUR_ACCESS_TOKEN" \
  -F "file=@/path/to/resumes.zip"
```

---

### GET /api/v1/jobs/{job_id}/candidates

List all candidates for a specific job.

**Authentication**: Required

**Path Parameters**:
- `job_id`: Integer job ID

**Query Parameters**:
- `skip`: Offset (default: 0)
- `limit`: Results per page (default: 100)

**Response** (200 OK):
```json
[
  {
    "id": 1,
    "tenant_id": "987fcdeb-51a2-43d7-8c9f-123456789abc",
    "job_id": 1,
    "first_name": "John",
    "last_name": "Doe",
    "email": "john@example.com",
    "phone": "+1-555-0100",
    "location": "San Francisco, CA",
    "linkedin_url": "https://linkedin.com/in/johndoe",
    "github_url": "https://github.com/johndoe",
    "portfolio_url": "https://johndoe.com",
    "other_urls": ["https://twitter.com/johndoe"],
    "file_path": "uploads/resume.pdf",
    "original_filename": "resume.pdf",
    "resume_text": "John Doe\nSenior Python Developer...",
    "anonymized_text": null,
    "status": "SCORED",
    "error_message": null,
    "created_at": "2025-12-31T11:10:00Z",
    "updated_at": "2025-12-31T11:15:00Z"
  }
]
```

**Tenant Isolation**: Automatically filters by tenant_id

**Example**:
```bash
curl -X GET "http://localhost:8000/api/v1/jobs/1/candidates?skip=0&limit=50" \
  -H "Authorization: Bearer YOUR_ACCESS_TOKEN"
```

---

### GET /api/v1/candidates/{candidate_id}

Get details for a specific candidate.

**Authentication**: Required

**Path Parameters**:
- `candidate_id`: Integer candidate ID

**Response** (200 OK):
```json
{
  "id": 1,
  "tenant_id": "987fcdeb-51a2-43d7-8c9f-123456789abc",
  "job_id": 1,
  "first_name": "John",
  "last_name": "Doe",
  "email": "john@example.com",
  "phone": "+1-555-0100",
  "location": "San Francisco, CA",
  "linkedin_url": "https://linkedin.com/in/johndoe",
  "github_url": "https://github.com/johndoe",
  "portfolio_url": "https://johndoe.com",
  "other_urls": ["https://twitter.com/johndoe"],
  "file_path": "uploads/resume.pdf",
  "original_filename": "resume.pdf",
  "resume_text": "John Doe\nSenior Python Developer...",
  "anonymized_text": null,
  "status": "SCORED",
  "error_message": null,
  "created_at": "2025-12-31T11:10:00Z",
  "updated_at": "2025-12-31T11:15:00Z"
}
```

**Errors**:
- `404 Not Found`: Candidate doesn't exist OR belongs to different tenant

---

### GET /api/v1/candidates/{candidate_id}/analysis

Get AI-generated evaluation for a candidate.

**Authentication**: Required

**Path Parameters**:
- `candidate_id`: Integer candidate ID

**Response** (200 OK):
```json
{
  "id": 1,
  "tenant_id": "987fcdeb-51a2-43d7-8c9f-123456789abc",
  "candidate_id": 1,
  "match_score": 82.5,                    // Python-calculated weighted average
  "category_scores": {
    "Python": {
      "score": 85,
      "reasoning": "Strong Python experience with FastAPI and Django. 6+ years in production environments."
    },
    "Databases": {
      "score": 80,
      "reasoning": "PostgreSQL experience evident in multiple projects. Designed schemas for high-traffic applications."
    }
  },
  "summary": "John is a strong candidate with extensive Python and database experience...",
  "pros": [
    "6+ years of Python development",
    "FastAPI and Django expertise",
    "Strong system design skills"
  ],
  "cons": [
    "Limited AWS experience",
    "No Kubernetes mentioned"
  ],
  "created_at": "2025-12-31T11:15:00Z"
}
```

**Score Calculation** (Python, not AI):
```python
# Weighted average prevents AI arithmetic hallucinations
match_score = sum(category_score * importance) / sum(importance)
```

**Errors**:
- `404 Not Found`: Candidate doesn't exist OR no evaluation yet
- `404 Not Found`: Belongs to different tenant

---

### DELETE /api/v1/candidates/{candidate_id}

Delete a candidate and their evaluation.

**Authentication**: Required

**Path Parameters**:
- `candidate_id`: Integer candidate ID

**Response** (204 No Content): Empty body

**Side Effects**:
- Deletes Candidate record
- CASCADE deletes Evaluation record
- Deletes resume file from `uploads/` directory
- **Does NOT** decrement `candidates_used_this_month` (prevents abuse)

**Errors**:
- `404 Not Found`: Candidate doesn't exist OR belongs to different tenant

**Example**:
```bash
curl -X DELETE http://localhost:8000/api/v1/candidates/1 \
  -H "Authorization: Bearer YOUR_ACCESS_TOKEN"
```

---

## Stripe Webhook Endpoints

Base path: `/api/v1/stripe`

---

### POST /api/v1/stripe/webhook

Handle Stripe webhook events for subscription lifecycle management.

**Authentication**: Stripe signature verification (not JWT)

**Request Headers**:
- `Stripe-Signature`: Webhook signature for verification

**Request Body**: Stripe event JSON

**Handled Events**:

1. **invoice.payment_succeeded**:
   - Updates `subscription.status = ACTIVE`
   - Resets `candidates_used_this_month = 0` (monthly billing cycle)

2. **invoice.payment_failed**:
   - Updates `subscription.status = PAST_DUE`
   - User can't create jobs or upload candidates until payment succeeds

3. **customer.subscription.updated**:
   - Syncs plan changes (e.g., upgrade from STARTER to PROFESSIONAL)
   - Updates `subscription.plan` and `monthly_candidate_limit`

4. **customer.subscription.deleted**:
   - Updates `subscription.status = CANCELED`
   - User retains access until `current_period_end`

**Response** (200 OK):
```json
{
  "status": "success"
}
```

**Errors**:
- `400 Bad Request`: Invalid signature or payload
- `500 Internal Server Error`: Webhook processing failed

**Security**:
- Validates signature using `STRIPE_WEBHOOK_SECRET`
- Rejects requests with invalid signatures

---

## Common Response Formats

### Pagination

All list endpoints support pagination:

**Query Parameters**:
- `skip`: Number of records to skip (default: 0)
- `limit`: Number of records to return (default: 100, max: 100)

**Response**: Array of resources (not wrapped in pagination object)

**Example**:
```bash
# Get jobs 10-19
GET /api/v1/jobs/?skip=10&limit=10
```

---

### Timestamps

All timestamps use ISO 8601 format with UTC timezone:
```
"2025-12-31T11:15:00Z"
```

---

### UUIDs

User IDs and tenant IDs are UUIDs:
```
"123e4567-e89b-12d3-a456-426614174000"
```

---

## Error Handling

### Error Response Format

```json
{
  "detail": "Error message here"
}
```

**OR** (Pydantic validation errors):
```json
{
  "detail": [
    {
      "loc": ["body", "email"],
      "msg": "value is not a valid email address",
      "type": "value_error.email"
    }
  ]
}
```

---

### HTTP Status Codes

| Code | Meaning | Common Causes |
|------|---------|---------------|
| `200` | OK | Successful GET/POST request |
| `201` | Created | Resource created successfully |
| `204` | No Content | Successful DELETE request |
| `400` | Bad Request | Validation error, invalid input |
| `401` | Unauthorized | Missing/invalid/expired token |
| `402` | Payment Required | Subscription inactive or limit reached |
| `404` | Not Found | Resource doesn't exist or tenant mismatch |
| `422` | Unprocessable Entity | Pydantic validation failed |
| `500` | Internal Server Error | Server-side error (check logs) |

---

### Authentication Errors

**Missing Token**:
```json
{
  "detail": "Not authenticated"
}
```

**Invalid Token**:
```json
{
  "detail": "Could not validate credentials"
}
```

**Expired Token**:
```json
{
  "detail": "Token has expired"
}
```

---

### Billing Errors

**Subscription Inactive**:
```json
{
  "detail": "Subscription is past_due. Please update your payment method."
}
```

**Monthly Limit Reached**:
```json
{
  "detail": "Monthly candidate limit reached (5/5). Please upgrade your plan or wait for next billing cycle."
}
```

---

## Rate Limiting & Billing Constraints

### Current Limitations

**No Rate Limiting**: Currently no request rate limiting (planned for Phase 2)

**Billing Constraints**:
- Job creation requires active subscription
- Candidate upload enforces monthly limits based on plan:
  - FREE: 5 candidates/month
  - STARTER: 100 candidates/month
  - SMALL_BUSINESS: 250 candidates/month
  - PROFESSIONAL: 1,000 candidates/month
  - ENTERPRISE: Unlimited (pay-per-use)

**File Size Limits**:
- Resume uploads: 10MB max
- ZIP uploads: No explicit limit (should be set in Phase 2)

**Text Extraction Limits**:
- PDF: 6 pages max
- Resume text: 25,000 characters max (truncated)
- Job description: 15,000 characters max

---

## Testing with Swagger UI

**Interactive Documentation**: http://localhost:8000/docs

**Authentication**:
1. Click "Authorize" button (top right)
2. Paste your `access_token` (without "Bearer" prefix)
3. Click "Authorize"
4. All authenticated endpoints now work

**Alternative**: ReDoc documentation at http://localhost:8000/redoc

---

## Frontend Integration Pattern

### Using Auth.fetch() Wrapper

```javascript
// Frontend utility that auto-injects JWT and handles token refresh
Auth.fetch('http://localhost:8000/api/v1/jobs/', {
  method: 'POST',
  headers: {
    'Content-Type': 'application/json'
  },
  body: JSON.stringify({
    title: 'Senior Python Developer',
    description: '5+ years Python experience...'
  })
})
.then(response => response.json())
.then(data => console.log(data))
.catch(error => console.error(error));
```

**Benefits**:
- Auto-injects `Authorization: Bearer <token>` header
- Auto-refreshes on 401 errors
- Auto-redirects to login if refresh fails

---

*Last Updated: 2025-12-31*

*API Version: v1*
