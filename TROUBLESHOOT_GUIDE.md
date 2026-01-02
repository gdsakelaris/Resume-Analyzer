# Troubleshooting Guide - Verification Endpoint Issues

## Current Issues

1. ❌ Internal server error when resending verification code
2. ❌ "Unauthorized" error messages

## Step-by-Step Debugging

### Step 1: Wait for GitHub Actions Deploy

```bash
# Check deployment status
# Go to: https://github.com/gdsakelaris/Resume-Analyzer/actions
# Wait for green checkmark (deployment complete)
```

### Step 2: SSH into Server

```bash
ssh -i ~/starscreen-key.pem ubuntu@ip-172-31-76-2
cd ~/Resume-Analyzer
```

### Step 3: Check Container Status

```bash
docker-compose ps
```

All containers should show "Up". If any are down:
```bash
docker-compose up -d
```

### Step 4: Check for Errors in Recent Logs

```bash
chmod +x check_api_errors.sh
./check_api_errors.sh
```

This will show you:
- Recent API errors
- Verification endpoint errors
- Redis connection issues
- 500 errors
- Unauthorized (401) errors

### Step 5: Test Redis Connection

```bash
# Test Redis from API container
docker-compose exec api python -c "
from app.core.rate_limiter import rate_limiter
print('Testing rate limiter...')
try:
    rate_limiter.check_rate_limit('test_key', max_requests=5, window_seconds=60)
    print('✅ Rate limiter works! Redis connection is good.')
    rate_limiter.reset_limit('test_key')
except Exception as e:
    print(f'❌ Error: {e}')
    import traceback
    traceback.print_exc()
"
```

### Step 6: Watch Logs in Real-Time

```bash
# Open a terminal and watch API logs
docker-compose logs -f api

# Then try to resend verification code from your browser
# Watch for errors in the logs
```

### Step 7: Common Issues and Fixes

#### Issue: "ConnectionRefusedError: [Errno 111] Connection refused"

**Cause:** Redis connection failing

**Fix:**
```bash
# Restart containers
docker-compose restart api worker redis

# Wait 30 seconds
sleep 30

# Test again
docker-compose exec api python -c "import redis; r = redis.Redis(host='redis', port=6379); print(r.ping())"
```

#### Issue: "401 Unauthorized"

**Cause:** Token expired or invalid

**Solution:** Have the user logout and login again
```javascript
// In browser console:
localStorage.clear()
window.location.href = '/static/login.html'
```

#### Issue: "500 Internal Server Error" on resend-verification-code

**Possible Causes:**
1. Redis connection failed
2. Rate limiter error
3. Email sending error (Celery/SES)
4. Database connection issue

**Debug:**
```bash
# Check last 500 error details
docker-compose logs api --tail 200 | grep -A 20 "500 Internal Server Error" | tail -30

# Check Python traceback
docker-compose logs api --tail 300 | grep -B 5 -A 15 "Traceback"
```

### Step 8: Test Email Verification Flow End-to-End

```bash
# Check if Celery worker is processing tasks
docker-compose logs worker --tail 50

# Check for email task errors
docker-compose logs worker --tail 100 | grep -i "email\|error"

# Check SES configuration
docker-compose exec api python -c "
from app.core.config import settings
print(f'AWS_SES_FROM_EMAIL: {settings.AWS_SES_FROM_EMAIL}')
print(f'AWS_SES_FROM_NAME: {settings.AWS_SES_FROM_NAME}')
print(f'AWS_REGION: {settings.AWS_REGION}')
"
```

### Step 9: Check Database Connection

```bash
# Test database connection
docker-compose exec api python -c "
from app.core.database import SessionLocal
try:
    db = SessionLocal()
    result = db.execute('SELECT 1').scalar()
    print(f'✅ Database connection works: {result}')
    db.close()
except Exception as e:
    print(f'❌ Database error: {e}')
"
```

### Step 10: Full System Restart (If All Else Fails)

```bash
# Stop everything
docker-compose down

# Remove old containers
docker-compose rm -f

# Start fresh
docker-compose up -d --build

# Wait for containers to be healthy
sleep 60

# Check status
docker-compose ps

# Watch logs
docker-compose logs -f
```

## Specific Error Messages and Solutions

### Error: "Too many requests"

This is actually **working correctly**! The rate limiter is protecting the endpoint.

**Wait time:** 2 minutes between resend requests

### Error: "Verification code expired"

User needs to request a new code. Codes expire after 15 minutes.

### Error: "Invalid verification code"

User entered wrong code. They have 10 attempts per 10 minutes.

## Getting Detailed Error Info

Run this to get the full error with stack trace:

```bash
# Show last API error with full traceback
docker-compose logs api --tail 500 > /tmp/api_logs.txt

# Search for the error
grep -A 30 "Traceback\|Error\|Exception" /tmp/api_logs.txt | tail -50

# Or view the file
less /tmp/api_logs.txt
# Press / to search, type "error" or "exception"
# Press n for next match
# Press q to quit
```

## Quick Health Check

Run all these commands to get a full health report:

```bash
#!/bin/bash
echo "=== HEALTH CHECK ==="
echo ""
echo "1. Containers:"
docker-compose ps
echo ""
echo "2. Redis:"
docker-compose exec redis redis-cli ping
echo ""
echo "3. Database:"
docker-compose exec db psql -U starscreen_user -d starscreen_prod -c "SELECT 1 as healthy;"
echo ""
echo "4. API Health:"
curl -f http://localhost:8000/api/v1/health || echo "Health endpoint failed"
echo ""
echo "5. Recent Errors:"
docker-compose logs api worker --tail 50 | grep -i "error\|exception" | tail -10
echo ""
echo "=== END HEALTH CHECK ==="
```

## After Fixing

Once you fix the issue:

1. Test the verification flow
2. Monitor logs for 5-10 minutes
3. Try these test cases:
   - Register new user
   - Resend verification code
   - Enter wrong code (should fail gracefully)
   - Enter correct code (should succeed)
   - Try resending too quickly (should see rate limit)

## Need More Help?

If none of these steps work, gather this information:

```bash
# Create a debug report
cat > /tmp/debug_report.txt << 'EOF'
=== SYSTEM INFO ===
EOF

docker-compose ps >> /tmp/debug_report.txt
echo "" >> /tmp/debug_report.txt

echo "=== API LOGS ===" >> /tmp/debug_report.txt
docker-compose logs api --tail 200 >> /tmp/debug_report.txt
echo "" >> /tmp/debug_report.txt

echo "=== WORKER LOGS ===" >> /tmp/debug_report.txt
docker-compose logs worker --tail 200 >> /tmp/debug_report.txt
echo "" >> /tmp/debug_report.txt

echo "=== REDIS LOGS ===" >> /tmp/debug_report.txt
docker-compose logs redis --tail 100 >> /tmp/debug_report.txt

echo "Report saved to /tmp/debug_report.txt"
cat /tmp/debug_report.txt
```

Then review the report or share relevant excerpts.
