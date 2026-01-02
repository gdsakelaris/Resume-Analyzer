# Deploy Redis Connection Fix - Quick Guide

## What Was Fixed

Fixed Redis connection issues causing 500 errors on `/api/v1/auth/resend-verification-code` endpoint.

**Error before fix:**
```
ConnectionRefusedError: [Errno 111] Connection refused
INFO: "POST /api/v1/auth/resend-verification-code HTTP/1.1" 500 Internal Server Error
```

**After fix:**
- Lazy Redis connection (connects on-demand, not at import time)
- Automatic retry logic (5 attempts with 1-second delay)
- Health checks (validates connections are still alive)
- Self-healing (reconnects automatically if connection dies)

## Files Changed

- ✅ [app/core/rate_limiter.py](app/core/rate_limiter.py) - **MAIN FIX**

## Deployment (Choose ONE method)

### Method 1: Git Push & Pull (Recommended) ⭐

On your **local Windows machine**:

```powershell
cd c:\Users\gdsak_ukfkfpt\Desktop\Resume-Analyzer

# Commit the fix
git add app/core/rate_limiter.py
git commit -m "Fix Redis connection with lazy initialization and retry logic

- Changed from eager to lazy Redis connection initialization
- Added retry logic (5 attempts with 1s delay between retries)
- Added connection health checks with automatic reconnection
- Improved timeout and error handling configuration

Fixes: ConnectionRefusedError on verification endpoints"

git push origin main
```

On your **EC2 server** (using PuTTY or terminal):

```bash
# SSH into your server
ssh -i ~/starscreen-key.pem ubuntu@ip-172-31-76-2

# Navigate to project
cd ~/Resume-Analyzer

# Pull the changes
git pull origin main

# Rebuild containers (to ensure Python code is refreshed)
docker-compose down
docker-compose build --no-cache api worker
docker-compose up -d

# Watch logs to verify fix
docker-compose logs -f api worker
```

**Look for this in the logs:**
```
✅ Redis connection established (attempt 1/5)
```

### Method 2: Direct File Copy

From your **local Windows machine**:

```powershell
# Copy the fixed file to server
scp -i c:\Users\gdsak_ukfkfpt\Desktop\starscreen-key.pem ^
    c:\Users\gdsak_ukfkfpt\Desktop\Resume-Analyzer\app\core\rate_limiter.py ^
    ubuntu@ip-172-31-76-2:~/Resume-Analyzer/app/core/rate_limiter.py
```

Then on your **EC2 server**:

```bash
ssh -i ~/starscreen-key.pem ubuntu@ip-172-31-76-2
cd ~/Resume-Analyzer

# Restart containers to load new code
docker-compose restart api worker

# Verify
docker-compose logs -f api worker
```

### Method 3: Manual Edit on Server

```bash
# SSH into server
ssh -i ~/starscreen-key.pem ubuntu@ip-172-31-76-2
cd ~/Resume-Analyzer

# Backup original
cp app/core/rate_limiter.py app/core/rate_limiter_backup.py

# Edit the file
nano app/core/rate_limiter.py
# (Copy-paste the new code from the fixed version)
# Press Ctrl+X, then Y, then Enter to save

# Restart
docker-compose restart api worker
docker-compose logs -f api worker
```

## Verification Steps

### Quick Test (30 seconds)

```bash
# On your EC2 server

# 1. Check containers
docker-compose ps
# All should show "Up"

# 2. Test Redis from API
docker-compose exec api python -c "import redis; r = redis.Redis(host='redis', port=6379, db=0); print('Redis OK:', r.ping())"
# Should print: Redis OK: True

# 3. Check for errors
docker-compose logs api --tail 50 | grep -i "connection refused"
# Should be empty (no output)

# 4. Look for success message
docker-compose logs api --tail 100 | grep -i "redis connection"
# Should show: ✅ Redis connection established
```

### Full Test (2 minutes)

```bash
# Make the test script executable and run it
chmod +x test_redis_fix.sh
./test_redis_fix.sh
```

This will run 10 automated tests and give you a detailed report.

## Expected Results

### ✅ Good Signs

In your logs, you should see:
```
✅ Redis connection established (attempt 1/5)
INFO: "POST /api/v1/auth/resend-verification-code HTTP/1.1" 200 OK
INFO: "POST /api/v1/auth/resend-verification-code HTTP/1.1" 429 Too Many Requests
```

### ❌ Bad Signs (Should NOT appear)

These should be gone:
```
❌ ConnectionRefusedError: [Errno 111] Connection refused
❌ kombu.exceptions.OperationalError
❌ INFO: "POST /api/v1/auth/resend-verification-code HTTP/1.1" 500 Internal Server Error
```

## Rollback (If Needed)

If something goes wrong, you can quickly rollback:

```bash
# On EC2 server
cd ~/Resume-Analyzer

# Option 1: Git rollback
git log --oneline -5  # Find the commit hash before your fix
git revert <commit-hash>
docker-compose restart api worker

# Option 2: Use backup
cp app/core/rate_limiter_backup.py app/core/rate_limiter.py
docker-compose restart api worker
```

## Monitoring

After deployment, monitor for 5-10 minutes:

```bash
# Watch all logs
docker-compose logs -f

# Or watch specific services
docker-compose logs -f api worker redis

# Filter for verification endpoint
docker-compose logs -f api | grep "verification"

# Filter for Redis messages
docker-compose logs -f api worker | grep -i redis
```

## Support

If you encounter issues:

1. **Check container status:**
   ```bash
   docker-compose ps
   ```

2. **Check Redis health:**
   ```bash
   docker-compose exec redis redis-cli ping
   ```

3. **Check network connectivity:**
   ```bash
   docker-compose exec api ping -c 3 redis
   ```

4. **Check environment variables:**
   ```bash
   docker-compose exec api env | grep REDIS
   ```

5. **Full restart:**
   ```bash
   docker-compose down
   docker-compose up -d
   docker-compose logs -f
   ```

## Related Documentation

- [REDIS_FIX_SUMMARY.md](REDIS_FIX_SUMMARY.md) - Detailed technical explanation
- [REDIS_FIX_INSTRUCTIONS.md](REDIS_FIX_INSTRUCTIONS.md) - Alternative deployment instructions
- [test_redis_fix.sh](test_redis_fix.sh) - Automated verification script

## Success Criteria

Deployment is successful when:

- ✅ All containers are running (`docker-compose ps`)
- ✅ Redis is accessible from API and Worker containers
- ✅ No "Connection refused" errors in logs
- ✅ Verification endpoints return 200/429 instead of 500
- ✅ You see "✅ Redis connection established" in logs
