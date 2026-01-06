#!/bin/bash
#
# Test script to verify Redis connection fix
# Run this on your EC2 server after deploying the fix
#

echo "=========================================="
echo "Redis Connection Fix - Verification Script"
echo "=========================================="
echo ""

# Colors for output
GREEN='\033[0;32m'
RED='\033[0;31m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# Test 1: Check if all containers are running
echo "Test 1: Checking container status..."
if docker-compose ps | grep -q "Up"; then
    echo -e "${GREEN}✅ Containers are running${NC}"
    docker-compose ps
else
    echo -e "${RED}❌ Some containers are not running${NC}"
    docker-compose ps
    exit 1
fi
echo ""

# Test 2: Check Redis container health
echo "Test 2: Testing Redis container..."
if docker-compose exec redis redis-cli ping | grep -q "PONG"; then
    echo -e "${GREEN}✅ Redis is healthy${NC}"
else
    echo -e "${RED}❌ Redis is not responding${NC}"
    exit 1
fi
echo ""

# Test 3: Test Redis connection from API container
echo "Test 3: Testing Redis connection from API container..."
API_REDIS_TEST=$(docker-compose exec api python -c "import redis; r = redis.Redis(host='redis', port=6379, db=0); print('CONNECTED' if r.ping() else 'FAILED')" 2>&1)
if echo "$API_REDIS_TEST" | grep -q "CONNECTED"; then
    echo -e "${GREEN}✅ API can connect to Redis${NC}"
else
    echo -e "${RED}❌ API cannot connect to Redis${NC}"
    echo "$API_REDIS_TEST"
    exit 1
fi
echo ""

# Test 4: Test Redis connection from Worker container
echo "Test 4: Testing Redis connection from Worker container..."
WORKER_REDIS_TEST=$(docker-compose exec worker python -c "import redis; r = redis.Redis(host='redis', port=6379, db=0); print('CONNECTED' if r.ping() else 'FAILED')" 2>&1)
if echo "$WORKER_REDIS_TEST" | grep -q "CONNECTED"; then
    echo -e "${GREEN}✅ Worker can connect to Redis${NC}"
else
    echo -e "${RED}❌ Worker cannot connect to Redis${NC}"
    echo "$WORKER_REDIS_TEST"
    exit 1
fi
echo ""

# Test 5: Check for connection errors in recent logs
echo "Test 5: Checking for connection errors in logs..."
CONNECTION_ERRORS=$(docker-compose logs api worker --tail 100 | grep -i "connection refused" | wc -l)
if [ "$CONNECTION_ERRORS" -eq 0 ]; then
    echo -e "${GREEN}✅ No connection errors found in recent logs${NC}"
else
    echo -e "${YELLOW}⚠️  Found $CONNECTION_ERRORS connection error(s) in logs${NC}"
    echo "Recent errors:"
    docker-compose logs api worker --tail 100 | grep -i "connection refused" | tail -5
fi
echo ""

# Test 6: Check for successful Redis connections
echo "Test 6: Checking for successful Redis connection messages..."
SUCCESS_MSGS=$(docker-compose logs api worker --tail 200 | grep -i "redis connection established" | wc -l)
if [ "$SUCCESS_MSGS" -gt 0 ]; then
    echo -e "${GREEN}✅ Found $SUCCESS_MSGS successful Redis connection message(s)${NC}"
    docker-compose logs api worker --tail 200 | grep -i "redis connection established" | tail -3
else
    echo -e "${YELLOW}⚠️  No successful connection messages found (this is OK if containers haven't been restarted recently)${NC}"
fi
echo ""

# Test 7: Test rate limiter module import
echo "Test 7: Testing rate limiter module import..."
IMPORT_TEST=$(docker-compose exec api python -c "from app.core.rate_limiter import rate_limiter; print('IMPORT_SUCCESS')" 2>&1)
if echo "$IMPORT_TEST" | grep -q "IMPORT_SUCCESS"; then
    echo -e "${GREEN}✅ Rate limiter module imports successfully${NC}"
else
    echo -e "${RED}❌ Rate limiter module import failed${NC}"
    echo "$IMPORT_TEST"
    exit 1
fi
echo ""

# Test 8: Test rate limiter initialization (should not create connection at import)
echo "Test 8: Testing lazy connection initialization..."
LAZY_TEST=$(docker-compose exec api python -c "
from app.core.rate_limiter import RateLimiter
rl = RateLimiter()
# At this point, _redis_client should be None (lazy)
if rl._redis_client is None:
    print('LAZY_CONNECTION_OK')
else:
    print('NOT_LAZY')
" 2>&1)
if echo "$LAZY_TEST" | grep -q "LAZY_CONNECTION_OK"; then
    echo -e "${GREEN}✅ Rate limiter uses lazy connection (connection created on-demand)${NC}"
else
    echo -e "${YELLOW}⚠️  Unexpected lazy connection behavior${NC}"
    echo "$LAZY_TEST"
fi
echo ""

# Test 9: Test actual rate limiter functionality
echo "Test 9: Testing rate limiter functionality..."
FUNC_TEST=$(docker-compose exec api python -c "
from app.core.rate_limiter import rate_limiter
import time

# Test basic rate limiting
try:
    rate_limiter.check_rate_limit('test_key', max_requests=2, window_seconds=60)
    rate_limiter.check_rate_limit('test_key', max_requests=2, window_seconds=60)
    print('RATE_LIMITER_WORKS')
    # Clean up
    rate_limiter.reset_limit('test_key')
except Exception as e:
    print(f'ERROR: {e}')
" 2>&1)
if echo "$FUNC_TEST" | grep -q "RATE_LIMITER_WORKS"; then
    echo -e "${GREEN}✅ Rate limiter functionality works correctly${NC}"
else
    echo -e "${RED}❌ Rate limiter functionality test failed${NC}"
    echo "$FUNC_TEST"
    exit 1
fi
echo ""

# Test 10: Check API health
echo "Test 10: Checking API health..."
HEALTH_CHECK=$(curl -s -o /dev/null -w "%{http_code}" http://localhost:8000/api/v1/health 2>/dev/null)
if [ "$HEALTH_CHECK" == "200" ]; then
    echo -e "${GREEN}✅ API health check passed (HTTP 200)${NC}"
elif [ -z "$HEALTH_CHECK" ]; then
    echo -e "${YELLOW}⚠️  Could not reach API health endpoint (curl might not be available)${NC}"
else
    echo -e "${YELLOW}⚠️  API health check returned HTTP $HEALTH_CHECK${NC}"
fi
echo ""

# Summary
echo "=========================================="
echo "Summary"
echo "=========================================="
echo -e "${GREEN}All critical tests passed!${NC}"
echo ""
echo "Next steps:"
echo "1. Monitor logs for any Redis connection issues:"
echo "   docker-compose logs -f api worker"
echo ""
echo "2. Test the verification endpoint:"
echo "   Watch logs while triggering /api/v1/auth/resend-verification-code"
echo "   Should return 200 OK or 429 (not 500)"
echo ""
echo "3. If issues persist, check:"
echo "   - Redis container logs: docker-compose logs redis"
echo "   - Network connectivity: docker-compose exec api ping redis"
echo "   - Environment variables: docker-compose exec api env | grep REDIS"
