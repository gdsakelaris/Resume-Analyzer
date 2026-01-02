#!/bin/bash
#
# Debug verification endpoint errors
#

echo "=========================================="
echo "Debugging Verification Endpoint Errors"
echo "=========================================="
echo ""

echo "1. Recent API errors (last 100 lines):"
echo "--------------------------------------"
docker-compose logs api --tail 100 | grep -i "error\|exception\|traceback" | tail -20
echo ""

echo "2. Verification endpoint logs:"
echo "--------------------------------------"
docker-compose logs api --tail 100 | grep -i "verification"
echo ""

echo "3. Redis connection errors:"
echo "--------------------------------------"
docker-compose logs api worker --tail 100 | grep -i "redis\|connection refused"
echo ""

echo "4. Recent 500 errors:"
echo "--------------------------------------"
docker-compose logs api --tail 100 | grep "500 Internal Server Error"
echo ""

echo "5. Full traceback of last error:"
echo "--------------------------------------"
docker-compose logs api --tail 200
echo ""

echo "6. Test Redis connection:"
echo "--------------------------------------"
docker-compose exec api python -c "
import redis
from app.core.config import settings
try:
    r = redis.Redis(host=settings.REDIS_HOST, port=settings.REDIS_PORT, db=settings.REDIS_DB)
    print('Redis ping:', r.ping())
except Exception as e:
    print(f'Redis error: {e}')
"
echo ""

echo "7. Test rate limiter import:"
echo "--------------------------------------"
docker-compose exec api python -c "
try:
    from app.core.rate_limiter import rate_limiter
    print('✅ Rate limiter imported successfully')
except Exception as e:
    print(f'❌ Import error: {e}')
    import traceback
    traceback.print_exc()
"
echo ""
