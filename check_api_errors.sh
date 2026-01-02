#!/bin/bash
echo "=== Checking for resend-verification errors ==="
docker-compose logs api --tail 200 | grep -A 10 -B 5 "resend-verification"

echo ""
echo "=== Checking for 500 errors ==="
docker-compose logs api --tail 100 | grep -A 10 "500 Internal Server Error"

echo ""
echo "=== Checking for unauthorized errors ==="
docker-compose logs api --tail 100 | grep -A 5 -i "unauthorized\|401"

echo ""
echo "=== Checking Redis errors ==="
docker-compose logs api worker --tail 100 | grep -i "redis\|connection"

echo ""
echo "=== Testing rate limiter directly ==="
docker-compose exec -T api python -c "
import sys
import traceback

try:
    print('1. Importing rate_limiter...')
    from app.core.rate_limiter import rate_limiter
    print('✅ Import successful')

    print('\n2. Testing rate limiter...')
    rate_limiter.check_rate_limit('test_key', max_requests=5, window_seconds=60)
    print('✅ Rate limiter works!')

    print('\n3. Cleaning up...')
    rate_limiter.reset_limit('test_key')
    print('✅ Test complete')

except Exception as e:
    print(f'\n❌ Error: {e}')
    print('\nFull traceback:')
    traceback.print_exc()
    sys.exit(1)
"
