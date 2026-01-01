# Starscreen Deployment & Troubleshooting Guide

> **LLM Context**: This document provides complete deployment instructions, troubleshooting procedures, and operational guidance for the Starscreen resume screening platform. Use this for understanding Docker setup, debugging production issues, and maintaining the system.

**Environment**: Docker Compose (development) → Kubernetes (production, Phase 2)

**Services**: PostgreSQL, Redis, FastAPI, Celery Worker

---

## Table of Contents

1. [Local Development Setup](#local-development-setup)
2. [Docker Operations](#docker-operations)
3. [Database Management](#database-management)
4. [Celery Worker Management](#celery-worker-management)
5. [Common Issues & Solutions](#common-issues--solutions)
6. [Debugging Guide](#debugging-guide)
7. [Production Deployment](#production-deployment-phase-2)
8. [Monitoring & Logging](#monitoring--logging)
9. [Backup & Recovery](#backup--recovery)

---

## Local Development Setup

### Prerequisites

**Required Software**:
- Docker Desktop 20.10+ (Windows/Mac) or Docker Engine + Docker Compose (Linux)
- Git
- Text editor (VS Code recommended)

**System Requirements**:
- 4GB RAM minimum (8GB recommended)
- 10GB disk space
- Internet connection (for pulling Docker images)

---

### Initial Setup

#### 1. Clone Repository

```bash
git clone <repository-url>
cd Resume-Analyzer
```

#### 2. Create Environment File

Create `.env` file in project root:

```bash
# AI API Settings
OPENAI_API_KEY=sk-proj-YOUR_KEY_HERE
OPENAI_MODEL=gpt-4o
OPENAI_TEMPERATURE=0.2

# Authentication Settings
SECRET_KEY=YOUR_SECRET_KEY_HERE  # Generate with: openssl rand -hex 32
ALGORITHM=HS256
ACCESS_TOKEN_EXPIRE_MINUTES=30
REFRESH_TOKEN_EXPIRE_DAYS=7

# Stripe Billing Settings (optional for development)
STRIPE_API_KEY=sk_test_YOUR_KEY_HERE
STRIPE_WEBHOOK_SECRET=whsec_YOUR_SECRET_HERE

# Stripe Products
STRIPE_PRICE_ID_STARTER=price_...
STRIPE_PRICE_ID_SMALL_BUSINESS=price_...
STRIPE_PRICE_ID_PROFESSIONAL=price_...
STRIPE_PRICE_ID_ENTERPRISE_BASE=price_...
STRIPE_PRICE_ID_ENTERPRISE_USAGE=price_...
```

**Generate SECRET_KEY**:
```bash
# Linux/Mac
openssl rand -hex 32

# Windows (PowerShell)
$bytes = New-Object Byte[] 32; [Security.Cryptography.RNGCryptoServiceProvider]::Create().GetBytes($bytes); [BitConverter]::ToString($bytes).Replace("-","").ToLower()
```

**Note**: Database and Redis configs are in `docker-compose.yml`, no need to add to `.env`.

#### 3. Start Services

```bash
# Start all services in background
docker-compose up -d

# View startup logs
docker-compose logs -f
```

**Expected Output**:
```
Creating network "resume-analyzer_default" with the default driver
Creating resume-analyzer_db_1    ... done
Creating resume-analyzer_redis_1 ... done
Creating resume-analyzer_api_1   ... done
Creating resume-analyzer_worker_1 ... done
```

#### 4. Run Database Migrations

```bash
docker-compose exec api alembic upgrade head
```

**Expected Output**:
```
INFO  [alembic.runtime.migration] Running upgrade  -> 7c0d41691735, add_small_business_plan
```

#### 5. Verify Setup

**Check API Health**:
```bash
curl http://localhost:8000/docs
```

Should return Swagger UI HTML.

**Check Services**:
```bash
docker-compose ps
```

Expected output:
```
Name                          State    Ports
------------------------------------------------------
resume-analyzer_api_1         Up       0.0.0.0:8000->8000/tcp
resume-analyzer_db_1          Up       5432/tcp
resume-analyzer_redis_1       Up       6379/tcp
resume-analyzer_worker_1      Up
```

**Test Registration**:
```bash
curl -X POST http://localhost:8000/api/v1/auth/register \
  -H "Content-Type: application/json" \
  -d '{
    "email": "test@example.com",
    "password": "Test123!@#",
    "full_name": "Test User"
  }'
```

Should return JSON with `access_token` and `refresh_token`.

---

## Docker Operations

### Starting Services

**Start All Services**:
```bash
docker-compose up -d
```

**Start with Logs** (foreground):
```bash
docker-compose up
```

**Start Specific Service**:
```bash
docker-compose up -d api
```

---

### Stopping Services

**Stop All Services**:
```bash
docker-compose down
```

**Stop Specific Service**:
```bash
docker-compose stop api
```

**Stop and Remove Volumes** (DELETES ALL DATA):
```bash
docker-compose down -v
```

**CRITICAL**: `-v` flag deletes database data. Use only for clean slate.

---

### Restarting Services

**Restart All Services**:
```bash
docker-compose restart
```

**Restart Specific Service**:
```bash
docker-compose restart api
```

**Restart After Code Changes**:
```bash
# API or Worker code changed
docker-compose restart api worker
```

**Restart After Dependency Changes**:
```bash
# requirements.txt changed
docker-compose down
docker-compose build
docker-compose up -d
```

---

### Viewing Logs

**All Services**:
```bash
docker-compose logs -f
```

**Specific Service**:
```bash
docker-compose logs -f api
docker-compose logs -f worker
docker-compose logs -f db
```

**Last N Lines**:
```bash
docker-compose logs --tail=50 api
```

**Since Timestamp**:
```bash
docker-compose logs --since 2025-12-31T10:00:00 api
```

---

### Rebuilding Services

**After requirements.txt Changes**:
```bash
docker-compose down
docker-compose build
docker-compose up -d
```

**Force Rebuild** (no cache):
```bash
docker-compose build --no-cache
docker-compose up -d
```

**Rebuild Specific Service**:
```bash
docker-compose build api
docker-compose up -d api
```

---

### Accessing Containers

**Execute Command in Running Container**:
```bash
docker-compose exec api bash
docker-compose exec db psql -U user -d talent_db
docker-compose exec worker bash
```

**Execute Python Shell**:
```bash
docker-compose exec api python
```

**Execute One-Off Command**:
```bash
docker-compose exec api alembic upgrade head
docker-compose exec api pytest
```

---

## Database Management

### Running Migrations

**Upgrade to Latest**:
```bash
docker-compose exec api alembic upgrade head
```

**Downgrade One Migration**:
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

---

### Creating Migrations

**Auto-Generate from Model Changes**:
```bash
docker-compose exec api alembic revision --autogenerate -m "description"
```

**Manual Migration**:
```bash
docker-compose exec api alembic revision -m "description"
```

**Best Practices**:
1. Review auto-generated migrations before applying
2. Test migrations on dev database first
3. Always provide descriptive migration names
4. Commit migration files to version control

---

### Database Access

**psql Shell**:
```bash
docker-compose exec db psql -U user -d talent_db
```

**Common psql Commands**:
```sql
-- List tables
\dt

-- Describe table
\d users

-- Count records
SELECT COUNT(*) FROM users;

-- List enum types
\dT+

-- Show enum values
\dT+ subscriptionplan

-- Quit
\q
```

---

### Database Backup

**Backup to File**:
```bash
docker-compose exec -T db pg_dump -U user talent_db > backup_$(date +%Y%m%d_%H%M%S).sql
```

**Backup with Compression**:
```bash
docker-compose exec -T db pg_dump -U user talent_db | gzip > backup_$(date +%Y%m%d_%H%M%S).sql.gz
```

---

### Database Restore

**From SQL File**:
```bash
# Stop API and worker first
docker-compose stop api worker

# Restore
cat backup.sql | docker-compose exec -T db psql -U user talent_db

# Restart services
docker-compose start api worker
```

**From Compressed Backup**:
```bash
gunzip -c backup.sql.gz | docker-compose exec -T db psql -U user talent_db
```

---

### Database Reset (DESTRUCTIVE)

**Complete Reset**:
```bash
# WARNING: Deletes ALL data
docker-compose down -v
docker-compose up -d
docker-compose exec api alembic upgrade head
```

**Table-Specific Reset**:
```bash
docker-compose exec db psql -U user -d talent_db -c "TRUNCATE TABLE candidates CASCADE;"
```

---

## Celery Worker Management

### Monitoring Workers

**Check Worker Status**:
```bash
docker-compose logs -f worker
```

**Active Tasks**:
```bash
docker-compose exec worker celery -A app.core.celery_app inspect active
```

**Registered Tasks**:
```bash
docker-compose exec worker celery -A app.core.celery_app inspect registered
```

**Worker Stats**:
```bash
docker-compose exec worker celery -A app.core.celery_app inspect stats
```

---

### Task Queue Management

**Purge All Tasks**:
```bash
docker-compose exec worker celery -A app.core.celery_app purge
```

**View Queue Length** (via Redis):
```bash
docker-compose exec redis redis-cli LLEN celery
```

---

### Restarting Workers

**Restart Worker**:
```bash
docker-compose restart worker
```

**After Code Changes**:
```bash
# Worker picks up new code on restart
docker-compose restart worker
```

---

## Common Issues & Solutions

### Issue: "Server error. Please try again" on Registration

**Symptoms**:
- Registration form shows generic error
- No specific error message

**Debug Steps**:
1. Check API logs:
   ```bash
   docker-compose logs api --tail=50
   ```

2. Look for Python stack traces

**Common Causes**:

#### 1. Bcrypt Version Incompatibility
**Error**: `ValueError: password cannot be longer than 72 bytes`

**Solution**: Ensure `bcrypt==3.2.0` in requirements.txt
```bash
# Update requirements.txt
# Then rebuild
docker-compose down
docker-compose build
docker-compose up -d
```

#### 2. Missing Database Tables
**Error**: `relation "users" does not exist`

**Solution**: Run migrations
```bash
docker-compose exec api alembic upgrade head
```

#### 3. Enum Value Mismatch
**Error**: `invalid input value for enum subscriptionplan: "FREE"`

**Solution**: Update models to use `values_callable`:
```python
plan = Column(
    Enum(SubscriptionPlan, values_callable=lambda x: [e.value for e in x]),
    default=SubscriptionPlan.FREE,
    nullable=False
)
```

Then restart:
```bash
docker-compose restart api
```

#### 4. Pydantic Validation Error
**Error**: `ValidationError: Extra inputs are not permitted`

**Solution**: Add `extra = "ignore"` to Settings Config class in `app/core/config.py`:
```python
class Config:
    env_file = ".env"
    case_sensitive = True
    extra = "ignore"
```

Then restart:
```bash
docker-compose restart api
```

---

### Issue: 401 Unauthorized on API Requests

**Symptoms**:
- API returns `{"detail": "Not authenticated"}`
- Frontend shows "Unauthorized" errors

**Debug Steps**:

1. **Check Token Format**:
   ```bash
   # Correct format
   Authorization: Bearer eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9...

   # Incorrect (missing "Bearer")
   Authorization: eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9...
   ```

2. **Verify Token Expiration**:
   ```javascript
   // Decode JWT (client-side)
   const payload = JSON.parse(atob(token.split('.')[1]));
   console.log('Expires:', new Date(payload.exp * 1000));
   console.log('Now:', new Date());
   ```

3. **Check SECRET_KEY**:
   ```bash
   # Verify .env has SECRET_KEY
   docker-compose exec api env | grep SECRET_KEY
   ```

**Solutions**:

- **Expired Token**: Use refresh token endpoint or re-login
- **Invalid Token**: Clear localStorage and re-login
- **Missing SECRET_KEY**: Add to `.env` and restart API

---

### Issue: Candidates Stuck at PARSED/PROCESSING

**Symptoms**:
- Candidates never reach SCORED status
- Evaluations not created

**Debug Steps**:

1. **Check Worker Logs**:
   ```bash
   docker-compose logs worker --tail=100
   ```

2. **Check Active Tasks**:
   ```bash
   docker-compose exec worker celery -A app.core.celery_app inspect active
   ```

3. **Check for Errors**:
   ```bash
   docker-compose logs worker | grep -i error
   ```

**Common Causes**:

#### 1. Worker Crashed
**Solution**: Restart worker
```bash
docker-compose restart worker
```

#### 2. OpenAI API Error
**Error**: `openai.error.RateLimitError` or `openai.error.InvalidRequestError`

**Solution**: Check OpenAI API key and quota
```bash
# Verify key in .env
docker-compose exec api env | grep OPENAI_API_KEY
```

#### 3. Missing tenant_id in Evaluation
**Error**: `null value in column "tenant_id" violates not-null constraint`

**Solution**: Update `app/tasks/scoring_tasks.py` to include tenant_id:
```python
evaluation = Evaluation(
    tenant_id=candidate.tenant_id,  # Add this
    candidate_id=candidate.id,
    match_score=match_score,
    # ... rest of fields
)
```

Then restart worker:
```bash
docker-compose restart worker
```

#### 4. Task Queue Blocked
**Solution**: Purge stuck tasks
```bash
docker-compose exec worker celery -A app.core.celery_app purge
```

Then re-upload candidates.

---

### Issue: 402 Payment Required on Candidate Upload

**Symptoms**:
- Error: "Monthly candidate limit reached (5/5)"
- Can't upload more candidates

**Debug Steps**:

1. **Check Subscription**:
   ```bash
   docker-compose exec db psql -U user -d talent_db -c \
     "SELECT plan, status, monthly_candidate_limit, candidates_used_this_month FROM subscriptions WHERE user_id = 'USER_UUID';"
   ```

2. **Verify Usage**:
   ```sql
   SELECT u.email, s.plan, s.candidates_used_this_month, s.monthly_candidate_limit
   FROM subscriptions s
   JOIN users u ON u.id = s.user_id
   WHERE u.email = 'user@example.com';
   ```

**Solutions**:

#### 1. Reset Usage Counter (Development Only)
```bash
docker-compose exec db psql -U user -d talent_db -c \
  "UPDATE subscriptions SET candidates_used_this_month = 0 WHERE user_id = 'USER_UUID';"
```

#### 2. Upgrade Plan
```bash
docker-compose exec db psql -U user -d talent_db -c \
  "UPDATE subscriptions SET plan = 'professional', monthly_candidate_limit = 1000 WHERE user_id = 'USER_UUID';"
```

#### 3. Reset Subscription Status
```bash
docker-compose exec db psql -U user -d talent_db -c \
  "UPDATE subscriptions SET status = 'active' WHERE user_id = 'USER_UUID';"
```

---

### Issue: Docker Containers Won't Start

**Symptoms**:
- `docker-compose up -d` fails
- Containers exit immediately

**Debug Steps**:

1. **Check Logs**:
   ```bash
   docker-compose logs
   ```

2. **Check Port Conflicts**:
   ```bash
   # Linux/Mac
   lsof -i :8000
   lsof -i :5432

   # Windows (PowerShell)
   netstat -ano | findstr :8000
   netstat -ano | findstr :5432
   ```

3. **Check Docker Resources**:
   - Docker Desktop → Settings → Resources
   - Ensure adequate RAM (4GB minimum)

**Solutions**:

#### 1. Port Already in Use
**Solution**: Change port in `docker-compose.yml`:
```yaml
services:
  api:
    ports:
      - "8001:8000"  # Changed from 8000:8000
```

Or stop conflicting process:
```bash
# Linux/Mac
kill -9 <PID>

# Windows
taskkill /PID <PID> /F
```

#### 2. Docker Out of Memory
**Solution**: Increase Docker memory limit:
- Docker Desktop → Settings → Resources → Memory → 4GB+

#### 3. Corrupted Docker State
**Solution**: Prune Docker system
```bash
docker system prune -a
docker volume prune
```

Then rebuild:
```bash
docker-compose build --no-cache
docker-compose up -d
```

---

### Issue: Frontend Shows "Failed to fetch" Errors

**Symptoms**:
- Network errors in browser console
- API requests fail

**Debug Steps**:

1. **Check API Status**:
   ```bash
   curl http://localhost:8000/docs
   ```

2. **Check Browser Console**:
   - Open DevTools → Console
   - Look for CORS errors or network failures

3. **Check CORS Headers**:
   ```bash
   curl -I -H "Origin: http://localhost:3000" http://localhost:8000/api/v1/auth/me
   ```

**Solutions**:

#### 1. API Not Running
**Solution**: Start API
```bash
docker-compose up -d api
```

#### 2. CORS Issue
**Solution**: Update CORS settings in `main.py`:
```python
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000", "http://localhost:8000"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
```

Then restart:
```bash
docker-compose restart api
```

#### 3. Wrong API URL
**Solution**: Check frontend config:
```javascript
// Should point to http://localhost:8000
const API_URL = "http://localhost:8000";
```

---

## Debugging Guide

### Enable Debug Logging

**FastAPI**:
Add to `main.py`:
```python
import logging
logging.basicConfig(level=logging.DEBUG)
```

**SQLAlchemy** (SQL query logging):
Add to `app/core/database.py`:
```python
engine = create_engine(
    DATABASE_URL,
    echo=True  # Logs all SQL queries
)
```

Restart:
```bash
docker-compose restart api
```

---

### Debugging Celery Tasks

**Add Logging to Tasks**:
```python
import logging
logger = logging.getLogger(__name__)

@celery_app.task
def my_task():
    logger.info("Task started")
    # ... task logic
    logger.info("Task completed")
```

**View Worker Logs**:
```bash
docker-compose logs -f worker
```

**Test Task Manually**:
```bash
docker-compose exec api python
>>> from app.tasks.scoring_tasks import score_candidate_task
>>> score_candidate_task.delay(candidate_id=1)
```

---

### Debugging Database Issues

**Enable SQL Logging**:
```python
# app/core/database.py
engine = create_engine(DATABASE_URL, echo=True)
```

**Check Slow Queries**:
```sql
-- Enable query logging in PostgreSQL
ALTER SYSTEM SET log_min_duration_statement = 1000;  -- Log queries >1s
SELECT pg_reload_conf();

-- View logs
docker-compose logs db
```

**Analyze Query Plans**:
```sql
EXPLAIN ANALYZE
SELECT c.*, e.match_score
FROM candidates c
LEFT JOIN evaluations e ON e.candidate_id = c.id
WHERE c.tenant_id = 'uuid-here';
```

---

### Debugging Authentication Issues

**Decode JWT Token**:
```bash
# Install jwt-cli
npm install -g jwt-cli

# Decode token
jwt decode <your_token_here>
```

**Or use Python**:
```python
docker-compose exec api python
>>> from app.core.security import decode_token
>>> payload = decode_token("your_token_here")
>>> print(payload)
```

**Verify Token in Database**:
```sql
SELECT u.*, s.*
FROM users u
LEFT JOIN subscriptions s ON s.user_id = u.id
WHERE u.id = '<user_id_from_token>';
```

---

## Production Deployment (Phase 2)

**Note**: Current setup is development-only. Production deployment pending.

### Production Checklist

**Security**:
- [ ] Change all default passwords
- [ ] Use environment-specific `.env` files
- [ ] Enable HTTPS (SSL/TLS certificates)
- [ ] Restrict CORS to production domains
- [ ] Enable rate limiting
- [ ] Set up firewall rules
- [ ] Use secrets manager (AWS Secrets Manager, Vault)

**Infrastructure**:
- [ ] Migrate to managed PostgreSQL (AWS RDS, Google Cloud SQL)
- [ ] Migrate to managed Redis (AWS ElastiCache, Redis Cloud)
- [ ] Set up S3 for file storage (replace local `uploads/`)
- [ ] Configure CDN for static files
- [ ] Set up load balancer
- [ ] Enable auto-scaling for API and workers

**Monitoring**:
- [ ] Set up Sentry for error tracking
- [ ] Configure Prometheus + Grafana for metrics
- [ ] Enable CloudWatch or Datadog logging
- [ ] Set up uptime monitoring (Pingdom, UptimeRobot)
- [ ] Configure alerts (PagerDuty, Slack)

**Backups**:
- [ ] Automated daily database backups
- [ ] Point-in-time recovery enabled
- [ ] Backup retention policy (30 days)
- [ ] Backup restoration tests

**CI/CD**:
- [ ] GitHub Actions for automated testing
- [ ] Automated deployment pipeline
- [ ] Blue-green deployment strategy
- [ ] Rollback procedures

---

## Monitoring & Logging

### Current Monitoring (Development)

**Docker Logs**:
```bash
# Tail all services
docker-compose logs -f

# Filter by service
docker-compose logs -f api | grep ERROR
```

**Resource Usage**:
```bash
docker stats
```

---

### Production Monitoring (Phase 2)

**Sentry Integration**:
```python
# main.py
import sentry_sdk
sentry_sdk.init(
    dsn="https://your-dsn@sentry.io/project",
    environment="production"
)
```

**Structured Logging**:
```python
# Replace print statements with structlog
import structlog
logger = structlog.get_logger()

logger.info("user_registered", user_id=user.id, email=user.email)
```

**Health Check Endpoint**:
```python
@app.get("/health")
def health_check():
    return {
        "status": "healthy",
        "database": check_db_connection(),
        "redis": check_redis_connection()
    }
```

---

## Backup & Recovery

### Development Backups

**Manual Backup**:
```bash
docker-compose exec -T db pg_dump -U user talent_db > backup.sql
```

**Restore**:
```bash
cat backup.sql | docker-compose exec -T db psql -U user talent_db
```

---

### Production Backups (Phase 2)

**Automated Daily Backups**:
- Use managed database backup features (RDS automated backups)
- Retention: 30 days
- Point-in-time recovery: Last 7 days

**Backup Strategy**:
1. **Database**: Automated snapshots every 6 hours
2. **Files**: S3 versioning enabled
3. **Configuration**: Stored in version control

**Recovery Time Objectives**:
- RTO (Recovery Time): < 1 hour
- RPO (Recovery Point): < 6 hours

---

## Performance Optimization

### Current Bottlenecks

1. **Local File Storage**: Blocks horizontal scaling
2. **No Query Caching**: Repeated API calls hit database
3. **No CDN**: Static files served from API
4. **Sequential Resume Processing**: One at a time

### Optimization Roadmap (Phase 2)

**Database**:
- Add indexes on frequently queried columns
- Enable connection pooling
- Use read replicas for analytics queries

**Caching**:
- Redis cache for API responses
- Cache job configs (rarely change)
- Cache user subscriptions

**File Storage**:
- Migrate to S3 with CloudFront CDN
- Pre-signed URLs for direct uploads
- Image optimization for resumes

**Worker Scaling**:
- Horizontal scaling (multiple workers)
- Priority queues (urgent vs. batch processing)
- Separate queues for parsing vs. scoring

---

*Last Updated: 2025-12-31*

*Environment: Docker Compose (Development)*
