#!/bin/bash
#
# Local Health Check Script
# Run this script ON your EC2 instance to check local health
# (Different from check_deployment.sh which runs from local machine)
#

set +e  # Don't exit on errors

echo "========================================="
echo "Starscreen Local Health Check (EC2)"
echo "========================================="
echo ""

# Check if running on EC2
if [ -f /sys/hypervisor/uuid ]; then
    UUID=$(cat /sys/hypervisor/uuid 2>/dev/null)
    if [[ "$UUID" == ec2* ]] || [[ "$UUID" == EC2* ]]; then
        echo "Running on EC2 instance ✓"
    fi
else
    echo "⚠️  This script is meant to run ON the EC2 instance"
fi

echo ""
echo "1. Checking disk space..."
df -h / | tail -1 | awk '{
    used=$5+0;
    if(used >= 80) print "   ⚠️  Disk usage: "$5" (HIGH)";
    else if(used >= 60) print "   ⚡ Disk usage: "$5" (moderate)";
    else print "   ✓ Disk usage: "$5
}'

echo ""
echo "2. Checking memory usage..."
free -h | grep Mem | awk '{
    total=$2; used=$3; avail=$7;
    print "   Total: "total", Used: "used", Available: "avail
}'
MEM_PERCENT=$(free | grep Mem | awk '{print int($3/$2 * 100)}')
if [ "$MEM_PERCENT" -ge 80 ]; then
    echo "   ⚠️  Memory usage: ${MEM_PERCENT}% (HIGH)"
elif [ "$MEM_PERCENT" -ge 60 ]; then
    echo "   ⚡ Memory usage: ${MEM_PERCENT}% (moderate)"
else
    echo "   ✓ Memory usage: ${MEM_PERCENT}%"
fi

echo ""
echo "3. Testing local API endpoint..."
API_HEALTH=$(curl -s --connect-timeout 5 http://localhost:8000/api/v1/health/ || echo "failed")
if [[ $API_HEALTH == *"healthy"* ]]; then
    echo "   ✓ Local API is healthy"
    echo "   Response: $API_HEALTH"
else
    echo "   ✗ Local API not responding"
fi

echo ""
echo "4. Testing public HTTPS endpoint..."
HTTPS_HEALTH=$(curl -L -s --connect-timeout 5 https://starscreen.net/api/v1/health/ || echo "failed")
if [[ $HTTPS_HEALTH == *"healthy"* ]]; then
    echo "   ✓ Public HTTPS is healthy"
    echo "   Response: $HTTPS_HEALTH"
else
    echo "   ✗ Public HTTPS not responding"
fi

echo ""
echo "5. Checking Docker containers..."
cd ~/Resume-Analyzer 2>/dev/null || cd /home/ubuntu/Resume-Analyzer 2>/dev/null
if docker-compose ps 2>/dev/null | grep -q "Up"; then
    echo "   ✓ Docker containers running"
    echo ""
    docker-compose ps | grep -E "NAME|Up|Exit"
else
    echo "   ✗ Docker containers not running"
fi

echo ""
echo "6. Checking Docker resource usage..."
docker stats --no-stream --format "table {{.Name}}\t{{.CPUPerc}}\t{{.MemUsage}}\t{{.MemPerc}}" | head -6

echo ""
echo "7. Checking for recent errors in API logs..."
ERRORS=$(docker-compose logs api 2>/dev/null | grep -i error | tail -5)
if [ -z "$ERRORS" ]; then
    echo "   ✓ No recent errors in API logs"
else
    echo "   ⚠️  Recent errors found:"
    echo "$ERRORS" | sed 's/^/     /'
fi

echo ""
echo "8. Database migration status..."
MIGRATION=$(docker-compose exec -T api alembic current 2>/dev/null | grep -v "INFO")
if [ -n "$MIGRATION" ]; then
    echo "   ✓ Current migration: $MIGRATION"
else
    echo "   ✗ Could not check migration status"
fi

echo ""
echo "9. System uptime..."
uptime

echo ""
echo "10. Load average..."
cat /proc/loadavg | awk '{print "   1min: "$1", 5min: "$2", 15min: "$3}'

echo ""
echo "========================================="
if [[ $API_HEALTH == *"healthy"* ]] && [[ $HTTPS_HEALTH == *"healthy"* ]]; then
    echo "✓ All systems operational"
else
    echo "⚠️  Some issues detected"
fi
echo "========================================="
echo ""
echo "For detailed diagnostics from local machine, run:"
echo "  bash check_deployment.sh"
echo ""
