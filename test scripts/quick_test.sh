#!/bin/bash
#
# Quick test to trigger Redis connection and verify fix
#

echo "=========================================="
echo "Quick Redis Connection Test"
echo "=========================================="
echo ""

# Test 1: Verify containers are running
echo "1. Container Status:"
docker-compose ps | grep -E "api|worker|redis"
echo ""

# Test 2: Test Redis is accessible
echo "2. Redis Health:"
docker-compose exec redis redis-cli ping
echo ""

# Test 3: Test direct Redis connection from API
echo "3. Direct Redis Connection from API:"
docker-compose exec api python -c "
import redis
from app.core.config import settings
r = redis.Redis(host=settings.REDIS_HOST, port=settings.REDIS_PORT, db=settings.REDIS_DB)
print('✅ Redis ping:', r.ping())
"
echo ""

# Test 4: Test rate limiter module (this will trigger the lazy connection)
echo "4. Testing Rate Limiter (triggers lazy connection):"
docker-compose exec api python -c "
from app.core.rate_limiter import rate_limiter
print('Rate limiter initialized')

# This will trigger the lazy connection
try:
    rate_limiter.check_rate_limit('test_key', max_requests=5, window_seconds=60)
    print('✅ Rate limiter works! Redis connection established.')
    # Clean up
    rate_limiter.reset_limit('test_key')
except Exception as e:
    print(f'❌ Error: {e}')
"
echo ""

# Test 5: Now check for the connection message in logs
echo "5. Checking for Redis connection messages in logs:"
docker-compose logs api --tail 50 | grep -i "redis connection" || echo "(Connection might have been established before logging)"
echo ""

# Test 6: Check for any connection errors
echo "6. Checking for connection errors:"
ERRORS=$(docker-compose logs api worker --tail 100 | grep -i "connection refused" | wc -l)
if [ "$ERRORS" -eq 0 ]; then
    echo "✅ No connection errors found!"
else
    echo "❌ Found $ERRORS connection error(s)"
fi
echo ""

echo "=========================================="
echo "Test complete!"
echo "=========================================="
echo ""
echo "Now run the full test suite:"
echo "  ./test_redis_fix.sh"
