# Starscreen Database Schema

> **LLM Context**: This document provides complete database schema documentation for the Starscreen resume screening platform. Use this for understanding table structures, relationships, constraints, indexes, and multi-tenancy implementation.

**Database**: PostgreSQL 15+

**ORM**: SQLAlchemy 2.0

**Migrations**: Alembic

**Connection String**: `postgresql://user:password@db:5432/talent_db` (Docker) or `postgresql://user:password@localhost:5432/talent_db` (local)

---

## Table of Contents

1. [Entity Relationship Diagram](#entity-relationship-diagram)
2. [Tables](#tables)
   - [users](#users-table)
   - [subscriptions](#subscriptions-table)
   - [jobs](#jobs-table)
   - [candidates](#candidates-table)
   - [evaluations](#evaluations-table)
3. [Enum Types](#enum-types)
4. [Indexes](#indexes)
5. [Foreign Key Relationships](#foreign-key-relationships)
6. [Multi-Tenancy Implementation](#multi-tenancy-implementation)
7. [Alembic Migrations](#alembic-migrations)
8. [Common Queries](#common-queries)

---

## Entity Relationship Diagram

```
┌─────────────────────┐
│      users          │
│  (Multi-tenancy     │
│   anchor)           │
├─────────────────────┤
│ id (PK, UUID)       │
│ tenant_id (UQ,UUID) │◄──────────┐
│ email (UQ)          │           │
│ hashed_password     │           │
│ full_name           │           │
│ company_name        │           │
│ is_active           │           │
│ is_verified         │           │
└─────────────────────┘           │
          │ 1                     │
          │                       │
          │                       │
          │ 1                     │
          ▼                       │
┌─────────────────────┐           │
│   subscriptions     │           │
├─────────────────────┤           │
│ id (PK, UUID)       │           │
│ user_id (FK, UQ)    │           │
│ stripe_customer_id  │           │
│ plan (ENUM)         │           │
│ status (ENUM)       │           │
│ monthly_limit       │           │
│ used_this_month     │           │
└─────────────────────┘           │
                                  │
┌─────────────────────┐           │
│       jobs          │           │
├─────────────────────┤           │
│ id (PK, SERIAL)     │           │
│ tenant_id (FK)      │───────────┤
│ title               │           │
│ description         │           │
│ status (ENUM)       │           │
│ job_config (JSONB)  │           │
└─────────────────────┘           │
          │ 1                     │
          │                       │
          │ N                     │
          ▼                       │
┌─────────────────────┐           │
│    candidates       │           │
├─────────────────────┤           │
│ id (PK, SERIAL)     │           │
│ tenant_id (FK)      │───────────┤
│ job_id (FK)         │           │
│ first_name          │           │
│ email               │           │
│ file_path           │           │
│ resume_text         │           │
│ status (ENUM)       │           │
└─────────────────────┘           │
          │ 1                     │
          │                       │
          │ 1 (optional)          │
          ▼                       │
┌─────────────────────┐           │
│   evaluations       │           │
├─────────────────────┤           │
│ id (PK, SERIAL)     │           │
│ tenant_id (FK)      │───────────┘
│ candidate_id(FK,UQ) │
│ match_score         │
│ category_scores     │
│ summary             │
│ pros (JSONB)        │
│ cons (JSONB)        │
└─────────────────────┘
```

**Key Design Principles**:
1. **Multi-Tenancy**: All tenant-owned resources have `tenant_id` column
2. **Cascade Deletion**: Deleting user → deletes all tenant data
3. **UUID for Users**: Prevents enumeration attacks
4. **SERIAL for Resources**: Auto-incrementing IDs for jobs/candidates/evaluations
5. **JSONB for Flexibility**: job_config, category_scores, pros/cons stored as JSON

---

## Tables

### users Table

**Purpose**: User accounts with authentication credentials

**SQLAlchemy Model**: `app/models/user.py`

| Column | Type | Constraints | Description |
|--------|------|-------------|-------------|
| `id` | UUID | PRIMARY KEY | User's unique identifier |
| `tenant_id` | UUID | UNIQUE, NOT NULL, INDEX | Multi-tenancy isolation key |
| `email` | VARCHAR | UNIQUE, NOT NULL, INDEX | User's email (login username) |
| `hashed_password` | VARCHAR | NOT NULL | Bcrypt-hashed password (72-byte limit) |
| `full_name` | VARCHAR | NULLABLE | User's display name |
| `company_name` | VARCHAR | NULLABLE | Organization name |
| `is_active` | BOOLEAN | NOT NULL, DEFAULT TRUE | Account active status |
| `is_verified` | BOOLEAN | NOT NULL, DEFAULT FALSE | Email verification status |
| `created_at` | TIMESTAMPTZ | NOT NULL, DEFAULT NOW() | Registration timestamp |
| `updated_at` | TIMESTAMPTZ | NULLABLE | Last update timestamp |
| `last_login_at` | TIMESTAMPTZ | NULLABLE | Last successful login |

**Indexes**:
- `ix_users_id` (PRIMARY KEY, auto-created)
- `ix_users_tenant_id` (UNIQUE)
- `ix_users_email` (UNIQUE)

**Relationships**:
- One-to-One: `subscription` (users.id → subscriptions.user_id)
- One-to-Many: `jobs` (users.tenant_id → jobs.tenant_id)
- One-to-Many: `candidates` (users.tenant_id → candidates.tenant_id)
- One-to-Many: `evaluations` (users.tenant_id → evaluations.tenant_id)

**Python Model**:
```python
from sqlalchemy import Column, String, Boolean, DateTime, func
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship

class User(Base):
    __tablename__ = "users"

    id = Column(UUID(as_uuid=True), primary_key=True, index=True)
    tenant_id = Column(UUID(as_uuid=True), unique=True, nullable=False, index=True)
    email = Column(String, unique=True, nullable=False, index=True)
    hashed_password = Column(String, nullable=False)
    full_name = Column(String, nullable=True)
    company_name = Column(String, nullable=True)
    is_active = Column(Boolean, default=True, nullable=False)
    is_verified = Column(Boolean, default=False, nullable=False)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())
    last_login_at = Column(DateTime(timezone=True), nullable=True)

    # Relationships
    subscription = relationship("Subscription", back_populates="user", uselist=False)
```

**Important Notes**:
- `tenant_id` is generated as a separate UUID (NOT equal to user.id)
- This allows future enterprise features where multiple users share a tenant
- Password is hashed with bcrypt (72-byte UTF-8 limit enforced in app/core/security.py)

---

### subscriptions Table

**Purpose**: Stripe billing and usage tracking

**SQLAlchemy Model**: `app/models/subscription.py`

| Column | Type | Constraints | Description |
|--------|------|-------------|-------------|
| `id` | UUID | PRIMARY KEY | Subscription record ID |
| `user_id` | UUID | FOREIGN KEY → users.id, UNIQUE, NOT NULL | Owner of subscription |
| `stripe_customer_id` | VARCHAR | UNIQUE, NULLABLE, INDEX | Stripe customer ID |
| `stripe_subscription_id` | VARCHAR | UNIQUE, NULLABLE, INDEX | Stripe subscription ID |
| `plan` | subscriptionplan | NOT NULL, DEFAULT 'free' | Current pricing tier (enum) |
| `status` | subscriptionstatus | NOT NULL, DEFAULT 'trialing', INDEX | Subscription lifecycle state (enum) |
| `monthly_candidate_limit` | INTEGER | NOT NULL, DEFAULT 5 | Max candidates per billing period |
| `candidates_used_this_month` | INTEGER | NOT NULL, DEFAULT 0 | Current usage counter |
| `current_period_start` | TIMESTAMPTZ | NULLABLE | Billing period start |
| `current_period_end` | TIMESTAMPTZ | NULLABLE | Billing period end |
| `created_at` | TIMESTAMPTZ | NOT NULL, DEFAULT NOW() | Subscription creation |
| `updated_at` | TIMESTAMPTZ | NULLABLE | Last update |

**Indexes**:
- `ix_subscriptions_id` (PRIMARY KEY)
- `ix_subscriptions_user_id` (UNIQUE, FOREIGN KEY)
- `ix_subscriptions_stripe_customer_id` (UNIQUE)
- `ix_subscriptions_stripe_subscription_id` (UNIQUE)
- `ix_subscriptions_status` (for billing queries)

**Relationships**:
- Many-to-One: `user` (subscriptions.user_id → users.id)

**Python Model**:
```python
from sqlalchemy import Column, String, Integer, DateTime, Enum, ForeignKey, func
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship

class Subscription(Base):
    __tablename__ = "subscriptions"

    id = Column(UUID(as_uuid=True), primary_key=True, index=True)
    user_id = Column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=False, unique=True, index=True)

    stripe_customer_id = Column(String, nullable=True, unique=True, index=True)
    stripe_subscription_id = Column(String, nullable=True, unique=True, index=True)

    plan = Column(
        Enum(SubscriptionPlan, values_callable=lambda x: [e.value for e in x]),
        default=SubscriptionPlan.FREE,
        nullable=False
    )
    status = Column(
        Enum(SubscriptionStatus, values_callable=lambda x: [e.value for e in x]),
        default=SubscriptionStatus.TRIALING,
        nullable=False,
        index=True
    )

    monthly_candidate_limit = Column(Integer, default=5, nullable=False)
    candidates_used_this_month = Column(Integer, default=0, nullable=False)

    current_period_start = Column(DateTime(timezone=True), nullable=True)
    current_period_end = Column(DateTime(timezone=True), nullable=True)

    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())

    # Relationships
    user = relationship("User", back_populates="subscription")
```

**Computed Properties** (Python, not SQL):
```python
@property
def is_active(self) -> bool:
    """Check if subscription allows access."""
    return self.status in [SubscriptionStatus.ACTIVE, SubscriptionStatus.TRIALING]

@property
def can_upload_candidate(self) -> bool:
    """Check if user can upload another candidate."""
    if self.plan == SubscriptionPlan.ENTERPRISE:
        return True  # Unlimited
    return self.is_active and self.candidates_used_this_month < self.monthly_candidate_limit

@property
def remaining_candidates(self) -> int:
    """Get remaining candidates this month."""
    return max(0, self.monthly_candidate_limit - self.candidates_used_this_month)
```

**Important Notes**:
- One subscription per user (enforced by UNIQUE constraint on user_id)
- FREE tier subscriptions have NULL Stripe IDs
- Usage counter is incremented on candidate upload, NOT decremented on deletion
- Monthly reset happens via Stripe webhook (invoice.payment_succeeded)

---

### jobs Table

**Purpose**: Job postings with AI-generated scoring rubrics

**SQLAlchemy Model**: `app/models/job.py`

| Column | Type | Constraints | Description |
|--------|------|-------------|-------------|
| `id` | SERIAL | PRIMARY KEY | Job's auto-incrementing ID |
| `tenant_id` | UUID | FOREIGN KEY → users.tenant_id, NOT NULL, INDEX | Owner of this job |
| `title` | VARCHAR(200) | NOT NULL | Job title |
| `description` | TEXT | NOT NULL | Job description (max 15k chars enforced in app) |
| `location` | VARCHAR(200) | NULLABLE | Job location |
| `work_authorization_required` | BOOLEAN | NOT NULL, DEFAULT FALSE | Authorization requirement |
| `status` | VARCHAR(20) | NOT NULL, DEFAULT 'PENDING' | Processing state |
| `job_config` | JSONB | NULLABLE | AI-generated scoring rubric |
| `error_message` | TEXT | NULLABLE | Error if config generation failed |
| `created_at` | TIMESTAMPTZ | NOT NULL, DEFAULT NOW() | Job creation timestamp |
| `updated_at` | TIMESTAMPTZ | NULLABLE | Last update timestamp |

**Indexes**:
- `ix_jobs_id` (PRIMARY KEY)
- `ix_jobs_tenant_id` (FOREIGN KEY, for multi-tenancy filtering)

**Relationships**:
- Many-to-One: `user` (jobs.tenant_id → users.tenant_id)
- One-to-Many: `candidates` (jobs.id → candidates.job_id)

**job_config JSONB Structure**:
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
      "keywords": ["postgresql", "sql", "orm"]
    }
  ]
}
```

**Status Values** (VARCHAR, not enum):
- `PENDING`: Job created, config generation queued
- `PROCESSING`: Celery worker generating config
- `COMPLETED`: Config generated successfully
- `FAILED`: Config generation failed (see error_message)

**Python Model**:
```python
from sqlalchemy import Column, Integer, String, Text, Boolean, DateTime, ForeignKey, func
from sqlalchemy.dialects.postgresql import UUID, JSONB
from sqlalchemy.orm import relationship

class Job(Base):
    __tablename__ = "jobs"

    id = Column(Integer, primary_key=True, index=True)
    tenant_id = Column(UUID(as_uuid=True), ForeignKey("users.tenant_id"), nullable=False, index=True)

    title = Column(String(200), nullable=False)
    description = Column(Text, nullable=False)
    location = Column(String(200), nullable=True)
    work_authorization_required = Column(Boolean, default=False, nullable=False)

    status = Column(String(20), default="PENDING", nullable=False)
    job_config = Column(JSONB, nullable=True)
    error_message = Column(Text, nullable=True)

    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())

    # Relationships
    candidates = relationship("Candidate", back_populates="job", cascade="all, delete-orphan")
```

**Cascade Deletion**:
- Deleting job → deletes all candidates (via SQLAlchemy cascade)
- Deleting candidates → deletes evaluations (via SQLAlchemy cascade)

---

### candidates Table

**Purpose**: Resume data and contact information

**SQLAlchemy Model**: `app/models/candidate.py`

| Column | Type | Constraints | Description |
|--------|------|-------------|-------------|
| `id` | SERIAL | PRIMARY KEY | Candidate's auto-incrementing ID |
| `tenant_id` | UUID | FOREIGN KEY → users.tenant_id, NOT NULL, INDEX | Owner of this candidate |
| `job_id` | INTEGER | FOREIGN KEY → jobs.id, NOT NULL | Associated job posting |
| `first_name` | VARCHAR(100) | NULLABLE | Extracted by AI or manually entered |
| `last_name` | VARCHAR(100) | NULLABLE | Extracted by AI or manually entered |
| `email` | VARCHAR | NULLABLE | Extracted by AI or manually entered |
| `phone` | VARCHAR(50) | NULLABLE | Extracted by AI or manually entered |
| `location` | VARCHAR(200) | NULLABLE | Extracted by AI or manually entered |
| `linkedin_url` | VARCHAR | NULLABLE | Extracted by AI |
| `github_url` | VARCHAR | NULLABLE | Extracted by AI |
| `portfolio_url` | VARCHAR | NULLABLE | Extracted by AI |
| `other_urls` | JSONB | NULLABLE, DEFAULT '[]' | Additional URLs (JSONB array) |
| `file_path` | VARCHAR | NOT NULL | Local filesystem path to resume |
| `original_filename` | VARCHAR | NOT NULL | Original uploaded filename |
| `resume_text` | TEXT | NOT NULL | Extracted resume text (max 25k chars) |
| `anonymized_text` | TEXT | NULLABLE | Reserved for blind screening |
| `status` | VARCHAR(20) | NOT NULL, DEFAULT 'UPLOADED' | Processing state |
| `error_message` | TEXT | NULLABLE | Error if parsing/scoring failed |
| `created_at` | TIMESTAMPTZ | NOT NULL, DEFAULT NOW() | Upload timestamp |
| `updated_at` | TIMESTAMPTZ | NULLABLE | Last update timestamp |

**Indexes**:
- `ix_candidates_id` (PRIMARY KEY)
- `ix_candidates_tenant_id` (FOREIGN KEY, for multi-tenancy filtering)
- `ix_candidates_job_id` (FOREIGN KEY, for filtering by job)

**Relationships**:
- Many-to-One: `job` (candidates.job_id → jobs.id)
- One-to-One: `evaluation` (candidates.id → evaluations.candidate_id)

**other_urls JSONB Structure**:
```json
["https://twitter.com/username", "https://medium.com/@username"]
```

**Status Values** (VARCHAR, not enum):
- `UPLOADED`: File uploaded, parsing queued
- `PROCESSING`: Celery worker parsing resume
- `PARSED`: Text extracted, scoring queued
- `SCORED`: Evaluation complete
- `FAILED`: Parsing or scoring failed (see error_message)

**Python Model**:
```python
from sqlalchemy import Column, Integer, String, Text, DateTime, ForeignKey, func
from sqlalchemy.dialects.postgresql import UUID, JSONB
from sqlalchemy.orm import relationship

class Candidate(Base):
    __tablename__ = "candidates"

    id = Column(Integer, primary_key=True, index=True)
    tenant_id = Column(UUID(as_uuid=True), ForeignKey("users.tenant_id"), nullable=False, index=True)
    job_id = Column(Integer, ForeignKey("jobs.id", ondelete="CASCADE"), nullable=False, index=True)

    # Contact fields (nullable for blind screening)
    first_name = Column(String(100), nullable=True)
    last_name = Column(String(100), nullable=True)
    email = Column(String, nullable=True)
    phone = Column(String(50), nullable=True)
    location = Column(String(200), nullable=True)

    # URLs
    linkedin_url = Column(String, nullable=True)
    github_url = Column(String, nullable=True)
    portfolio_url = Column(String, nullable=True)
    other_urls = Column(JSONB, nullable=True, default=[])

    # File and text
    file_path = Column(String, nullable=False)
    original_filename = Column(String, nullable=False)
    resume_text = Column(Text, nullable=False)
    anonymized_text = Column(Text, nullable=True)

    # Processing
    status = Column(String(20), default="UPLOADED", nullable=False)
    error_message = Column(Text, nullable=True)

    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())

    # Relationships
    job = relationship("Job", back_populates="candidates")
    evaluation = relationship("Evaluation", back_populates="candidate", uselist=False, cascade="all, delete-orphan")
```

**Contact Field Update Logic** (app/tasks/scoring_tasks.py):
```python
# Only update if AI found the field AND field is currently NULL
if contact_info.get("email") and not candidate.email:
    candidate.email = contact_info.get("email")
```

**Important Notes**:
- All contact fields are nullable (supports blind screening)
- AI extracts PII opportunistically (doesn't fail if missing)
- Files stored in `uploads/` directory (local filesystem)
- Future: Migrate to S3 for horizontal scaling

---

### evaluations Table

**Purpose**: AI-generated candidate assessments

**SQLAlchemy Model**: `app/models/evaluation.py`

| Column | Type | Constraints | Description |
|--------|------|-------------|-------------|
| `id` | SERIAL | PRIMARY KEY | Evaluation's auto-incrementing ID |
| `tenant_id` | UUID | FOREIGN KEY → users.tenant_id, NOT NULL, INDEX | Owner of this evaluation |
| `candidate_id` | INTEGER | FOREIGN KEY → candidates.id, UNIQUE, NOT NULL | Evaluated candidate |
| `match_score` | NUMERIC(5,2) | NOT NULL | Python-calculated weighted score (0-100) |
| `category_scores` | JSONB | NOT NULL | AI-generated category breakdowns |
| `summary` | TEXT | NOT NULL | AI-generated executive summary |
| `pros` | JSONB | NOT NULL | Strengths (JSONB array) |
| `cons` | JSONB | NOT NULL | Gaps/weaknesses (JSONB array) |
| `created_at` | TIMESTAMPTZ | NOT NULL, DEFAULT NOW() | Evaluation timestamp |

**Indexes**:
- `ix_evaluations_id` (PRIMARY KEY)
- `ix_evaluations_tenant_id` (FOREIGN KEY, for multi-tenancy filtering)
- `ix_evaluations_candidate_id` (UNIQUE, FOREIGN KEY)

**Relationships**:
- One-to-One: `candidate` (evaluations.candidate_id → candidates.id)

**category_scores JSONB Structure**:
```json
{
  "Python": {
    "score": 85,
    "reasoning": "Strong Python experience with FastAPI and Django. 6+ years in production."
  },
  "Databases": {
    "score": 80,
    "reasoning": "PostgreSQL expertise evident in multiple projects."
  }
}
```

**pros JSONB Structure**:
```json
[
  "6+ years of Python development",
  "FastAPI and Django expertise",
  "Strong system design skills"
]
```

**cons JSONB Structure**:
```json
[
  "Limited AWS experience",
  "No Kubernetes mentioned"
]
```

**Python Model**:
```python
from sqlalchemy import Column, Integer, Text, Numeric, DateTime, ForeignKey, func
from sqlalchemy.dialects.postgresql import UUID, JSONB
from sqlalchemy.orm import relationship

class Evaluation(Base):
    __tablename__ = "evaluations"

    id = Column(Integer, primary_key=True, index=True)
    tenant_id = Column(UUID(as_uuid=True), ForeignKey("users.tenant_id"), nullable=False, index=True)
    candidate_id = Column(Integer, ForeignKey("candidates.id", ondelete="CASCADE"), unique=True, nullable=False, index=True)

    match_score = Column(Numeric(5, 2), nullable=False)  # 0.00 to 100.00
    category_scores = Column(JSONB, nullable=False)
    summary = Column(Text, nullable=False)
    pros = Column(JSONB, nullable=False)
    cons = Column(JSONB, nullable=False)

    created_at = Column(DateTime(timezone=True), server_default=func.now())

    # Relationships
    candidate = relationship("Candidate", back_populates="evaluation")
```

**Score Calculation** (Python, NOT AI):
```python
# Prevents AI arithmetic hallucinations
total_weighted = sum(
    category_scores[cat]["score"] * job_config["categories"][i]["importance"]
    for i, cat in enumerate(category_scores.keys())
)
total_importance = sum(cat["importance"] for cat in job_config["categories"])
match_score = total_weighted / total_importance
```

**Important Notes**:
- One evaluation per candidate (enforced by UNIQUE constraint)
- Match score calculated by Python, not AI (prevents hallucinations)
- Evaluation is idempotent (deletes old evaluation before creating new one)

---

## Enum Types

PostgreSQL custom enum types created by Alembic migrations.

### subscriptionplan Enum

**Values**: `'free'`, `'recruiter'`, `'small_business'`, `'professional'`, `'enterprise'`

**SQL Definition**:
```sql
CREATE TYPE subscriptionplan AS ENUM (
    'free',
    'recruiter',
    'small_business',
    'professional',
    'enterprise'
);
```

**Python Enum** (app/models/subscription.py):
```python
class SubscriptionPlan(str, enum.Enum):
    FREE = "free"
    RECRUITER = "recruiter"
    SMALL_BUSINESS = "small_business"
    PROFESSIONAL = "professional"
    ENTERPRISE = "enterprise"
```

**SQLAlchemy Column Usage**:
```python
plan = Column(
    Enum(SubscriptionPlan, values_callable=lambda x: [e.value for e in x]),
    default=SubscriptionPlan.FREE,
    nullable=False
)
```

**CRITICAL**: Use `values_callable=lambda x: [e.value for e in x]` to ensure SQLAlchemy uses lowercase enum **values** instead of uppercase Python **names**.

---

### subscriptionstatus Enum

**Values**: `'trialing'`, `'active'`, `'past_due'`, `'canceled'`, `'unpaid'`

**SQL Definition**:
```sql
CREATE TYPE subscriptionstatus AS ENUM (
    'trialing',
    'active',
    'past_due',
    'canceled',
    'unpaid'
);
```

**Python Enum** (app/models/subscription.py):
```python
class SubscriptionStatus(str, enum.Enum):
    TRIALING = "trialing"  # Free trial period
    ACTIVE = "active"      # Paid and in good standing
    PAST_DUE = "past_due"  # Payment failed, grace period
    CANCELED = "canceled"  # User canceled, access until period_end
    UNPAID = "unpaid"      # Payment failed multiple times, revoked
```

**Lifecycle**:
```
TRIALING (new user) → ACTIVE (payment succeeds)
                   ↓
              PAST_DUE (payment fails)
                   ↓
              UNPAID (multiple failures)

ACTIVE → CANCELED (user cancels, access until period_end)
```

---

## Indexes

### Explicit Indexes

| Table | Column | Type | Purpose |
|-------|--------|------|---------|
| users | id | PRIMARY KEY | Unique user lookup |
| users | tenant_id | UNIQUE | Multi-tenancy isolation |
| users | email | UNIQUE | Login lookup |
| subscriptions | id | PRIMARY KEY | Unique subscription lookup |
| subscriptions | user_id | UNIQUE, FOREIGN KEY | One subscription per user |
| subscriptions | stripe_customer_id | UNIQUE | Stripe webhook lookups |
| subscriptions | stripe_subscription_id | UNIQUE | Stripe webhook lookups |
| subscriptions | status | INDEX | Billing queries (active users) |
| jobs | id | PRIMARY KEY | Unique job lookup |
| jobs | tenant_id | FOREIGN KEY, INDEX | Tenant isolation filtering |
| candidates | id | PRIMARY KEY | Unique candidate lookup |
| candidates | tenant_id | FOREIGN KEY, INDEX | Tenant isolation filtering |
| candidates | job_id | FOREIGN KEY, INDEX | Job's candidates query |
| evaluations | id | PRIMARY KEY | Unique evaluation lookup |
| evaluations | tenant_id | FOREIGN KEY, INDEX | Tenant isolation filtering |
| evaluations | candidate_id | UNIQUE, FOREIGN KEY | One evaluation per candidate |

### Missing Indexes (Potential Performance Improvements)

**Candidates**:
- `status` - Frequent filtering by processing state
- `created_at` - Sorting by upload date

**Jobs**:
- `status` - Filtering by processing state
- `created_at` - Sorting by creation date

**Users**:
- `created_at` - Analytics queries

---

## Foreign Key Relationships

### Cascade Deletion Rules

**User Deletion** (CASCADE ALL):
```
Delete User
  ↓
Delete Subscription (via user_id FK)
  ↓
Delete Jobs (via tenant_id FK)
  ↓
Delete Candidates (via job_id FK CASCADE)
  ↓
Delete Evaluations (via candidate_id FK CASCADE)
```

**Job Deletion** (CASCADE):
```
Delete Job
  ↓
Delete Candidates (via job_id FK, ondelete="CASCADE")
  ↓
Delete Evaluations (via candidate_id FK CASCADE in SQLAlchemy)
```

**Candidate Deletion** (CASCADE):
```
Delete Candidate
  ↓
Delete Evaluation (via candidate_id FK, SQLAlchemy cascade="all, delete-orphan")
```

### Foreign Key Definitions

**subscriptions → users**:
```python
user_id = Column(UUID, ForeignKey("users.id"), nullable=False, unique=True)
```

**jobs → users** (via tenant_id):
```python
tenant_id = Column(UUID, ForeignKey("users.tenant_id"), nullable=False)
```

**candidates → jobs**:
```python
job_id = Column(Integer, ForeignKey("jobs.id", ondelete="CASCADE"), nullable=False)
```

**candidates → users** (via tenant_id):
```python
tenant_id = Column(UUID, ForeignKey("users.tenant_id"), nullable=False)
```

**evaluations → candidates**:
```python
candidate_id = Column(Integer, ForeignKey("candidates.id", ondelete="CASCADE"), unique=True, nullable=False)
```

**evaluations → users** (via tenant_id):
```python
tenant_id = Column(UUID, ForeignKey("users.tenant_id"), nullable=False)
```

---

## Multi-Tenancy Implementation

### Row-Level Security Pattern

**Tenant Anchor**: `users.tenant_id` (UUID, UNIQUE)

**Propagation**:
1. User registers → `users.tenant_id` generated (UUID v4)
2. Jobs created → `jobs.tenant_id = current_user.tenant_id`
3. Candidates uploaded → `candidates.tenant_id = current_user.tenant_id`
4. Evaluations created → `evaluations.tenant_id = current_user.tenant_id`

**Query Filtering** (app/crud/job.py example):
```python
def get_multi(db: Session, tenant_id: UUID, skip: int = 0, limit: int = 100):
    query = db.query(Job).filter(Job.tenant_id == tenant_id)
    return query.offset(skip).limit(limit).all()
```

**Dependency Injection** (app/api/deps.py):
```python
def get_tenant_id(token: str = Depends(oauth2_scheme)) -> UUID:
    """Extract tenant_id from JWT token."""
    payload = decode_token(token)
    tenant_id = payload.get("tenant_id")
    if not tenant_id:
        raise HTTPException(status_code=401, detail="Invalid token")
    return UUID(tenant_id)
```

**Endpoint Usage**:
```python
@router.get("/jobs/")
def list_jobs(
    db: Session = Depends(get_db),
    tenant_id: UUID = Depends(get_tenant_id),
    skip: int = 0,
    limit: int = 100
):
    jobs = crud.job.get_multi(db, tenant_id=tenant_id, skip=skip, limit=limit)
    return jobs
```

### Why tenant_id ≠ user.id

**Current Design**: `users.id` (UUID) ≠ `users.tenant_id` (UUID)

**Rationale**:
- Future enterprise feature: Multiple users per tenant
- Example: Company account with 5 recruiters sharing jobs/candidates
- All users would have same `tenant_id` but different `user.id`

**Current State**: Phase 1 (one user per tenant, 1:1 mapping)

**Future State**: Phase 2+ (many users per tenant, N:1 mapping)

---

## Alembic Migrations

### Migration Commands

**Run Migrations**:
```bash
docker-compose exec api alembic upgrade head
```

**Create Migration**:
```bash
docker-compose exec api alembic revision --autogenerate -m "Description"
```

**Rollback Migration**:
```bash
docker-compose exec api alembic downgrade -1
```

**View Migration History**:
```bash
docker-compose exec api alembic history
```

**Check Current Version**:
```bash
docker-compose exec api alembic current
```

### Migration Files

Located in `alembic/versions/`

**Recent Migrations**:
1. `7c0d41691735_add_small_business_plan.py` - Added `small_business` to subscriptionplan enum
2. (Other migrations from Phase 1 implementation)

### Enum Migration Pattern

**Adding Enum Value** (PostgreSQL 9.1+):
```python
def upgrade() -> None:
    op.execute("ALTER TYPE subscriptionplan ADD VALUE IF NOT EXISTS 'small_business'")

def downgrade() -> None:
    # PostgreSQL doesn't support removing enum values
    # Update records to fallback value
    op.execute("""
        UPDATE subscriptions
        SET plan = 'professional'
        WHERE plan = 'small_business'
    """)
```

**Note**: PostgreSQL does NOT support removing enum values. Full enum recreation requires:
1. Create new enum type
2. Alter table to use new type
3. Drop old enum type

---

## Common Queries

### Get User with Subscription

```sql
SELECT u.*, s.*
FROM users u
LEFT JOIN subscriptions s ON s.user_id = u.id
WHERE u.email = 'user@example.com';
```

### Get Jobs with Candidate Count

```sql
SELECT j.id, j.title, COUNT(c.id) as candidate_count
FROM jobs j
LEFT JOIN candidates c ON c.job_id = j.id
WHERE j.tenant_id = '987fcdeb-51a2-43d7-8c9f-123456789abc'
GROUP BY j.id, j.title;
```

### Get Top Candidates for Job

```sql
SELECT c.id, c.first_name, c.last_name, e.match_score
FROM candidates c
INNER JOIN evaluations e ON e.candidate_id = c.id
WHERE c.job_id = 1
  AND c.tenant_id = '987fcdeb-51a2-43d7-8c9f-123456789abc'
ORDER BY e.match_score DESC
LIMIT 10;
```

### Get Active Subscriptions with Usage

```sql
SELECT u.email, s.plan, s.status,
       s.candidates_used_this_month,
       s.monthly_candidate_limit,
       (s.candidates_used_this_month::float / s.monthly_candidate_limit * 100) as usage_pct
FROM subscriptions s
INNER JOIN users u ON u.id = s.user_id
WHERE s.status IN ('active', 'trialing')
ORDER BY usage_pct DESC;
```

### Find Jobs with Failed Config Generation

```sql
SELECT j.id, j.title, j.error_message, j.created_at
FROM jobs j
WHERE j.status = 'FAILED'
  AND j.tenant_id = '987fcdeb-51a2-43d7-8c9f-123456789abc'
ORDER BY j.created_at DESC;
```

### Get Candidates Stuck in Processing

```sql
SELECT c.id, c.original_filename, c.status, c.created_at
FROM candidates c
WHERE c.status IN ('UPLOADED', 'PROCESSING', 'PARSED')
  AND c.created_at < NOW() - INTERVAL '10 minutes'
  AND c.tenant_id = '987fcdeb-51a2-43d7-8c9f-123456789abc';
```

---

## Database Connection

### Docker Environment

**Connection String**:
```
postgresql://user:password@db:5432/talent_db
```

**Components**:
- Host: `db` (Docker Compose service name)
- User: `user`
- Password: `password`
- Database: `talent_db`
- Port: 5432

### Local Development

**Connection String**:
```
postgresql://user:password@localhost:5432/talent_db
```

**Port Mapping**: Add to docker-compose.yml if needed:
```yaml
services:
  db:
    ports:
      - "5432:5432"
```

### psql Access

```bash
# From host (if port mapped)
psql postgresql://user:password@localhost:5432/talent_db

# From Docker container
docker-compose exec db psql -U user -d talent_db
```

### Useful psql Commands

```sql
-- List tables
\dt

-- Describe table
\d users

-- List enum types
\dT+

-- Show enum values
\dT+ subscriptionplan

-- List indexes
\di

-- Show table relationships
\d+ candidates
```

---

*Last Updated: 2025-12-31*

*PostgreSQL Version: 15+*

*SQLAlchemy Version: 2.0*
