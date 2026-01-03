# Redis Connection Fix Instructions

## Problem
The application is experiencing Redis connection failures with the error:
```
ConnectionRefusedError: [Errno 111] Connection refused
```

This happens because:
1. The RateLimiter creates a Redis connection when the module loads
2. Redis might not be ready when the API container starts
3. No retry logic exists if the initial connection fails
4. The connection isn't validated before use

## Solution
Implement lazy connection with retry logic and connection health checks.

## Commands to Run on Your Server

1. **Upload the fixed rate_limiter.py file to your server:**
   ```bash
   scp -i ~/starscreen-key.pem rate_limiter_fixed.py ubuntu@ip-172-31-76-2:~/Resume-Analyzer/app/core/rate_limiter.py
   ```

2. **SSH into your server:**
   ```bash
   ssh -i ~/starscreen-key.pem ubuntu@ip-172-31-76-2
   ```

3. **Navigate to the project directory:**
   ```bash
   cd ~/Resume-Analyzer
   ```

4. **Rebuild and restart the containers:**
   ```bash
   docker-compose down
   docker-compose build --no-cache api worker
   docker-compose up -d
   ```

5. **Monitor the logs:**
   ```bash
   # Watch all logs
   docker-compose logs -f

   # Or watch specific services
   docker-compose logs -f api worker redis
   ```

6. **Test Redis connectivity:**
   ```bash
   # Test from API container
   docker-compose exec api python -c "import redis; r = redis.Redis(host='redis', port=6379, db=0); print('Redis ping:', r.ping())"

   # Test from worker container
   docker-compose exec worker python -c "import redis; r = redis.Redis(host='redis', port=6379, db=0); print('Redis ping:', r.ping())"
   ```

7. **Test the verification endpoint:**
   ```bash
   # Check recent logs for the endpoint
   docker-compose logs api --tail 100 | grep "resend-verification"
   ```

## Verification Steps

After applying the fix, verify:
- ✅ All containers are running: `docker-compose ps`
- ✅ No connection errors in logs: `docker-compose logs api | grep -i "connection refused"`
- ✅ Redis is accessible: `docker-compose exec redis redis-cli ping`
- ✅ API can connect to Redis: See test command above
- ✅ The `/api/v1/auth/resend-verification-code` endpoint returns 200 or 429 (not 500)

## Alternative Quick Fix (If file upload doesn't work)

You can also manually edit the file on the server:

```bash
ssh -i ~/starscreen-key.pem ubuntu@ip-172-31-76-2
cd ~/Resume-Analyzer
nano app/core/rate_limiter.py
# Paste the fixed code
# Press Ctrl+X, then Y, then Enter to save

# Restart containers
docker-compose restart api worker
```
