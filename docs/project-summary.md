# Starscreen - Technical Reference

**Purpose**: AI resume screening with hybrid scoring (GPT-4o + deterministic Python)

**Status**: Phase 1 Complete - Multi-tenant SaaS with JWT authentication, Stripe billing, and complete authentication UI

## Stack
- **API**: FastAPI (Python) + Celery workers
- **Database**: PostgreSQL (Alembic migrations)
- **Queue**: Redis
- **AI**: OpenAI GPT-4o (temp=0.0)
- **Frontend**: Alpine.js + Tailwind CSS (static files)
- **Parsing**: pdfplumber, docx2txt
- **Auth**: JWT (stateless, HS256), localStorage-based token management
- **Billing**: Stripe (webhooks for subscription sync)
- **Security**: Bcrypt password hashing (72-byte limit), row-level multi-tenancy

## Architecture

```
User → Static HTML/JS → FastAPI API → PostgreSQL
       (Alpine.js)           ↓
                          Redis → Celery Workers
```

## Data Models

### users (Phase 1)
```python
id (UUID, PK)
tenant_id (UUID, unique)  # Multi-tenancy isolation key
email (unique, EmailStr)
hashed_password (bcrypt)
full_name (nullable)
company_name (nullable)
is_active (boolean, default=True)
is_verified (boolean, default=False)
created_at, updated_at, last_login_at
```

### subscriptions (Phase 1)
```python
id (UUID, PK)
user_id (FK -> users.id, unique)
stripe_customer_id (unique, nullable)
stripe_subscription_id (unique, nullable)
plan: ENUM(free, starter, professional, enterprise)
status: ENUM(trialing, active, past_due, canceled, unpaid)
monthly_candidate_limit (integer)
candidates_used_this_month (integer, default=0)
current_period_start (datetime)
current_period_end (datetime)
```

### jobs
```python
id (serial, PK)
tenant_id (UUID, FK -> users.tenant_id)  # Multi-tenancy
title (varchar)
description (text, max 15k chars)
location (varchar, nullable)
work_authorization_required (boolean)
status: PENDING → PROCESSING → COMPLETED/FAILED
job_config (JSONB)  # AI-generated scoring rubric
error_message (text, nullable)
created_at, updated_at
```

### candidates
```python
id (serial, PK)
tenant_id (UUID, FK -> users.tenant_id)  # Multi-tenancy
job_id (FK -> jobs.id, cascade delete)

# Contact fields (all nullable - blind screening support)
first_name, last_name, email, phone, location
linkedin_url, github_url, portfolio_url
other_urls (JSONB array)  # Additional URLs

file_path (varchar)  # Local file system path
original_filename (varchar)
resume_text (text, max 25k chars)
anonymized_text (text, nullable)
status: UPLOADED → PROCESSING → PARSED → SCORED/FAILED
error_message (text, nullable)
created_at, updated_at
```

### evaluations
```python
id (serial, PK)
tenant_id (UUID, FK -> users.tenant_id)  # Multi-tenancy
candidate_id (FK -> candidates.id, unique, cascade delete)
match_score (numeric, 0-100)  # Python-calculated weighted average
category_scores (JSONB)  # {"Python": {"score": 85, "reasoning": "..."}, ...}
summary (text)  # AI-generated executive summary
pros (JSONB array)  # ["Strength 1", "Strength 2", ...]
cons (JSONB array)  # ["Gap 1", "Gap 2", ...]
created_at
```

**Relationships**:
- User →→ Jobs →→ Candidates → Evaluation
- All relationships use CASCADE DELETE via tenant_id foreign keys

## Processing Pipeline

### Job Creation Flow
1. **POST /api/v1/jobs** → Insert into DB (status=PENDING, with tenant_id)
2. **Celery task**: `generate_job_config_task(job_id)`
   - GPT-4o analyzes job description
   - Generates structured rubric: `{"categories": [{"name": "Python", "importance": 5, "keywords": [...]}]}`
   - Updates `job_config` JSONB field
   - Status: PENDING → PROCESSING → COMPLETED

### Resume Upload & Scoring Flow
1. **POST /api/v1/jobs/{id}/candidates** → Save file to `uploads/` directory
2. **Celery task**: `parse_resume_task(candidate_id)`
   - Extract text from PDF (6 pages max) or DOCX
   - Truncate to 25k characters
   - Status: UPLOADED → PROCESSING → PARSED
   - Auto-chains to scoring task
3. **Celery task**: `score_candidate_task(candidate_id)` *(Auto-chained)*
   - **AI Portion**: GPT-4o analyzes resume against job_config
     - Grades each category (0-100)
     - Extracts PII: first_name, last_name, email, phone, location
     - Extracts URLs: LinkedIn, GitHub, Portfolio, and other URLs
     - Generates summary, pros, cons
   - **Python Portion**: Calculates weighted score
     - Formula: `sum(category_score * importance) / sum(importance)`
     - This prevents AI arithmetic hallucinations
   - **Database Updates**:
     - Create Evaluation record (with tenant_id)
     - Update Candidate contact fields (only if NULL and AI found them)
     - Update Candidate URLs (smart sorting)
   - Status: PARSED → SCORED

## Authentication & Authorization (Phase 1)

### JWT Token System

**Token Types**:
- **Access Token**: 30-minute lifespan, used for API requests
- **Refresh Token**: 7-day lifespan, used to obtain new access tokens

**Token Structure** (HS256 signed):
```json
{
  "sub": "user_email@example.com",
  "tenant_id": "uuid-here",
  "exp": 1234567890
}
```

**Storage**: Tokens stored in browser `localStorage`:
- Key: `starscreen_access_token`
- Key: `starscreen_refresh_token`

### API Endpoints (app/api/endpoints/auth.py)

- **POST /api/v1/auth/register**
  - Input: `{email, password, full_name?, company_name?}`
  - Validation: Email format, password strength (8-72 chars, uppercase, lowercase, number, special)
  - Creates: User + Subscription (plan=FREE, status=TRIALING)
  - Returns: `{access_token, refresh_token, token_type}`

- **POST /api/v1/auth/login**
  - Input: `{username: email, password}` (OAuth2 spec uses "username")
  - Validates credentials with bcrypt
  - Updates `last_login_at` timestamp
  - Returns: `{access_token, refresh_token, token_type}`

- **POST /api/v1/auth/refresh**
  - Input: `{refresh_token}`
  - Validates refresh token
  - Returns: NEW `{access_token, refresh_token, token_type}`

- **GET /api/v1/auth/me**
  - Requires: `Authorization: Bearer <access_token>`
  - Returns: User profile (id, email, full_name, company_name, tenant_id)

### Frontend Authentication (static/auth.js)

**Auth Utility Object** (`Auth`):
```javascript
Auth.login(accessToken, refreshToken)      // Store tokens
Auth.logout()                               // Clear tokens, redirect to login
Auth.isAuthenticated()                      // Check if logged in (validates exp)
Auth.getAccessToken()                       // Get current token
Auth.getAuthHeaders()                       // Get {'Authorization': 'Bearer ...'}
Auth.fetch(url, options)                    // Auto-injects headers, auto-refreshes on 401
Auth.refreshAccessToken()                   // Refresh tokens
Auth.parseJWT(token)                        // Decode JWT (client-side only)
```

**Auto-Refresh Flow**:
1. API request gets 401 Unauthorized
2. `Auth.fetch()` automatically calls `Auth.refreshAccessToken()`
3. Retries original request with new token
4. If refresh fails → logout user

**Route Protection**:
- `auth.js` includes DOMContentLoaded listener
- Public pages: `login.html`, `register.html`
- All other pages require authentication (auto-redirect to login)

### Password Validation (app/schemas/user.py)

**Backend Validation** (Pydantic):
```python
@field_validator('password')
def validate_password_strength(cls, v: str) -> str:
    # Length: 8-72 characters (bcrypt limitation)
    # Must contain: lowercase, uppercase, number, special char
    # Special chars: !@#$%^&*(),.?":{}|<>
```

**Frontend Validation** (register.html):
- Real-time checklist with green/red indicators
- Password visibility toggle (eye icon)
- Confirm password matching indicator
- All validation logic in `validatePassword()` and `validatePasswordMatch()`

### Multi-Tenancy Implementation

**Row-Level Security**:
- Every protected resource has `tenant_id` column
- All queries filter by `tenant_id` via dependency injection
- Dependency: `get_tenant_id(token)` extracts tenant_id from JWT

**Development Mode**:
- Currently using `get_tenant_id_optional()` in jobs.py and candidates.py
- Allows testing without authentication
- **Production**: Replace with `get_tenant_id()` to enforce auth

**Tenant Isolation**:
```python
# app/crud/job.py example
def get_multi(db, tenant_id, skip=0, limit=100):
    query = db.query(Job).filter(Job.tenant_id == tenant_id)
    return query.offset(skip).limit(limit).all()
```

## Frontend Architecture

### File Structure
```
static/
├── index.html         # Main dashboard (Alpine.js SPA)
├── login.html         # Login page (Alpine.js form)
├── register.html      # Registration page (Alpine.js form)
├── auth.js            # Authentication utility library
└── analysis.html      # Candidate detail view

public/
└── images/
    └── Logo.png       # Starscreen logo
```

### Main Dashboard (static/index.html)

**Features**:
- Job creation form with AI-powered config generation
- Job list with expand/collapse
- Resume upload (drag-drop + file picker)
- Candidate table with real-time status updates
- Analysis modal with detailed scoring
- Logout button

**Tech Stack**:
- Alpine.js for reactivity (x-data, x-model, x-show, etc.)
- Tailwind CSS for styling (CDN-loaded)
- `Auth.fetch()` for all API calls (auto-injects JWT)

**Key State Variables**:
```javascript
jobs: [],           // List of jobs
candidates: [],     // List of candidates for selected job
selectedJob: null,  // Currently expanded job
selectedCandidate: null,  // Candidate being viewed in modal
```

### Login Page (static/login.html)

**Features**:
- Email + password form
- Error message display (red banner)
- Success message (green banner)
- Auto-redirect if already logged in
- Link to registration page

**Alpine.js State**:
```javascript
{
  email: '',
  password: '',
  loading: false,
  errorMessage: '',
  successMessage: ''
}
```

**Error Handling**:
- Parses FastAPI error formats: string detail, array detail (Pydantic), object with message
- Displays user-friendly error messages

### Registration Page (static/register.html)

**Features**:
- Email, password, confirm password, full name, company name
- Real-time password validation with visual checklist
- Password visibility toggles (eye icons)
- Password match indicator
- Auto-redirect if already logged in
- Link to login page

**Password Validation UI**:
- 5 requirements with green checkmarks / red X icons:
  - 8-72 characters
  - Lowercase letter
  - Uppercase letter
  - Number
  - Special character (!@#$%^&*)
- Password match indicator (green "Passwords match" / red "Passwords do not match")

**Alpine.js State**:
```javascript
{
  email: '',
  password: '',
  confirm_password: '',
  full_name: '',
  company_name: '',
  loading: false,
  errorMessage: '',
  successMessage: '',
  showPassword: false,
  showConfirmPassword: false,
  passwordsMatch: false,
  passwordChecks: {
    length: false,
    lowercase: false,
    uppercase: false,
    number: false,
    special: false
  }
}
```

**Functions**:
- `validatePassword()`: Checks all password requirements with regex
- `validatePasswordMatch()`: Checks if passwords match
- `handleRegister()`: Form submission, API call, token storage

**Layout Fix**: Uses `min-h-screen` instead of `h-full` to prevent content cutoff on tall forms

## Key Implementation Rules

### File Parsing (app/tasks/resume_tasks.py)

**PDF Files**:
- Maximum 6 pages extracted
- Maximum 25,000 characters total
- Uses `pdfplumber` library
- Error handling: Rejects corrupted PDFs

**DOCX Files**:
- Maximum 25,000 characters
- Uses `docx2txt` library

**DOC Files**:
- Rejected with message: "Please convert .doc to .docx or PDF"

**Storage**:
- Files saved to `uploads/` directory (local filesystem)
- Path format: `uploads/{original_filename}`
- **Future**: Migrate to S3 for horizontal scaling

### Scoring Engine (app/tasks/scoring_tasks.py)

**Hybrid Architecture** (AI + Python):
- **AI Responsibilities**:
  - Grade each category (0-100) based on resume evidence
  - Extract PII: first_name, last_name, email, phone, location
  - Extract URLs: LinkedIn, GitHub, Portfolio, and other URLs
  - Generate summary (2 paragraphs)
  - Generate pros (3 items)
  - Generate cons (2 items)

- **Python Responsibilities**:
  - Calculate weighted final score: `sum(score * importance) / sum(importance)`
  - This prevents AI from hallucinating arithmetic
  - Update database with extracted data

**Grading Scale** (communicated to AI):
- 0-20: No evidence found
- 21-50: Listed in Skills section, but no project usage
- 51-75: Competent - used in at least one project
- 76-90: Strong match - multiple projects, years of experience
- 91-100: Exceptional - lead architect, major achievements

**Contact Field Updates**:
- Only update if AI found the field AND field is currently NULL
- Preserves manually entered contact information
- Example logic:
  ```python
  if contact_info.get("email") and not candidate.email:
      candidate.email = contact_info.get("email")
  ```

**URL Extraction & Smart Sorting**:
1. AI returns: `linkedin_url`, `github_url`, `portfolio_url`, `all_other_urls[]`
2. Python assigns to dedicated columns
3. Remove duplicates from `other_urls`
4. Store remaining URLs as JSONB array

**Error Handling**:
- If scoring fails → `candidate.status = FAILED`, `candidate.error_message = str(e)`
- Idempotent: Deletes existing evaluation before creating new one

### Legal Compliance

**Terminology**:
- Use "Relevance Indicator" not "Match Score" in UI
- Disclaimer: "This is a decision-support tool, not a hiring decision"

**Blind Screening Support**:
- All candidate contact fields are nullable
- Resume text extraction doesn't require PII
- AI extracts PII opportunistically, doesn't fail if missing

**Data Retention**:
- CASCADE DELETE: Deleting user deletes all jobs/candidates/evaluations

## Code Structure

```
Resume-Analyzer/
├── app/
│   ├── api/
│   │   ├── deps.py              # Auth dependencies (get_current_user, get_tenant_id)
│   │   └── endpoints/
│   │       ├── auth.py          # Register, login, refresh, me
│   │       ├── jobs.py          # Job CRUD + config generation
│   │       ├── candidates.py    # Upload + retrieval + analysis
│   │       └── stripe_webhooks.py  # Stripe event handling
│   ├── core/
│   │   ├── config.py            # Settings (loads from .env)
│   │   ├── database.py          # PostgreSQL session
│   │   ├── celery_app.py        # Redis broker config
│   │   └── security.py          # JWT + bcrypt utilities
│   ├── crud/
│   │   ├── job.py               # Repository pattern for Job
│   │   ├── candidate.py         # Repository pattern for Candidate
│   │   └── user.py              # Repository pattern for User
│   ├── models/                  # SQLAlchemy models
│   │   ├── user.py              # User, Subscription
│   │   ├── job.py               # Job
│   │   ├── candidate.py         # Candidate
│   │   └── evaluation.py        # Evaluation
│   ├── schemas/                 # Pydantic validation
│   │   ├── user.py              # UserRegisterRequest, UserLoginRequest, TokenResponse
│   │   ├── job.py               # JobCreateRequest, JobResponse
│   │   └── candidate.py         # CandidateResponse, EvaluationResponse
│   └── tasks/                   # Celery tasks
│       ├── resume_tasks.py      # parse_resume_task
│       ├── scoring_tasks.py     # score_candidate_task (hybrid AI+Python)
│       └── job_tasks.py         # generate_job_config_task
├── static/
│   ├── index.html               # Main dashboard
│   ├── login.html               # Login page (Alpine.js)
│   ├── register.html            # Registration page (Alpine.js + validation)
│   ├── auth.js                  # Auth utility library
│   └── analysis.html            # Candidate detail view
├── public/
│   └── images/
│       └── Logo.png             # Starscreen branding
├── uploads/                     # Resume file storage (local)
├── alembic/                     # Database migrations
│   └── versions/                # Migration files
├── docs/
│   └── project-summary.md       # This file
├── main.py                      # FastAPI app entry point
├── docker-compose.yml           # Multi-container orchestration
├── Dockerfile                   # API + Worker image
├── requirements.txt             # Python dependencies
└── .env                         # Environment variables
```

## Environment Variables (.env)

**Required**:
```bash
# Database
DATABASE_URL=postgresql://starscreen:password@db:5432/starscreen

# Redis (Celery)
CELERY_BROKER_URL=redis://redis:6379/0
CELERY_RESULT_BACKEND=redis://redis:6379/0

# OpenAI
OPENAI_API_KEY=sk-...

# JWT Authentication
SECRET_KEY=<openssl rand -hex 32>
ALGORITHM=HS256
ACCESS_TOKEN_EXPIRE_MINUTES=30
REFRESH_TOKEN_EXPIRE_DAYS=7
```

**Optional** (Stripe - skip for testing):
```bash
STRIPE_API_KEY=sk_test_...
STRIPE_WEBHOOK_SECRET=whsec_...
STRIPE_PRICE_ID_STARTER=price_...
STRIPE_PRICE_ID_PROFESSIONAL=price_...
```

**Note**: Without Stripe keys, app works fine - all users get FREE trial subscriptions.

## Common Commands

### Docker Operations
```bash
# Start all services
docker-compose up -d

# View logs
docker-compose logs -f api
docker-compose logs -f worker

# Restart services
docker-compose restart api worker

# Rebuild after dependency changes
docker-compose down
docker-compose build
docker-compose up -d
```

### Database Operations
```bash
# Run migrations
docker-compose exec api alembic upgrade head

# Create new migration
docker-compose exec api alembic revision --autogenerate -m "Description"

# Access database
docker-compose exec db psql -U starscreen -d starscreen

# Reset database (WARNING: deletes all data)
docker-compose down -v
docker-compose up -d
docker-compose exec api alembic upgrade head
```

### Celery Operations
```bash
# Check worker status
docker-compose exec worker celery -A app.core.celery_app inspect active

# Purge task queue
docker-compose exec worker celery -A app.core.celery_app purge
```

## API Documentation

- **Swagger UI**: http://localhost:8000/docs
- **ReDoc**: http://localhost:8000/redoc

**Testing with Swagger**:
1. Click "Authorize" button
2. Paste access_token (without "Bearer")
3. All authenticated endpoints now work

## Testing

### Manual Testing Flow

**1. Register New User**:
```bash
curl -X POST http://localhost:8000/api/v1/auth/register \
  -H "Content-Type: application/json" \
  -d '{
    "email": "test@example.com",
    "password": "Test123!@#",
    "full_name": "Test User",
    "company_name": "Test Co"
  }'

# Save the access_token from response
```

**2. Create Job**:
```bash
curl -X POST http://localhost:8000/api/v1/jobs/ \
  -H "Authorization: Bearer YOUR_ACCESS_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "title": "Senior Python Developer",
    "description": "5+ years Python, FastAPI, PostgreSQL, AWS experience required",
    "location": "Remote"
  }'

# Note the job "id" from response
```

**3. Upload Resume**:
```bash
curl -X POST http://localhost:8000/api/v1/jobs/1/candidates \
  -H "Authorization: Bearer YOUR_ACCESS_TOKEN" \
  -F "file=@/path/to/resume.pdf"

# Note the candidate "id" from response
```

**4. Check Candidate Status**:
```bash
curl -X GET http://localhost:8000/api/v1/candidates/1 \
  -H "Authorization: Bearer YOUR_ACCESS_TOKEN"

# Status progression: UPLOADED → PROCESSING → PARSED → SCORED
```

**5. View Analysis**:
```bash
curl -X GET http://localhost:8000/api/v1/candidates/1/analysis \
  -H "Authorization: Bearer YOUR_ACCESS_TOKEN"

# Returns: match_score, category_scores, summary, pros, cons
```

### Multi-Tenancy Testing

**Verify tenant isolation**:
```bash
# Create Company A user
TOKEN_A=$(curl -X POST http://localhost:8000/api/v1/auth/register \
  -H "Content-Type: application/json" \
  -d '{"email": "companya@test.com", "password": "Test123!@#"}' \
  | jq -r '.access_token')

# Create Company B user
TOKEN_B=$(curl -X POST http://localhost:8000/api/v1/auth/register \
  -H "Content-Type: application/json" \
  -d '{"email": "companyb@test.com", "password": "Test123!@#"}' \
  | jq -r '.access_token')

# Company A creates job
JOB_A=$(curl -X POST http://localhost:8000/api/v1/jobs/ \
  -H "Authorization: Bearer $TOKEN_A" \
  -H "Content-Type: application/json" \
  -d '{"title": "Secret Job A", "description": "Confidential"}' \
  | jq -r '.id')

# Company B should NOT see Company A's job
curl -X GET http://localhost:8000/api/v1/jobs/$JOB_A \
  -H "Authorization: Bearer $TOKEN_B"

# Expected: 404 Not Found (tenant isolation working)
```

## Troubleshooting

### Common Errors

**401 Unauthorized**:
- Verify `Authorization: Bearer <token>` header format
- Check if token expired (30 min for access token)
- Ensure SECRET_KEY is set in .env
- Try refreshing token or re-logging in

**Candidates Stuck at PARSED**:
- Check worker logs: `docker-compose logs -f worker`
- Verify `tenant_id` is set on Evaluation model (bug fixed in scoring_tasks.py:281)
- Restart worker: `docker-compose restart worker`

**Password Validation Errors**:
- Password must be 8-72 characters (bcrypt limitation)
- Requires: lowercase, uppercase, number, special character (!@#$%^&*(),.?":{}|<>)
- Frontend shows real-time validation checklist

**"[object Object]" Error on Login**:
- Fixed in login.html:149 - sends `username` field instead of `email`
- Backend expects OAuth2-compliant request format

**Registration Page Content Cutoff**:
- Fixed in register.html:2,39 - uses `min-h-screen` instead of `h-full`
- Allows scrolling for tall forms

**Migration Errors**:
```bash
# Reset database (WARNING: deletes all data)
docker-compose down -v
docker-compose up -d
docker-compose exec api alembic upgrade head
```

**Celery Worker Not Processing**:
```bash
# Check worker status
docker-compose logs worker

# Restart worker
docker-compose restart worker

# Purge stuck tasks
docker-compose exec worker celery -A app.core.celery_app purge
```

## Current Limitations & Future Work

### Phase 1 Complete ✓
- [x] JWT authentication system
- [x] Multi-tenant database architecture
- [x] Stripe billing integration (optional)
- [x] Login/registration UI with password validation
- [x] Token-based auth in frontend (Auth.js)
- [x] Auto-refresh tokens on 401 errors
- [x] Password validation with real-time feedback
- [x] Multi-tenancy isolation for all resources

### Phase 2 - Production Readiness
- [ ] **S3 File Storage**: Replace local `uploads/` with AWS S3
  - Enables horizontal scaling (stateless API servers)
  - Update: `app/api/endpoints/candidates.py`, `app/tasks/resume_tasks.py`
- [ ] **Email Verification**: Send verification email on registration
- [ ] **Password Reset**: Forgot password flow with email
- [ ] **Rate Limiting**: Protect OpenAI API calls, prevent abuse
- [ ] **Unit Tests**: pytest for API endpoints and tasks
- [ ] **Monitoring**: Sentry for error tracking, Prometheus for metrics
- [ ] **Logging**: Replace print with structured JSON logging (structlog)

### Known Issues
- [ ] Local file storage blocks horizontal scaling
- [ ] No email verification (is_verified always False)
- [ ] No password reset functionality
- [ ] No API rate limiting
- [ ] No user profile editing UI
- [ ] Development mode uses optional auth (`get_tenant_id_optional`)
  - Production: Replace with `get_tenant_id()` to enforce auth

## Security Considerations

### Current Security Measures
- ✅ Bcrypt password hashing (72-byte limit enforced)
- ✅ JWT tokens with expiration
- ✅ Row-level multi-tenancy (tenant_id filtering)
- ✅ HTTPS recommended for production
- ✅ Password strength validation (frontend + backend)
- ✅ Pydantic validation for all inputs
- ✅ SQL injection prevention (SQLAlchemy ORM)

### Production Recommendations
- Use environment variables for all secrets (never hardcode)
- Enable CORS restrictions (currently allows all origins)
- Implement rate limiting on auth endpoints
- Add CAPTCHA to registration (prevent bots)
- Enable HTTPS-only cookies for tokens (migrate from localStorage)
- Add CSP headers to prevent XSS
- Regular dependency updates (Dependabot)
- Database backups and disaster recovery plan

## Migration Notes

### Breaking Changes from Pre-Auth Version
- All jobs/candidates now require `tenant_id`
- Legacy data assigned to `legacy@starscreen.internal` user
- API endpoints now require `Authorization: Bearer <token>` header
- Frontend must use `Auth.fetch()` instead of regular `fetch()`

### Database Enum Types Created
```sql
CREATE TYPE subscriptionplan AS ENUM ('free', 'starter', 'professional', 'enterprise');
CREATE TYPE subscriptionstatus AS ENUM ('trialing', 'active', 'past_due', 'canceled', 'unpaid');
```

### Tenant ID Propagation
All resources cascade from `users.tenant_id`:
```
users.tenant_id (unique)
  ↓
jobs.tenant_id
  ↓
candidates.tenant_id
  ↓
evaluations.tenant_id
```

## Additional Resources

**Frontend Frameworks**:
- Alpine.js Docs: https://alpinejs.dev
- Tailwind CSS Docs: https://tailwindcss.com

**Backend Libraries**:
- FastAPI Docs: https://fastapi.tiangolo.com
- SQLAlchemy ORM: https://docs.sqlalchemy.org
- Celery Docs: https://docs.celeryproject.org
- Pydantic Validation: https://docs.pydantic.dev

**OpenAI API**:
- GPT-4 Docs: https://platform.openai.com/docs

**Deployment**:
- Docker Compose: https://docs.docker.com/compose/
- Alembic Migrations: https://alembic.sqlalchemy.org

---

*Last Updated: 2025-12-31*

*Phase 1 Complete - Multi-tenant SaaS with JWT auth + UI*

*For LLM code assistance: This document provides complete context for understanding and modifying the Starscreen codebase. All architectural decisions, implementation patterns, and critical bugs/fixes are documented above.*
