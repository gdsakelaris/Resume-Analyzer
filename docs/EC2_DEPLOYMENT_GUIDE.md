# EC2 Deployment Guide - Starscreen with S3

## Current Status

### ✅ What's Done
1. **IAM Role**: `StarscreenEC2Role` created with `AmazonS3FullAccess` policy attached
2. **IAM User**: `starscreen-app` created with access keys (for local AWS CLI)
3. **IAM Instance Profile**: Created and attached to EC2 instance
4. **EC2 Instance**: Launched (Ubuntu 24.04, t3.medium, Public IP: 44.223.41.116)
5. **SSH Access**: Configured via `ssh starscreen-ec2`
6. **User Data Script**: Auto-installed Docker, Docker Compose, Git, AWS CLI
7. **S3 Bucket**: `starscreen-resumes-prod` created with encryption and public access blocked
8. **S3 Access Verified**: EC2 can upload/download/delete from S3 bucket

### ⏳ What's Next
1. Push code to GitHub
2. Clone repository on EC2
3. Configure .env with production settings
4. Deploy application with Docker Compose
5. Run database migrations
6. Test end-to-end S3 upload flow

---

## Step-by-Step Deployment

### Step 0: Configure Local AWS CLI (Required First!)

Before you can create the instance profile, you need to configure your local AWS CLI with the `starscreen-app` user's credentials.

**On your local Windows machine (PowerShell):**

```powershell
# Configure AWS CLI with starscreen-app credentials
aws configure

# You'll be prompted for:
# AWS Access Key ID: [Enter the access key from starscreen-app user]
# AWS Secret Access Key: [Enter the secret key from starscreen-app user]
# Default region name: us-east-1
# Default output format: json
```

**Verify it works:**
```powershell
aws sts get-caller-identity
# Should show: UserId, Account, and Arn for starscreen-app user
```

---

### Step 0.5: Create and Attach IAM Instance Profile

**IMPORTANT**: Creating an IAM role is not enough - you must also create an **instance profile** and attach it to EC2.

**From your local machine (PowerShell):**

```powershell
# Step 1: Create instance profile
aws iam create-instance-profile --instance-profile-name StarscreenEC2Role

# Step 2: Add the IAM role to the instance profile
aws iam add-role-to-instance-profile `
  --instance-profile-name StarscreenEC2Role `
  --role-name StarscreenEC2Role

# Step 3: Get your EC2 instance ID
aws ec2 describe-instances `
  --filters "Name=ip-address,Values=44.223.41.116" `
  --query "Reservations[0].Instances[0].InstanceId" `
  --output text
# Copy the instance ID (will look like: i-0abc123def456789)

# Step 4: Attach instance profile to EC2
aws ec2 associate-iam-instance-profile `
  --instance-id i-XXXXXXXXXXXXXXXXX `
  --iam-instance-profile Name=StarscreenEC2Role
# Replace i-XXXXXXXXXXXXXXXXX with your actual instance ID from Step 3
```

**Verify it worked:**
```powershell
# Check instance profile is attached
aws ec2 describe-instances `
  --instance-ids i-XXXXXXXXXXXXXXXXX `
  --query "Reservations[0].Instances[0].IamInstanceProfile" `
  --output json
# Should show the instance profile ARN
```

---

### Step 1: SSH into EC2

```bash
ssh starscreen-ec2
```

---

### Step 2: Verify Setup Script Completed

```bash
# Check setup completed
cat ~/setup-complete.txt
# Should output: "Starscreen base setup complete!"

# Verify Docker installed
docker --version
# Should show: Docker version 24.x.x

# Verify Docker Compose
docker-compose --version
# Should show: Docker Compose version v2.24.0

# Verify IAM role attached (most important!)
curl -s http://169.254.169.254/latest/meta-data/iam/security-credentials/
# Should output: StarscreenEC2Role
```

If any of these fail, the user data script may still be running. Wait 2-3 minutes and check again.

---

### Step 3: Create S3 Bucket

```bash
# Create bucket
aws s3 mb s3://starscreen-resumes-prod --region us-east-1

# Block public access
aws s3api put-public-access-block \
  --bucket starscreen-resumes-prod \
  --public-access-block-configuration \
  "BlockPublicAcls=true,IgnorePublicAcls=true,BlockPublicPolicy=true,RestrictPublicBuckets=true"

# Enable encryption
aws s3api put-bucket-encryption \
  --bucket starscreen-resumes-prod \
  --server-side-encryption-configuration \
  '{"Rules":[{"ApplyServerSideEncryptionByDefault":{"SSEAlgorithm":"AES256"}}]}'

# Test bucket access
echo "test" > test.txt
aws s3 cp test.txt s3://starscreen-resumes-prod/test.txt
aws s3 ls s3://starscreen-resumes-prod/
aws s3 rm s3://starscreen-resumes-prod/test.txt
rm test.txt

# If all commands succeed, S3 is ready! ✅
```

---

### Step 4: Clone Repository

```bash
# Navigate to home directory
cd ~

# Clone your repository (replace with your GitHub URL)
git clone https://github.com/YOUR_USERNAME/Resume-Analyzer.git

# Or if you haven't pushed to GitHub yet, upload code manually (see Option B below)

cd Resume-Analyzer
```

**Option A: Using Git (Recommended)**
- Commit and push your local changes to GitHub first
- Then clone on EC2

**Option B: Manual Upload (If no GitHub)**
```bash
# From your local machine (PowerShell):
scp -i C:\Users\gdsak_ukfkfpt\.ssh\starscreen-key.pem -r C:\Users\gdsak_ukfkfpt\Desktop\Resume-Analyzer ubuntu@44.223.41.116:~/
```

---

### Step 5: Create .env File

```bash
cd ~/Resume-Analyzer

# Create .env file
nano .env
```

Paste this configuration (update the placeholder values):

```bash
# API Settings
PROJECT_NAME=Starscreen Resume Analyzer
API_V1_STR=/api/v1

# Database (managed by docker-compose)
POSTGRES_USER=starscreen_user
POSTGRES_PASSWORD=CHANGE_THIS_TO_STRONG_PASSWORD_123
POSTGRES_SERVER=db
POSTGRES_PORT=5432
POSTGRES_DB=starscreen_prod

# Redis (managed by docker-compose)
REDIS_HOST=redis
REDIS_PORT=6379
REDIS_DB=0

# OpenAI API
OPENAI_API_KEY=sk-YOUR_OPENAI_API_KEY_HERE
OPENAI_MODEL=gpt-4o
OPENAI_TEMPERATURE=0.2

# JWT Authentication
SECRET_KEY=CHANGE_THIS_TO_RANDOM_64_CHAR_SECRET_KEY_GENERATE_WITH_openssl_rand_hex_32
ALGORITHM=HS256
ACCESS_TOKEN_EXPIRE_MINUTES=30
REFRESH_TOKEN_EXPIRE_DAYS=7

# Stripe Settings
STRIPE_API_KEY=sk_test_YOUR_STRIPE_KEY
STRIPE_WEBHOOK_SECRET=whsec_YOUR_WEBHOOK_SECRET
STRIPE_PRICE_ID_STARTER=price_YOUR_STARTER_PRICE_ID
STRIPE_PRICE_ID_SMALL_BUSINESS=price_YOUR_SMALL_BIZ_PRICE_ID
STRIPE_PRICE_ID_PROFESSIONAL=price_YOUR_PROF_PRICE_ID
STRIPE_PRICE_ID_ENTERPRISE_BASE=price_YOUR_ENTERPRISE_BASE_PRICE_ID

# AWS S3 Settings (IAM role provides credentials automatically)
USE_S3=true
AWS_ACCESS_KEY_ID=
AWS_SECRET_ACCESS_KEY=
AWS_REGION=us-east-1
S3_BUCKET_NAME=starscreen-resumes-prod

# Free tier limit
FREE_TIER_CANDIDATE_LIMIT=10
```

**Save**: Press `Ctrl+X`, then `Y`, then `Enter`

---

### Step 6: Generate Secure Secret Key

```bash
# Generate random secret key for JWT
openssl rand -hex 32

# Copy the output and update SECRET_KEY in .env
nano .env
# Replace the SECRET_KEY value with the generated key
```

---

### Step 7: Build and Start Application

```bash
cd ~/Resume-Analyzer

# Build Docker images
docker-compose build

# Start all services (API, Worker, Database, Redis)
docker-compose up -d

# Check if containers are running
docker-compose ps
# Should show: api, worker, db, redis all "Up"
```

---

### Step 8: Check Logs

```bash
# API logs
docker-compose logs -f api

# Worker logs
docker-compose logs -f worker

# All logs
docker-compose logs -f

# Press Ctrl+C to exit logs
```

Look for:
- ✅ API: "Application startup complete"
- ✅ Worker: "celery@worker ready"
- ✅ Database: "database system is ready to accept connections"

---

### Step 9: Test Application

```bash
# Test API is responding
curl http://localhost:8000/

# Test API docs
curl http://localhost:8000/docs

# From your local machine, test public access:
# http://44.223.41.116:8000/docs
```

If you see the Swagger UI, the API is running! ✅

---

### Step 10: Run Database Migrations

```bash
cd ~/Resume-Analyzer

# Run Alembic migrations
docker-compose exec api alembic upgrade head

# Verify tables created
docker-compose exec db psql -U starscreen_user -d starscreen_prod -c "\dt"
# Should show: users, subscriptions, jobs, candidates, evaluations
```

---

### Step 11: Test S3 Upload (End-to-End)

```bash
# Register a test user
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
    "title": "Test Job",
    "description": "Testing S3 integration"
  }'

# Upload a test resume (create a dummy PDF first)
echo "Test Resume Content" > test-resume.txt
curl -X POST http://localhost:8000/api/v1/jobs/1/candidates \
  -H "Authorization: Bearer YOUR_ACCESS_TOKEN" \
  -F "file=@test-resume.txt"

# Check S3 bucket for uploaded file
aws s3 ls s3://starscreen-resumes-prod/resumes/
# Should show uploaded file!
```

---

## Troubleshooting

### Problem: IAM role not showing up (curl returns empty)

**Symptom**: When you run `curl http://169.254.169.254/latest/meta-data/iam/security-credentials/` on EC2, it returns nothing.

**Root Cause**: You created the IAM role, but didn't create/attach the **instance profile**.

**Solution**: Follow Step 0.5 above to create the instance profile and attach it to your EC2 instance.

Quick check if instance profile exists:
```powershell
# From local machine
aws iam get-instance-profile --instance-profile-name StarscreenEC2Role
```

If you get "NoSuchEntity" error, the instance profile doesn't exist - create it with Step 0.5.

---

### Problem: "InvalidClientTokenId" when running AWS CLI locally

**Cause**: Your local AWS CLI is not configured with credentials.

**Fix**: Run `aws configure` and enter your `starscreen-app` user's access key ID and secret access key (from IAM console).

---

### Problem: "docker: command not found"

```bash
# User data script may still be running
# Check cloud-init logs
sudo tail -f /var/log/cloud-init-output.log

# Or manually install Docker
curl -fsSL https://get.docker.com -o get-docker.sh
sudo sh get-docker.sh
sudo usermod -aG docker ubuntu
logout
# SSH back in
```

### Problem: "Access Denied" when accessing S3

```bash
# Verify IAM role is attached
curl http://169.254.169.254/latest/meta-data/iam/security-credentials/
# Should output: StarscreenEC2Role

# If empty, role is not attached. Attach it:
# Go to EC2 Console → Instance → Actions → Security → Modify IAM role → Select StarscreenEC2Role
```

### Problem: Containers won't start

```bash
# Check Docker daemon
sudo systemctl status docker

# Check logs
docker-compose logs

# Restart Docker
sudo systemctl restart docker
docker-compose up -d
```

### Problem: Database connection failed

```bash
# Check if database container is running
docker-compose ps

# Check database logs
docker-compose logs db

# Restart database
docker-compose restart db
```

### Problem: Worker not processing resumes

```bash
# Check worker logs
docker-compose logs worker

# Check Redis connection
docker-compose exec worker redis-cli -h redis ping
# Should output: PONG

# Restart worker
docker-compose restart worker
```

---

## Security Checklist

Before going live:

- [ ] Change `POSTGRES_PASSWORD` to strong password
- [ ] Generate new `SECRET_KEY` with `openssl rand -hex 32`
- [ ] Update Stripe keys to production keys
- [ ] Add domain name (not just IP address)
- [ ] Set up HTTPS with Let's Encrypt
- [ ] Remove port 8000 from security group (use Nginx reverse proxy)
- [ ] Enable CloudWatch monitoring
- [ ] Set up automated backups for database

---

## Production Recommendations

### 1. Use Domain Name (Not IP)

- Register domain: `starscreen.com`
- Point A record to EC2 IP: `44.223.41.116`
- Update CORS settings in `.env`

### 2. Set Up HTTPS

```bash
# Install Nginx
sudo apt install nginx

# Install Certbot
sudo apt install certbot python3-certbot-nginx

# Get SSL certificate
sudo certbot --nginx -d starscreen.com -d www.starscreen.com
```

### 3. Nginx Reverse Proxy

```nginx
# /etc/nginx/sites-available/starscreen
server {
    listen 80;
    server_name starscreen.com www.starscreen.com;

    location / {
        proxy_pass http://localhost:8000;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
    }
}
```

### 4. Auto-restart on Reboot

```bash
# Enable Docker service
sudo systemctl enable docker

# Create systemd service for docker-compose
sudo nano /etc/systemd/system/starscreen.service
```

Paste:
```ini
[Unit]
Description=Starscreen Application
Requires=docker.service
After=docker.service

[Service]
Type=oneshot
RemainAfterExit=yes
WorkingDirectory=/home/ubuntu/Resume-Analyzer
ExecStart=/usr/local/bin/docker-compose up -d
ExecStop=/usr/local/bin/docker-compose down
User=ubuntu

[Install]
WantedBy=multi-user.target
```

Enable:
```bash
sudo systemctl enable starscreen
sudo systemctl start starscreen
```

---

## Monitoring

### Check Application Status

```bash
# Container status
docker-compose ps

# Resource usage
docker stats

# API health
curl http://localhost:8000/

# Database connections
docker-compose exec db psql -U starscreen_user -d starscreen_prod -c "SELECT count(*) FROM pg_stat_activity;"
```

### View Logs

```bash
# Last 100 lines
docker-compose logs --tail=100

# Follow logs in real-time
docker-compose logs -f

# Specific service
docker-compose logs -f api
```

---

*Last Updated: 2026-01-01*
*Status: Ready for deployment*
