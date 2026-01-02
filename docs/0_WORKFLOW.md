# Development Workflow

**Purpose**: This document explains the complete development workflow for Starscreen Resume Analyzer, optimized for LLM context and debugging assistance.

---

## Architecture Overview

```
┌─────────────────┐         ┌──────────────┐         ┌─────────────────┐
│  Local Machine  │ ──git──>│ GitHub Repo  │ ──git──>│   EC2 Server    │
│  (Windows)      │ <─pull──│  (Remote)    │ <─push──│  (Production)   │
└─────────────────┘         └──────────────┘         └─────────────────┘
     │                                                          │
     │ Claude Code                                              │ Docker
     │ IDE: VS Code                                             │ Nginx + SSL
     │                                                          │
     └─> Local development                                      └─> starscreen.net
         Code changes                                               Live users
         Testing                                                    Production DB
```

---

## Three-Environment System

### 1. **Local Machine** (Development)
- **OS**: Windows (`c:\Users\gdsak_ukfkfpt\Desktop\Resume-Analyzer\`)
- **Purpose**: Code development, testing, AI assistance with Claude Code
- **Tools**: VS Code, Git, Claude Code CLI
- **Services**: Docker Compose (optional for local testing)
- **Database**: Local PostgreSQL (if running Docker locally)

### 2. **GitHub Repository** (Version Control)
- **URL**: Remote repository (centralized)
- **Purpose**: Version control, code synchronization between local and EC2
- **Branches**: `main` (production), feature branches as needed
- **Critical Files**:
  - `.gitignore` (excludes `.env`, `uploads/`, `__pycache__/`, etc.)
  - All application code (`app/`, `static/`, `docs/`)

### 3. **EC2 Server** (Production)
- **Domain**: https://starscreen.net
- **OS**: Ubuntu Linux
- **Purpose**: Live production environment
- **Services**:
  - Docker Compose (API, Worker, PostgreSQL, Redis)
  - Nginx (reverse proxy, SSL termination with Let's Encrypt)
- **Database**: Production PostgreSQL with live user data
- **Storage**: AWS S3 for resume files (uses IAM role authentication)

---

## Standard Development Workflow

### Step 1: Make Changes Locally
```bash
# On local machine (Windows)
# Work in: c:\Users\gdsak_ukfkfpt\Desktop\Resume-Analyzer\

# 1. Edit code files (with Claude Code assistance)
# 2. Test changes locally (optional: docker-compose up)
# 3. Review changes
git status
git diff
```

### Step 2: Commit and Push to GitHub
```bash
# Add changed files
git add <files>

# Commit with descriptive message
git commit -m "Description of changes

🤖 Generated with [Claude Code](https://claude.com/claude-code)

Co-Authored-By: Claude Sonnet 4.5 <noreply@anthropic.com>"

# Push to remote
git push origin main
```

### Step 3: Deploy to EC2
```bash
# SSH into EC2 server
ssh ubuntu@starscreen.net  # (or use EC2 IP)

# Navigate to project directory
cd /path/to/Resume-Analyzer

# Pull latest changes
git pull origin main

# Restart affected services
docker-compose restart api        # For backend code changes
docker-compose restart worker     # For Celery task changes
# OR
docker-compose build api && docker-compose up -d api  # If dependencies changed
# OR
docker-compose down && docker-compose up -d  # Full restart (rare)

# For static files (HTML/JS/CSS):
# Nginx serves them directly, no restart needed after git pull

# Check logs
docker-compose logs -f api
docker-compose logs -f worker
```

---

## Critical Files and Locations

### Code Files (Synced via Git)
- `app/` - Python backend code (FastAPI, SQLAlchemy models, endpoints)
- `static/` - Frontend HTML/JS/CSS files
- `requirements.txt` - Python dependencies
- `docker-compose.yml` - Service orchestration
- `Dockerfile` - API container build instructions
- `alembic/` - Database migrations

### Environment Files (NOT in Git)
- `.env` - Environment variables (LOCAL version)
- `.env` on EC2 - Environment variables (PRODUCTION version)
  - **Important**: Changes to `.env` must be made manually on both local and EC2
  - **Never commit** `.env` to Git (contains secrets like API keys)

### Generated/Runtime Files (NOT in Git)
- `uploads/` - Resume files (local storage fallback)
- `__pycache__/` - Python bytecode
- `.pytest_cache/` - Test cache
- `*.pyc` - Compiled Python files

---

## Environment Configuration

### Local `.env`
```bash
# Located: c:\Users\gdsak_ukfkfpt\Desktop\Resume-Analyzer\.env
FRONTEND_URL=https://starscreen.net
POSTGRES_SERVER=db
POSTGRES_USER=starscreen_user
POSTGRES_PASSWORD=Ilikecode1!
POSTGRES_DB=starscreen_prod

# Free tier for testing
FREE_TIER_CANDIDATE_LIMIT=999999

# Live Stripe keys
STRIPE_API_KEY=sk_live_...
STRIPE_WEBHOOK_SECRET=whsec_...

# S3 Settings
USE_S3=true
AWS_REGION=us-east-1
S3_BUCKET_NAME=starscreen-resumes-prod
AWS_ACCESS_KEY_ID=          # Empty (using IAM role on EC2)
AWS_SECRET_ACCESS_KEY=      # Empty (using IAM role on EC2)
```

### EC2 `.env`
**Same as local, but must be updated manually when values change!**

To update EC2 `.env`:
```bash
# SSH to EC2
ssh ubuntu@starscreen.net

# Edit .env
nano .env  # or vim .env

# Save changes
# Restart services
docker-compose restart api worker
```

---

## Common Operations

### Update Backend Code
```bash
# Local
git add app/
git commit -m "Fix: Update subscription logic"
git push

# EC2
ssh ubuntu@starscreen.net
cd /path/to/project
git pull
docker-compose restart api
```

### Update Frontend Code
```bash
# Local
git add static/
git commit -m "UI: Update pricing page"
git push

# EC2
ssh ubuntu@starscreen.net
cd /path/to/project
git pull
# No restart needed - Nginx serves static files directly
```

### Add New Python Dependency
```bash
# Local
# 1. Add to requirements.txt
echo "new-package==1.0.0" >> requirements.txt

# 2. Commit and push
git add requirements.txt
git commit -m "Add new-package dependency"
git push

# EC2
ssh ubuntu@starscreen.net
cd /path/to/project
git pull
docker-compose build api worker    # Rebuild to install new packages
docker-compose up -d api worker     # Restart with new image
```

### Database Migration
```bash
# Local - Create migration
docker-compose exec api alembic revision --autogenerate -m "Description"

# Commit migration file
git add alembic/versions/*.py
git commit -m "Migration: Description"
git push

# EC2 - Apply migration
ssh ubuntu@starscreen.net
cd /path/to/project
git pull
docker-compose exec api alembic upgrade head
docker-compose restart api
```

### View Logs
```bash
# EC2
docker-compose logs -f api              # Follow API logs
docker-compose logs --tail=100 worker   # Last 100 worker logs
docker-compose logs api | grep ERROR    # Filter for errors
```

### Emergency Rollback
```bash
# EC2
git log --oneline -10                   # Find commit to rollback to
git checkout <commit-hash>              # Rollback code
docker-compose restart api worker       # Restart with old code
# OR
git revert <commit-hash>                # Create revert commit
git push                                # Push revert
```

---

## Key Architectural Decisions

### 1. **S3 for File Storage**
- Production uses AWS S3 (`starscreen-resumes-prod` bucket)
- EC2 instance has IAM role with S3 access (no credentials needed)
- Local development: Leave `AWS_ACCESS_KEY_ID` empty to use IAM role when testing on EC2

### 2. **Nginx + SSL**
- Nginx on EC2 handles HTTPS termination with Let's Encrypt certificates
- Routes `https://starscreen.net/api/v1/*` → `http://localhost:8000` (FastAPI)
- Routes `https://starscreen.net/static/*` → Direct file serving
- Routes `https://starscreen.net/` → `/static/index.html`

### 3. **Database**
- Production PostgreSQL runs in Docker on EC2
- Port 5432 (internal to Docker network)
- Regular backups recommended (not covered in this doc)

### 4. **Authentication**
- JWT-based stateless authentication
- Access tokens expire in 30 minutes
- Refresh tokens expire in 7 days
- Public pages: `login.html`, `register.html`, `pricing.html`, `checkout.html`

### 5. **Subscription System**
- **FREE**: Configurable limit (currently 999999 for testing)
- **STARTER** (Recruiter): 100 candidates/month ($20/mo)
- **SMALL_BUSINESS**: 1,000 candidates/month ($149/mo)
- **PROFESSIONAL** (Enterprise): Unlimited + $0.25/candidate ($399/mo base)
- No free trials - immediate billing

---

## Troubleshooting Common Issues

### Issue: Changes not appearing on production
```bash
# EC2
git pull                    # Ensure latest code is pulled
docker-compose restart api  # Ensure service restarted
docker-compose logs api     # Check for startup errors
```

### Issue: Environment variables not working
```bash
# EC2
cat .env                    # Verify .env exists and has correct values
docker-compose down
docker-compose up -d        # Full restart to reload .env
```

### Issue: Database connection failed
```bash
# EC2
docker-compose ps           # Check if db container is running
docker-compose logs db      # Check database logs
# Verify POSTGRES_* variables in .env match docker-compose.yml
```

### Issue: Import errors / Module not found
```bash
# EC2
docker-compose build api    # Rebuild to install missing dependencies
docker-compose up -d api
docker-compose logs api     # Check for import errors
```

### Issue: Resume upload failing (402 Payment Required)
- Check user's subscription status and limits in database
- Verify `FREE_TIER_CANDIDATE_LIMIT` in `.env`
- Check if subscription status is `ACTIVE` or `TRIALING`
- See commit `11e8023` for fix

---

## Git Best Practices

### Commit Messages
```
Brief description (50 chars or less)

Longer explanation if needed. Describe:
- Why this change was made
- What problem it solves
- Any side effects or considerations

🤖 Generated with [Claude Code](https://claude.com/claude-code)

Co-Authored-By: Claude Sonnet 4.5 <noreply@anthropic.com>
```

### Files to Never Commit
- `.env` (contains secrets)
- `uploads/` (user data)
- `__pycache__/` (generated files)
- `*.pyc` (compiled Python)
- `.pytest_cache/` (test cache)
- `.DS_Store` (macOS)
- `node_modules/` (if using Node)

### Pre-Push Checklist
- [ ] Code tested locally (if applicable)
- [ ] No secrets in committed files
- [ ] Commit message is descriptive
- [ ] `.env` changes documented for manual EC2 update
- [ ] Database migrations created (if schema changed)

---

## Quick Reference Commands

### Local Development
```bash
# View status
git status

# View changes
git diff

# Commit changes
git add <files>
git commit -m "Message"
git push

# View recent commits
git log --oneline -10
```

### EC2 Production
```bash
# Deploy
ssh ubuntu@starscreen.net
cd /path/to/project
git pull
docker-compose restart api

# Check status
docker-compose ps
docker-compose logs -f api

# Full restart
docker-compose down
docker-compose up -d
```

### Docker Commands
```bash
# Restart specific service
docker-compose restart api

# Rebuild and restart
docker-compose build api
docker-compose up -d api

# View logs
docker-compose logs -f api
docker-compose logs --tail=50 worker

# Execute command in container
docker-compose exec api python -c "print('hello')"
docker-compose exec db psql -U starscreen_user -d starscreen_prod

# Full cleanup (DANGEROUS - removes volumes!)
docker-compose down -v
```

---

**Last Updated**: 2026-01-01
**Status**: Production workflow established and documented
