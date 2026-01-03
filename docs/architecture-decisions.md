# Starscreen Architecture & Design Decisions

> **LLM Context**: This document explains the architectural choices, design patterns, and technical trade-offs made in building the Starscreen resume screening platform. Use this to understand WHY the system is built this way, not just HOW it works.

**Project Phase**: Phase 1 Complete (Multi-tenant SaaS with JWT auth and billing)

**Architecture Style**: Monolithic API + Async Workers (transitioning to microservices in Phase 2+)

---

## Table of Contents

1. [System Architecture Overview](#system-architecture-overview)
2. [Technology Stack Decisions](#technology-stack-decisions)
3. [Authentication & Security Design](#authentication--security-design)
4. [Multi-Tenancy Pattern](#multi-tenancy-pattern)
5. [Data Processing Pipeline](#data-processing-pipeline)
6. [AI Integration Strategy](#ai-integration-strategy)
7. [Billing & Subscription Model](#billing--subscription-model)
8. [Frontend Architecture](#frontend-architecture)
9. [Database Design Decisions](#database-design-decisions)
10. [Trade-offs & Future Improvements](#trade-offs--future-improvements)

---

## System Architecture Overview

### High-Level Architecture

```
┌─────────────────────────────────────────────────────────────┐
│                    User's Browser                           │
│  (Alpine.js + Tailwind CSS + Auth.js)                       │
└────────────────────┬────────────────────────────────────────┘
                     │ HTTPS (JWT in Authorization header)
                     ▼
┌─────────────────────────────────────────────────────────────┐
│               FastAPI Application (Port 8000)                │
│  ┌──────────────────────────────────────────────────────┐   │
│  │  API Endpoints                                       │   │
│  │  - /api/v1/auth (login, register, refresh)          │   │
│  │  - /api/v1/jobs (CRUD operations)                    │   │
│  │  - /api/v1/candidates (upload, analysis)            │   │
│  │  - /api/v1/stripe/webhook (subscription sync)       │   │
│  └───────────┬──────────────────────────────────────────┘   │
│              │                                               │
│  ┌───────────▼──────────────────────────────────────────┐   │
│  │  Business Logic Layer                                │   │
│  │  - JWT validation (app/api/deps.py)                  │   │
│  │  - Tenant isolation enforcement                      │   │
│  │  - Subscription limit checks                         │   │
│  │  - Pydantic request/response validation              │   │
│  └───────────┬──────────────────────────────────────────┘   │
│              │                                               │
│  ┌───────────▼──────────────────────────────────────────┐   │
│  │  Data Access Layer (CRUD)                            │   │
│  │  - SQLAlchemy ORM queries                            │   │
│  │  - Multi-tenant filtering on all queries             │   │
│  │  - Transaction management                            │   │
│  └───────────┬──────────────────────────────────────────┘   │
└──────────────┼───────────────────────────────────────────────┘
               │
               ▼
┌─────────────────────────────────────────────────────────────┐
│           PostgreSQL Database (Port 5432)                    │
│  Tables: users, subscriptions, jobs, candidates, evaluations │
│  Row-Level Security: tenant_id on all resources              │
└─────────────────────────────────────────────────────────────┘

               │
               │ (FastAPI enqueues tasks)
               ▼
┌─────────────────────────────────────────────────────────────┐
│              Redis Message Broker (Port 6379)                │
│  Celery Task Queue: parse_resume, score_candidate, gen_config│
└────────────────────┬────────────────────────────────────────┘
                     │ (Celery workers pull tasks)
                     ▼
┌─────────────────────────────────────────────────────────────┐
│            Celery Worker Processes                           │
│  ┌──────────────────────────────────────────────────────┐   │
│  │  Resume Parsing Worker                               │   │
│  │  - PDF extraction (pdfplumber)                       │   │
│  │  - DOCX extraction (docx2txt)                        │   │
│  │  - Text truncation (25k chars)                       │   │
│  └───────────┬──────────────────────────────────────────┘   │
│              │                                               │
│  ┌───────────▼──────────────────────────────────────────┐   │
│  │  Candidate Scoring Worker                            │   │
│  │  - OpenAI GPT-4o API calls                           │   │
│  │  - Category grading (AI)                             │   │
│  │  - PII extraction (AI)                               │   │
│  │  - Weighted score calculation (Python)               │   │
│  └───────────┬──────────────────────────────────────────┘   │
│              │                                               │
│  ┌───────────▼──────────────────────────────────────────┐   │
│  │  Job Config Generation Worker                        │   │
│  │  - GPT-4o analyzes job description                   │   │
│  │  - Generates scoring rubric (categories + keywords)  │   │
│  └──────────────────────────────────────────────────────┘   │
└─────────────────────────────────────────────────────────────┘
```

### Request Flow Examples

#### User Registration
1. Browser → POST /api/v1/auth/register (email, password)
2. API validates password strength (Pydantic)
3. API hashes password (bcrypt, 72-byte limit)
4. API generates tenant_id (UUID v4)
5. API creates User record
6. API creates Subscription record (plan=FREE, status=TRIALING)
7. API generates JWT tokens (access + refresh)
8. API returns tokens to browser
9. Browser stores tokens in localStorage

#### Resume Upload & Scoring
1. Browser → POST /api/v1/jobs/{id}/candidates (multipart file)
2. API validates JWT token → extracts tenant_id
3. API checks subscription.can_upload_candidate → enforces limit
4. API saves file to uploads/ directory
5. API creates Candidate record (status=UPLOADED)
6. API increments subscription.candidates_used_this_month
7. API enqueues parse_resume_task(candidate_id) → Redis
8. API returns candidate_id to browser
9. Celery worker pulls task from Redis
10. Worker extracts text from PDF/DOCX → updates status=PARSED
11. Worker auto-chains to score_candidate_task(candidate_id)
12. Worker calls GPT-4o API with resume + job rubric
13. Worker receives category scores + PII from AI
14. Worker calculates weighted match_score (Python, not AI)
15. Worker creates Evaluation record
16. Worker updates Candidate contact fields (if NULL)
17. Worker updates status=SCORED
18. Browser polls GET /api/v1/candidates/{id} → sees SCORED status
19. Browser fetches GET /api/v1/candidates/{id}/analysis → displays results

---

## Technology Stack Decisions

### Backend: FastAPI (Python)

**Why FastAPI?**
- ✅ Automatic API documentation (Swagger UI, ReDoc)
- ✅ Built-in Pydantic validation (type safety, error messages)
- ✅ Async support (handles I/O-bound tasks efficiently)
- ✅ Dependency injection (clean auth middleware)
- ✅ Fast performance (comparable to Node.js/Go)
- ✅ Python ecosystem (OpenAI SDK, pdfplumber, ML libraries)

**Alternatives Considered**:
- Django REST Framework: Too heavyweight, slower iteration
- Flask: Less built-in features, more boilerplate
- Node.js (Express): Less suitable for ML/AI tasks

---

### Database: PostgreSQL

**Why PostgreSQL?**
- ✅ JSONB support (flexible schema for job_config, category_scores)
- ✅ UUID support (secure, non-enumerable user IDs)
- ✅ Enum types (subscriptionplan, subscriptionstatus)
- ✅ ACID compliance (critical for billing)
- ✅ Full-text search (future: resume text search)
- ✅ Strong ecosystem (Alembic migrations, pgAdmin)

**Alternatives Considered**:
- MySQL: Weaker JSON support, no native UUID type
- MongoDB: Less suitable for relational data (users → jobs → candidates)
- DynamoDB: Overkill for MVP, vendor lock-in

---

### Task Queue: Celery + Redis

**Why Celery + Redis?**
- ✅ Async processing (doesn't block API requests)
- ✅ Retry logic (handles OpenAI API failures)
- ✅ Task chaining (parse → score automatically)
- ✅ Monitoring tools (Flower dashboard)
- ✅ Horizontal scaling (add more workers)

**Alternatives Considered**:
- AWS Lambda: Vendor lock-in, cold start latency
- RabbitMQ: More complex setup than Redis
- Dramatiq: Less mature ecosystem

---

### ORM: SQLAlchemy 2.0

**Why SQLAlchemy?**
- ✅ Powerful ORM with relationship management
- ✅ Migration support (Alembic integration)
- ✅ SQL injection protection (parameterized queries)
- ✅ Flexible (can drop to raw SQL when needed)
- ✅ Database agnostic (easier to switch DBs)

**Alternatives Considered**:
- Raw SQL: Too much boilerplate, error-prone
- Peewee: Less feature-rich, smaller community
- Tortoise ORM: Less mature, async-only

---

### AI Provider: OpenAI GPT-4o

**Why GPT-4o?**
- ✅ State-of-the-art language understanding
- ✅ JSON mode (structured output for category scores)
- ✅ Consistent quality (better than GPT-3.5)
- ✅ Low temperature (0.2) for deterministic output
- ✅ Good cost/performance ratio ($2.50 per 1M input tokens)

**Alternatives Considered**:
- GPT-3.5 Turbo: Cheaper but less accurate (especially for nuanced scoring)
- Claude (Anthropic): No JSON mode at time of implementation
- Llama 2 (open-source): Requires self-hosting, higher complexity

**Cost Analysis** (GPT-4o):
- Resume scoring: ~2,000 tokens input + ~500 tokens output = $0.006/candidate
- FREE tier (5 candidates): $0.03/month
- RECRUITER tier (100 candidates): $0.60/month
- PROFESSIONAL tier (1,000 candidates): $6/month

**Why Hybrid AI + Python?**
- AI handles subjective evaluation (category grading, pros/cons)
- Python handles arithmetic (weighted score calculation)
- **Prevents hallucinations**: AI can't make math errors in final score

---

### Frontend: Alpine.js + Tailwind CSS (Static Files)

**Why Alpine.js?**
- ✅ Lightweight (15KB, no build step)
- ✅ Vue-like syntax (easy learning curve)
- ✅ Perfect for SPAs without complexity
- ✅ Fast iteration (no npm, webpack, etc.)
- ✅ Works with static HTML files

**Why Tailwind CSS?**
- ✅ Utility-first (rapid prototyping)
- ✅ CDN available (no build step in Phase 1)
- ✅ Consistent design system
- ✅ Responsive by default

**Alternatives Considered**:
- React: Overkill for Phase 1, requires build pipeline
- Vue.js: Heavier than Alpine, similar benefits
- Svelte: Requires build step, less mature ecosystem
- Pure Vanilla JS: Too much boilerplate

**Why Static Files (No SPA Framework)?**
- ✅ Faster development (no Node.js, no build pipeline)
- ✅ Easier deployment (serve from FastAPI /static)
- ✅ Good enough for MVP

**Phase 2+ Migration**: Will consider React/Next.js for:
- Server-side rendering (SEO)
- Complex state management
- Code splitting
- Better TypeScript support

---

### Authentication: JWT (Stateless)

**Why JWT?**
- ✅ Stateless (no session storage in database)
- ✅ Horizontal scaling (any API server can validate)
- ✅ Mobile-friendly (easy to store in app)
- ✅ Self-contained (includes user_id, tenant_id)
- ✅ Industry standard (RFC 7519)

**Why HS256 (Symmetric) instead of RS256 (Asymmetric)?**
- ✅ Simpler setup (one SECRET_KEY, not public/private key pair)
- ✅ Faster signing/verification
- ✅ Good enough for single-service architecture
- ❌ Limitation: Can't distribute public key to third parties
- **Future**: Migrate to RS256 for microservices architecture

**Why localStorage instead of httpOnly cookies?**
- ✅ Easier CORS handling (no SameSite issues)
- ✅ Simpler frontend code (Auth.js utility)
- ✅ Mobile app compatibility (can use same tokens)
- ❌ Security trade-off: Vulnerable to XSS (mitigated by CSP headers in Phase 2)

---

## Authentication & Security Design

### Password Security

**Hashing Algorithm**: bcrypt with default cost factor (12 rounds)

**Why bcrypt?**
- ✅ Designed for password hashing (slow by design)
- ✅ Salt built-in (prevents rainbow table attacks)
- ✅ Industry standard (OWASP recommended)
- ✅ Adjustable cost factor (can increase difficulty over time)

**Why not SHA-256 or MD5?**
- ❌ Too fast (vulnerable to brute-force)
- ❌ No salt (unless manually implemented)
- ❌ Not designed for passwords

**72-Byte Limit**:
- Bcrypt has hard 72-byte limit (UTF-8 encoded)
- Passwords >72 bytes are silently truncated by bcrypt library
- We enforce this in app/core/security.py to prevent confusion
- Frontend validates 8-72 characters (prevents user confusion)

**Password Requirements**:
- Minimum: 8 characters
- Maximum: 72 characters (bcrypt limit)
- Must contain: lowercase, uppercase, number, special char
- Special chars allowed: `!@#$%^&*(),.?":{}|<>`

**Why these requirements?**
- Balances security with usability
- Prevents weak passwords like "password123"
- Aligned with NIST 800-63B guidelines

---

### JWT Token Design

**Token Structure**:
```json
{
  "sub": "user-uuid-here",        // User ID (subject)
  "tenant_id": "tenant-uuid-here", // Multi-tenancy isolation
  "exp": 1735660800,               // Expiration timestamp
  "type": "refresh"                // Only in refresh tokens
}
```

**Why include tenant_id in token?**
- Avoids database lookup on every request
- Enforces tenant isolation at API layer
- Faster performance (no JOIN to users table)

**Token Expiration Strategy**:
- **Access Token**: 30 minutes (short-lived for security)
- **Refresh Token**: 7 days (long-lived for UX)

**Why 30 minutes for access token?**
- Limits damage if token is stolen (XSS, MITM)
- Forces periodic re-validation
- Balances security with UX (auto-refresh on 401)

**Why 7 days for refresh token?**
- Avoids frequent re-login (better UX)
- Long enough for "remember me" functionality
- Short enough to limit risk if device is compromised

**Token Refresh Flow**:
1. Access token expires (30 min)
2. Frontend gets 401 Unauthorized
3. Auth.fetch() automatically calls /auth/refresh with refresh token
4. API validates refresh token, issues NEW access + refresh tokens
5. Frontend retries original request with new access token
6. If refresh fails → redirect to login

**Why issue new refresh token on refresh?**
- Implements "refresh token rotation" (security best practice)
- Old refresh token becomes invalid (prevents reuse)
- Limits impact of refresh token theft

---

### Multi-Factor Authentication (Future)

**Phase 2+ Feature**: Email verification + TOTP (Authenticator app)

**Implementation Plan**:
1. Email verification:
   - Send verification code on registration
   - Mark is_verified=true after confirmation
   - Require verification before job creation

2. TOTP (Two-Factor Authentication):
   - Optional for users (not required)
   - Store TOTP secret in users table
   - Validate code on login
   - Backup codes for recovery

---

## Multi-Tenancy Pattern

### Row-Level Security (RLS) Pattern

**Design**: Soft multi-tenancy with tenant_id column on all resources

**Why tenant_id column instead of separate databases?**
- ✅ Simpler infrastructure (one database, not thousands)
- ✅ Easier backups and migrations
- ✅ Cost-effective (shared resources)
- ✅ Easier analytics (cross-tenant queries for admin dashboard)
- ❌ Trade-off: Less data isolation (must carefully filter queries)

**Tenant Isolation Enforcement**:

1. **Database Level**:
   - All tenant-owned tables have tenant_id column (UUID, FK → users.tenant_id)
   - All queries filter by tenant_id

2. **API Level**:
   - Dependency injection extracts tenant_id from JWT
   - All CRUD functions require tenant_id parameter
   - Example:
     ```python
     def get_multi(db, tenant_id: UUID, skip=0, limit=100):
         query = db.query(Job).filter(Job.tenant_id == tenant_id)
         return query.offset(skip).limit(limit).all()
     ```

3. **Application Level**:
   - All resources created with current user's tenant_id
   - Example:
     ```python
     job = Job(
         tenant_id=tenant_id,  # From JWT token
         title=request.title,
         description=request.description
     )
     ```

**Why tenant_id ≠ user.id?**
- Future-proofs for enterprise features
- Allows multiple users per tenant (team accounts)
- Example: Company with 5 recruiters sharing jobs/candidates

**Current State**: Phase 1 (one user per tenant)
**Future State**: Phase 2+ (N users per tenant)

---

### Tenant Isolation Testing

**Test Scenario**:
```python
# Create two users in different tenants
user_a = create_user(email="alice@company-a.com")
user_b = create_user(email="bob@company-b.com")

# Alice creates job
job_a = create_job(tenant_id=user_a.tenant_id, title="Secret Job A")

# Bob tries to access Alice's job
response = get_job(job_id=job_a.id, tenant_id=user_b.tenant_id)

# Expected: 404 Not Found (tenant isolation working)
assert response.status_code == 404
```

**Critical**: NEVER expose resources based on ID alone. Always filter by tenant_id.

---

## Data Processing Pipeline

### Async Task Architecture

**Why Asynchronous Processing?**
- ✅ Fast API response times (doesn't wait for AI)
- ✅ Resilience (retries on failures)
- ✅ Scalability (add more workers)
- ✅ User experience (real-time status updates)

**Task Flow**:

```
Upload Resume
    ↓
[API] Create Candidate record (status=UPLOADED)
    ↓
[API] Enqueue parse_resume_task → Redis
    ↓
[API] Return candidate_id to frontend
    ↓
[Worker] Pull task from Redis
    ↓
[Worker] Extract text from PDF/DOCX
    ↓
[Worker] Update status=PARSED
    ↓
[Worker] Auto-chain to score_candidate_task
    ↓
[Worker] Call GPT-4o API
    ↓
[Worker] Calculate weighted score (Python)
    ↓
[Worker] Create Evaluation record
    ↓
[Worker] Update Candidate contact fields
    ↓
[Worker] Update status=SCORED
    ↓
[Frontend] Poll GET /api/v1/candidates/{id} until status=SCORED
    ↓
[Frontend] Fetch analysis, display to user
```

**Why polling instead of WebSockets?**
- ✅ Simpler implementation (no persistent connections)
- ✅ Works with any frontend framework
- ✅ Easier load balancing
- ❌ Trade-off: Slightly higher latency (1-2 second poll interval)
- **Future**: Migrate to WebSockets or Server-Sent Events (SSE) in Phase 2

---

### Task Retry Strategy

**Celery Configuration**:
```python
@celery_app.task(
    bind=True,
    max_retries=3,
    default_retry_delay=60  # 1 minute
)
def score_candidate_task(self, candidate_id: int):
    try:
        # ... scoring logic
    except OpenAIError as e:
        # Retry on rate limit, timeout, or server errors
        raise self.retry(exc=e)
```

**Why 3 retries with 60-second delay?**
- Handles transient failures (OpenAI rate limits, network issues)
- 60-second delay allows rate limit windows to reset
- 3 retries balances reliability with timeliness (max 3 min delay)

**Failure Handling**:
- After 3 retries → update candidate.status = FAILED
- Store error message in candidate.error_message
- User sees "Processing failed" in UI with option to retry

---

### File Storage Design

**Current**: Local filesystem (`uploads/` directory)

**Why local filesystem for Phase 1?**
- ✅ Simple implementation (no cloud dependencies)
- ✅ Fast development iteration
- ✅ No additional costs
- ❌ Limitation: Blocks horizontal scaling (workers need access to same files)
- ❌ Limitation: No redundancy (files lost if container deleted)

**Phase 2 Migration to S3**:

**Benefits**:
- ✅ Horizontal scaling (stateless API servers)
- ✅ Redundancy (99.999999999% durability)
- ✅ CDN integration (CloudFront for faster downloads)
- ✅ Pre-signed URLs (direct upload from browser)
- ✅ Lifecycle policies (auto-delete old files)

**Implementation Plan**:
1. Update candidate upload endpoint to generate pre-signed S3 URLs
2. Frontend uploads directly to S3 (bypasses API)
3. Frontend sends S3 key to API
4. API creates Candidate record with S3 key
5. Worker pulls file from S3 for parsing

---

## AI Integration Strategy

### Hybrid AI + Python Architecture

**Design Philosophy**: "AI for judgment, Python for facts"

**AI Responsibilities**:
- Category grading (subjective: 0-100 scores)
- PII extraction (name, email, phone, location)
- URL extraction (LinkedIn, GitHub, Portfolio)
- Summary generation (2-paragraph overview)
- Pros/Cons generation (strengths and gaps)

**Python Responsibilities**:
- Weighted score calculation (arithmetic)
- Contact field updates (conditional logic)
- URL deduplication and sorting
- Database transactions

**Why not let AI calculate final score?**
- ❌ AI hallucinates arithmetic (e.g., 85*5 + 80*4 = 671 instead of 745)
- ❌ Inconsistent rounding (sometimes 82.5, sometimes 83)
- ❌ Hard to debug (can't trace how score was calculated)

**Hybrid Example**:
```python
# AI returns category scores
category_scores = {
    "Python": {"score": 85, "reasoning": "..."},
    "Databases": {"score": 80, "reasoning": "..."}
}

# Python calculates weighted average
importances = {"Python": 5, "Databases": 4}
total_weighted = 85*5 + 80*4  # 745
total_importance = 5 + 4       # 9
match_score = 745 / 9          # 82.78

# Store both in database
evaluation = Evaluation(
    category_scores=category_scores,  # AI output
    match_score=round(match_score, 2) # Python calculation
)
```

---

### OpenAI API Design Patterns

**Temperature**: 0.2 (low randomness for consistent output)

**Why 0.2 instead of 0 or 1?**
- 0: Too deterministic (robotic, repetitive summaries)
- 0.2: Slight variation (natural language, still consistent)
- 1: Too creative (inconsistent grading, hallucinations)

**JSON Mode**: Structured output for category scores

**Prompt Engineering**:
```python
system_prompt = """
You are an expert recruiter analyzing resumes.
Grade each category from 0-100 using this scale:
- 0-20: No evidence
- 21-50: Listed in skills, no project usage
- 51-75: Competent - used in projects
- 76-90: Strong - multiple projects, years of experience
- 91-100: Exceptional - lead architect, major achievements

Return JSON only. No additional text.
"""
```

**Why explicit grading scale?**
- Prevents AI from clustering scores (e.g., everything 70-80)
- Enforces use of full 0-100 range
- Consistent interpretation across resumes

**Token Optimization**:
- Resume text truncated to 25k characters (prevents excessive API costs)
- Job descriptions limited to 15k characters
- Minimal prompt (reduces input tokens)

---

### Error Handling & Fallbacks

**OpenAI API Errors**:

1. **Rate Limit (429)**:
   - Celery retry with exponential backoff
   - Max 3 retries
   - If still failing → mark candidate as FAILED

2. **Timeout**:
   - Retry with same logic
   - Timeout set to 60 seconds (generous for resume analysis)

3. **Invalid JSON Response**:
   - Log error
   - Retry task
   - If persistent → mark as FAILED with error message

4. **Content Filter Violation**:
   - Mark as FAILED
   - Error message: "Resume content violated content policy"
   - Rare (only if resume contains prohibited content)

**Future Enhancements**:
- Fallback to GPT-3.5 Turbo if GPT-4o fails (cheaper, faster)
- Caching of job configs (don't regenerate for same job description)
- Batch processing (score multiple candidates in one API call)

---

## Billing & Subscription Model

### Stripe Integration Architecture

**Why Stripe?**
- ✅ Industry-leading payment processing
- ✅ Webhooks for real-time subscription updates
- ✅ Metered billing support (Enterprise plan)
- ✅ Dunning management (automatic retry of failed payments)
- ✅ PCI compliance (Stripe handles card data)

**Subscription Lifecycle**:

```
User Registers
    ↓
[API] Create Subscription (plan=FREE, status=TRIALING)
    ↓
User Upgrades to STARTER via Stripe Checkout
    ↓
[Stripe] Sends customer.subscription.created webhook
    ↓
[API] Update subscription (plan=STARTER, status=ACTIVE, monthly_limit=100)
    ↓
[Stripe] Charges card on billing date
    ↓
[Stripe] Sends invoice.payment_succeeded webhook
    ↓
[API] Reset candidates_used_this_month = 0
    ↓
[Stripe] Payment fails next month
    ↓
[Stripe] Sends invoice.payment_failed webhook
    ↓
[API] Update status=PAST_DUE
    ↓
[User] Blocked from creating jobs/uploading candidates
    ↓
[User] Updates payment method
    ↓
[Stripe] Retries payment, succeeds
    ↓
[Stripe] Sends invoice.payment_succeeded webhook
    ↓
[API] Update status=ACTIVE
    ↓
[User] Access restored
```

---

### Usage Tracking Design

**Approach**: Application-level tracking (not Stripe reporting API)

**Why application-level?**
- ✅ Real-time enforcement (block uploads immediately when limit reached)
- ✅ No API latency (don't need to query Stripe on every upload)
- ✅ Simpler implementation (just increment counter)
- ❌ Trade-off: Counter could drift if webhook fails (mitigated by idempotent webhook handling)

**Counter Logic**:
```python
# On candidate upload
subscription.candidates_used_this_month += 1
db.commit()

# On monthly billing cycle (invoice.payment_succeeded webhook)
subscription.candidates_used_this_month = 0
db.commit()
```

**Why NOT decrement on deletion?**
- Prevents abuse (upload 100, delete 50, upload 50 more = 150 total)
- Aligns with usage-based billing (you used 100 credits, even if deleted)
- Simpler logic (no need to track deletions)

---

### Metered Billing (Enterprise Plan)

**Design**: $500 base + $0.50 per candidate

**Implementation**:
1. User on ENTERPRISE plan uploads candidate
2. API increments subscription.candidates_used_this_month
3. At end of billing period, Stripe webhook fires
4. API reports usage to Stripe via API:
   ```python
   stripe.SubscriptionItem.create_usage_record(
       subscription_item_id,
       quantity=subscription.candidates_used_this_month,
       timestamp=int(time.time())
   )
   ```
5. Stripe charges: $500 (base) + ($0.50 × quantity)

**Why metered billing for ENTERPRISE?**
- ✅ Aligns pricing with value (high-volume customers pay more)
- ✅ Removes arbitrary limit (unlimited candidates)
- ✅ Competitive with per-seat pricing (more flexible)

---

## Frontend Architecture

### Alpine.js Component Pattern

**Why component-based architecture?**
- ✅ Reusable logic (Auth.js shared across pages)
- ✅ Separation of concerns (UI state vs. business logic)
- ✅ Easier testing (can unit test Auth.js independently)

**Example Component** (static/auth.js):
```javascript
const Auth = {
  login(accessToken, refreshToken) { ... },
  logout() { ... },
  isAuthenticated() { ... },
  fetch(url, options) { ... },  // Auto-injects JWT, auto-refreshes on 401
  refreshAccessToken() { ... }
};
```

**Usage in Alpine.js**:
```javascript
function handleLogin() {
  Auth.fetch('/api/v1/auth/login', {
    method: 'POST',
    body: JSON.stringify({ username: this.email, password: this.password })
  })
  .then(response => response.json())
  .then(data => {
    Auth.login(data.access_token, data.refresh_token);
    window.location.href = '/';
  });
}
```

---

### Auto-Refresh Token Pattern

**Implementation**:
```javascript
Auth.fetch = async function(url, options = {}) {
  // Inject Authorization header
  options.headers = {
    ...options.headers,
    ...this.getAuthHeaders()
  };

  // Make request
  let response = await fetch(url, options);

  // If 401, refresh token and retry
  if (response.status === 401) {
    const refreshed = await this.refreshAccessToken();
    if (refreshed) {
      options.headers = {...options.headers, ...this.getAuthHeaders()};
      response = await fetch(url, options);  // Retry with new token
    } else {
      this.logout();  // Refresh failed, logout user
    }
  }

  return response;
};
```

**Why auto-refresh instead of manual?**
- ✅ Better UX (user doesn't notice token expiration)
- ✅ Less code duplication (one place handles refresh)
- ✅ Transparent to application code (just use Auth.fetch())

---

### Real-Time Status Updates

**Current**: Polling every 2 seconds

**Implementation**:
```javascript
function pollCandidateStatus(candidateId) {
  const interval = setInterval(() => {
    Auth.fetch(`/api/v1/candidates/${candidateId}`)
      .then(response => response.json())
      .then(data => {
        this.candidate.status = data.status;
        if (data.status === 'SCORED' || data.status === 'FAILED') {
          clearInterval(interval);  // Stop polling
          if (data.status === 'SCORED') {
            this.fetchAnalysis(candidateId);  // Load results
          }
        }
      });
  }, 2000);  // Poll every 2 seconds
}
```

**Why polling instead of WebSockets?**
- ✅ Simpler (no persistent connection management)
- ✅ Works with load balancers (no sticky sessions)
- ✅ Good enough for Phase 1 (sub-3-second latency acceptable)
- ❌ Trade-off: Slightly higher server load (more requests)

**Phase 2 Enhancement**: Server-Sent Events (SSE) or WebSockets
- Push updates to frontend when status changes
- Reduces server load (no polling)
- Real-time updates (sub-second latency)

---

## Database Design Decisions

### UUID vs. Auto-Incrementing IDs

**Users**: UUID (Universally Unique Identifier)
- ✅ Non-enumerable (can't guess other user IDs)
- ✅ Globally unique (safe for distributed systems)
- ✅ Secure (prevents user enumeration attacks)
- ❌ Slightly larger storage (16 bytes vs. 8 bytes for BIGINT)

**Jobs/Candidates/Evaluations**: SERIAL (Auto-Incrementing Integer)
- ✅ Smaller storage (4 bytes for INT)
- ✅ Better performance (faster indexes)
- ✅ Human-readable (easy to reference in support tickets)
- ❌ Enumerable (can guess IDs, mitigated by tenant_id filtering)

**Why different strategies?**
- Users need strong security (UUIDs prevent enumeration)
- Resources protected by tenant_id (enumeration doesn't matter)

---

### JSONB vs. Separate Tables

**JSONB Used For**:
- `job_config` (dynamic schema, varies by job)
- `category_scores` (dynamic categories, varies by job)
- `pros/cons` (simple arrays, no need for separate table)
- `other_urls` (variable-length arrays)

**Why JSONB?**
- ✅ Flexible schema (categories defined at runtime)
- ✅ Atomic updates (no need for transactions across tables)
- ✅ Simpler queries (one SELECT instead of JOIN)
- ✅ Faster writes (one INSERT instead of multiple)
- ❌ Trade-off: Can't enforce schema at database level
- ❌ Trade-off: Harder to index (can index specific keys, but not entire JSON)

**When NOT to use JSONB**:
- Fixed schema (e.g., User fields → use columns)
- Need to JOIN (e.g., subscriptions → separate table with FK)
- Need to enforce constraints (e.g., unique email → use column)

---

### Cascade Deletion Strategy

**Design**: Aggressive cascading (deleting user deletes all data)

**Cascade Rules**:
```
Delete User
  → Delete Subscription (FK: user_id)
  → Delete Jobs (FK: tenant_id)
    → Delete Candidates (FK: job_id, CASCADE)
      → Delete Evaluations (FK: candidate_id, CASCADE)
```

**Why aggressive cascading?**
- ✅ Data compliance (GDPR right to deletion)
- ✅ Simpler code (one DELETE, not dozens)
- ✅ Prevents orphaned records
- ❌ Trade-off: Accidental deletion destroys all data

**Protection**: Soft delete pattern (future enhancement)
- Add `deleted_at` timestamp to users
- Filter out deleted users in queries
- Permanently delete after 30 days (compliance window)

---

## Trade-offs & Future Improvements

### Current Limitations

| Limitation | Impact | Planned Fix (Phase) |
|-----------|--------|---------------------|
| Local file storage | Blocks horizontal scaling | S3 migration (Phase 2) |
| No rate limiting | Vulnerable to abuse | API rate limiting (Phase 2) |
| Polling for status | Higher server load | WebSockets/SSE (Phase 2) |
| No email verification | Spam accounts possible | Email verification (Phase 2) |
| No password reset | Poor UX if forgotten | Password reset flow (Phase 2) |
| localStorage tokens | Vulnerable to XSS | httpOnly cookies + CSP (Phase 2) |
| Tailwind CDN | Slower page loads | Self-host Tailwind (Phase 2) |
| No unit tests | Harder to refactor | pytest suite (Phase 2) |
| No monitoring | Blind to errors | Sentry + Prometheus (Phase 2) |

---

### Technical Debt

**Prioritized by Impact**:

1. **CRITICAL - S3 File Storage**:
   - Current: Blocks horizontal scaling
   - Timeline: Before production deployment
   - Effort: 2-3 days (S3 SDK, update upload/parse logic)

2. **HIGH - Email Verification**:
   - Current: Spam accounts can register
   - Timeline: Phase 2 (before public launch)
   - Effort: 1 day (SendGrid integration, verification flow)

3. **HIGH - Unit Tests**:
   - Current: Manual testing only, risky refactors
   - Timeline: Phase 2 (before adding features)
   - Effort: 1 week (pytest setup, test API endpoints + tasks)

4. **MEDIUM - Rate Limiting**:
   - Current: Vulnerable to DoS, API abuse
   - Timeline: Phase 2 (before scaling)
   - Effort: 1 day (SlowAPI middleware)

5. **MEDIUM - Monitoring**:
   - Current: No visibility into production errors
   - Timeline: Phase 2 (before production)
   - Effort: 1 day (Sentry integration)

6. **LOW - WebSockets**:
   - Current: Polling works, just inefficient
   - Timeline: Phase 3 (optimization phase)
   - Effort: 2 days (WebSocket endpoint, frontend refactor)

---

### Scalability Roadmap

**Phase 1 Capacity** (Current):
- ✅ 100 concurrent users
- ✅ 1,000 candidates/day
- ✅ Single-server deployment
- ❌ Bottleneck: Local file storage

**Phase 2 Capacity** (S3 + Load Balancer):
- ✅ 1,000 concurrent users
- ✅ 10,000 candidates/day
- ✅ Horizontal API scaling (2-3 servers)
- ✅ Horizontal worker scaling (5-10 workers)
- ❌ Bottleneck: Database (single PostgreSQL instance)

**Phase 3 Capacity** (Database Read Replicas):
- ✅ 10,000 concurrent users
- ✅ 100,000 candidates/day
- ✅ Read replicas for analytics queries
- ✅ Connection pooling (PgBouncer)
- ❌ Bottleneck: OpenAI API rate limits

**Phase 4 Capacity** (Microservices + Caching):
- ✅ 100,000+ concurrent users
- ✅ 1,000,000 candidates/day
- ✅ Separate services (API, Worker, Analytics)
- ✅ Redis caching (job configs, user sessions)
- ✅ CDN for static assets
- ✅ OpenAI API quota increases (enterprise contract)

---

*Last Updated: 2025-12-31*

*Phase: 1 Complete (Multi-tenant SaaS with JWT auth and billing)*
