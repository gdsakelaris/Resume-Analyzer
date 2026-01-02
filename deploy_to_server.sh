#!/bin/bash
#
# Deployment script for Redis connection fix
# Run this script on your EC2 server
#

set -e  # Exit on error

echo "=========================================="
echo "Deploying Redis Connection Fix"
echo "=========================================="
echo ""

# Colors
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m'

# Navigate to project directory
cd ~/Resume-Analyzer

echo -e "${BLUE}Step 1: Pulling latest code from GitHub...${NC}"
git pull origin main
echo -e "${GREEN}✅ Code updated${NC}"
echo ""

echo -e "${BLUE}Step 2: Stopping containers...${NC}"
docker-compose down
echo -e "${GREEN}✅ Containers stopped${NC}"
echo ""

echo -e "${BLUE}Step 3: Rebuilding API and Worker containers...${NC}"
docker-compose build --no-cache api worker
echo -e "${GREEN}✅ Containers rebuilt${NC}"
echo ""

echo -e "${BLUE}Step 4: Starting all services...${NC}"
docker-compose up -d
echo -e "${GREEN}✅ Services started${NC}"
echo ""

echo -e "${BLUE}Step 5: Waiting for containers to be healthy (30 seconds)...${NC}"
sleep 30
echo -e "${GREEN}✅ Wait complete${NC}"
echo ""

echo -e "${BLUE}Step 6: Checking container status...${NC}"
docker-compose ps
echo ""

echo -e "${BLUE}Step 7: Testing Redis connection from API...${NC}"
docker-compose exec -T api python -c "import redis; r = redis.Redis(host='redis', port=6379, db=0); print('✅ API -> Redis: CONNECTED' if r.ping() else '❌ FAILED')"
echo ""

echo -e "${BLUE}Step 8: Testing Redis connection from Worker...${NC}"
docker-compose exec -T worker python -c "import redis; r = redis.Redis(host='redis', port=6379, db=0); print('✅ Worker -> Redis: CONNECTED' if r.ping() else '❌ FAILED')"
echo ""

echo -e "${BLUE}Step 9: Checking for connection errors...${NC}"
ERROR_COUNT=$(docker-compose logs api worker --tail 100 | grep -c "connection refused" || true)
if [ "$ERROR_COUNT" -eq 0 ]; then
    echo -e "${GREEN}✅ No connection errors found${NC}"
else
    echo -e "${YELLOW}⚠️  Found $ERROR_COUNT connection error(s)${NC}"
fi
echo ""

echo -e "${BLUE}Step 10: Looking for successful connection messages...${NC}"
docker-compose logs api worker --tail 100 | grep -i "redis connection established" | tail -3 || echo -e "${YELLOW}(No messages yet - this is normal, will appear on first request)${NC}"
echo ""

echo "=========================================="
echo -e "${GREEN}Deployment Complete!${NC}"
echo "=========================================="
echo ""
echo "Monitor logs with:"
echo "  docker-compose logs -f api worker"
echo ""
echo "Run full test suite:"
echo "  chmod +x test_redis_fix.sh && ./test_redis_fix.sh"
echo ""
