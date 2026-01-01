# Quick Start - Deploy Starscreen to Production

## Current Status

✅ **Infrastructure Setup Complete:**
- IAM Role `StarscreenEC2Role` with `AmazonS3FullAccess` policy
- IAM Instance Profile attached to EC2
- EC2 instance running (Ubuntu 24.04, IP: 44.223.41.116)
- SSH access configured (`ssh starscreen-ec2`)
- S3 bucket `starscreen-resumes-prod` created and tested
- S3 code implementation complete

✅ **Ready to deploy application!**

---

## Deployment Steps

### Step 1: Push Code to GitHub

From your **local Windows machine** (PowerShell):

```powershell
cd C:\Users\gdsak_ukfkfpt\Desktop\Resume-Analyzer

# Initialize git repository (if not done already)
git init
git add .
git commit -m "Initial commit - Starscreen with S3 storage integration"

# Add your GitHub remote (create repo on GitHub first)
git remote add origin https://github.com/YOUR_USERNAME/Resume-Analyzer.git
git branch -M main
git push -u origin main
```

---

### Step 2: Clone Repository on EC2

SSH into your EC2 instance:

```bash
ssh starscreen-ec2

# Clone the repository
cd ~
git clone https://github.com/YOUR_USERNAME/Resume-Analyzer.git
cd Resume-Analyzer
```

---

### Step 3: Create Production `.env` File

Create the environment configuration file:

```bash
cd ~/Resume-Analyzer
nano .env
```

Paste this configuration (**update the placeholders!**):

```bash
# API Settings
PROJECT_NAME=Starscreen Resume Analyzer
API_V1_STR=/api/v1

# Database
POSTGRES_USER=starscreen_user
POSTGRES_PASSWORD=CHANGE_THIS_TO_STRONG_PASSWORD
POSTGRES_SERVER=db
POSTGRES_PORT=5432
POSTGRES_DB=starscreen_prod

# Redis
REDIS_HOST=redis
REDIS_PORT=6379
REDIS_DB=0

# OpenAI
OPENAI_API_KEY=sk-YOUR_OPENAI_API_KEY_HERE
OPENAI_MODEL=gpt-4o
OPENAI_TEMPERATURE=0.2

# JWT (generate SECRET_KEY with: openssl rand -hex 32)
SECRET_KEY=GENERATE_RANDOM_64_CHAR_KEY
ALGORITHM=HS256
ACCESS_TOKEN_EXPIRE_MINUTES=30
REFRESH_TOKEN_EXPIRE_DAYS=7

# Stripe
STRIPE_API_KEY=sk_test_YOUR_STRIPE_KEY
STRIPE_WEBHOOK_SECRET=whsec_YOUR_WEBHOOK_SECRET
STRIPE_PRICE_ID_STARTER=price_YOUR_STARTER_PRICE_ID
STRIPE_PRICE_ID_SMALL_BUSINESS=price_YOUR_SMALL_BIZ_PRICE_ID
STRIPE_PRICE_ID_PROFESSIONAL=price_YOUR_PROF_PRICE_ID
STRIPE_PRICE_ID_ENTERPRISE_BASE=price_YOUR_ENTERPRISE_BASE_PRICE_ID

# AWS S3 (IAM role provides credentials - leave these empty!)
USE_S3=true
AWS_ACCESS_KEY_ID=
AWS_SECRET_ACCESS_KEY=
AWS_REGION=us-east-1
S3_BUCKET_NAME=starscreen-resumes-prod

# Free Tier
FREE_TIER_CANDIDATE_LIMIT=10
```

**Save**: Press `Ctrl+X`, then `Y`, then `Enter`

---

### Step 4: Generate Secure Keys

Generate a secure SECRET_KEY for JWT tokens:

```bash
openssl rand -hex 32
```

Copy the output and update the `SECRET_KEY` value in `.env`:

```bash
nano .env
# Find SECRET_KEY= and paste the generated value
```

---

### Step 5: Build and Start Application

Start all services with Docker Compose:

```bash
cd ~/Resume-Analyzer

# Build Docker images (includes installing boto3 for S3)
docker-compose build

# Start all services (API, Worker, Database, Redis)
docker-compose up -d

# Verify all containers are running
docker-compose ps
# Should show: api, worker, db, redis all "Up"
```

---

### Step 6: Run Database Migrations

Initialize the database schema:

```bash
cd ~/Resume-Analyzer

# Run Alembic migrations
docker-compose exec api alembic upgrade head

# Verify tables were created
docker-compose exec db psql -U starscreen_user -d starscreen_prod -c "\dt"
# Should show: users, subscriptions, jobs, candidates, evaluations
```

---

### Step 7: Check Application Logs

Verify everything started correctly:

```bash
# View all logs
docker-compose logs

# View API logs specifically
docker-compose logs api

# Follow logs in real-time
docker-compose logs -f

# Press Ctrl+C to exit
```

Look for:
- ✅ API: "Application startup complete"
- ✅ Worker: "celery@worker ready"
- ✅ Database: "database system is ready to accept connections"

---

### Step 8: Test the API

Test from EC2:

```bash
# Test API is responding
curl http://localhost:8000/

# Should return: {"message":"Starscreen API is running"}
```

Test from your **local machine**:

Open browser to: `http://44.223.41.116:8000/docs`

You should see the Swagger API documentation! ✅

---

### Step 9: Test End-to-End S3 Flow

Register a test user and upload a resume:

```bash
# Register user
curl -X POST http://localhost:8000/api/v1/auth/register \
  -H "Content-Type: application/json" \
  -d '{
    "email": "test@starscreen.com",
    "password": "Test123!@#"
  }'

# Copy the access_token from the response

# Create a job
curl -X POST http://localhost:8000/api/v1/jobs/ \
  -H "Authorization: Bearer YOUR_ACCESS_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "title": "Senior Python Developer",
    "description": "Looking for experienced Python developer with FastAPI and AWS experience"
  }'

# Upload a test resume (create a test file first)
echo "John Doe - Senior Python Developer
5+ years experience with Python, FastAPI, AWS, and Docker" > test-resume.txt

curl -X POST http://localhost:8000/api/v1/jobs/1/candidates \
  -H "Authorization: Bearer YOUR_ACCESS_TOKEN" \
  -F "file=@test-resume.txt" \
  -F "name=John Doe" \
  -F "email=john@example.com"

# Verify file was uploaded to S3
aws s3 ls s3://starscreen-resumes-prod/resumes/
# Should show the uploaded file!
```

---

## Next Steps

### Production Hardening

1. **Set up HTTPS**:
   - Install Nginx reverse proxy
   - Get SSL certificate with Let's Encrypt (certbot)
   - Configure domain name

2. **Security**:
   - Close port 8000 in security group (use Nginx on port 80/443)
   - Set up CloudWatch logging
   - Enable automated backups for PostgreSQL

3. **Monitoring**:
   - Set up health check endpoints
   - Configure CloudWatch alarms
   - Monitor Docker container logs

### Useful Commands

```bash
# View running containers
docker-compose ps

# Restart a service
docker-compose restart api

# View logs
docker-compose logs -f api

# Stop all services
docker-compose down

# Rebuild and restart
docker-compose down && docker-compose build && docker-compose up -d

# Check database
docker-compose exec db psql -U starscreen_user -d starscreen_prod

# Access Redis
docker-compose exec redis redis-cli

# Run shell in API container
docker-compose exec api bash
```

---

## Troubleshooting

### API Won't Start

```bash
# Check logs
docker-compose logs api

# Common issues:
# - Missing .env file
# - Invalid DATABASE_URL
# - Port 8000 already in use
```

### Worker Not Processing Resumes

```bash
# Check worker logs
docker-compose logs worker

# Test Redis connection
docker-compose exec worker redis-cli -h redis ping
# Should return: PONG

# Restart worker
docker-compose restart worker
```

### S3 Upload Fails

```bash
# Verify S3 bucket exists
aws s3 ls s3://starscreen-resumes-prod/

# Test S3 access from EC2
echo "test" > test.txt
aws s3 cp test.txt s3://starscreen-resumes-prod/test.txt
aws s3 rm s3://starscreen-resumes-prod/test.txt
rm test.txt

# Check IAM role
aws sts get-caller-identity
# Should show: StarscreenEC2Role
```

---

**Status**: Ready for Production Deployment
**Last Updated**: 2026-01-01
