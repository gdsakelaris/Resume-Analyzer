#!/bin/bash
# Deployment check and troubleshooting script for Starscreen

set +e  # Don't exit on errors - we want to see all diagnostics

INSTANCE_IP="54.158.113.25"
SSH_KEY="starsceen_key.pem"
SSH_OPTS="-o ConnectTimeout=10 -o StrictHostKeyChecking=no"

echo "========================================"
echo "Starscreen Deployment Health Check"
echo "========================================"
echo ""

# Test network connectivity first
echo "1. Testing network connectivity to EC2..."
if ping -n 1 -w 3000 $INSTANCE_IP > /dev/null 2>&1; then
    echo "   ✓ Network reachable"
else
    echo "   ✗ Cannot ping EC2 (may be blocked by firewall)"
fi

# Test SSH connectivity
echo ""
echo "2. Testing SSH connectivity..."
if ssh -i "$SSH_KEY" $SSH_OPTS ubuntu@$INSTANCE_IP 'echo "SSH works"' 2>/dev/null; then
    echo "   ✓ SSH connection successful"
    SSH_WORKS=true
else
    echo "   ✗ SSH connection failed - EC2 may be down"
    SSH_WORKS=false
fi

# Test HTTPS endpoint
echo ""
echo "3. Testing HTTPS endpoint..."
HTTP_CODE=$(curl -s -o /dev/null -w "%{http_code}" --connect-timeout 10 https://starscreen.net 2>/dev/null || echo "000")
if [ "$HTTP_CODE" = "200" ] || [ "$HTTP_CODE" = "307" ] || [ "$HTTP_CODE" = "308" ]; then
    echo "   ✓ HTTPS responding (HTTP $HTTP_CODE)"
else
    echo "   ✗ HTTPS not responding (HTTP $HTTP_CODE)"
fi

# Test API health endpoint
echo ""
echo "4. Testing API health endpoint..."
API_HEALTH=$(curl -s --connect-timeout 10 https://starscreen.net/api/v1/health/ 2>/dev/null || echo "failed")
if [[ $API_HEALTH == *"healthy"* ]] || [[ $API_HEALTH == *"status"* ]]; then
    echo "   ✓ API is healthy"
    echo "   Response: $API_HEALTH"
else
    echo "   ✗ API health check failed"
fi

# If SSH works, do detailed checks
if [ "$SSH_WORKS" = true ]; then
    echo ""
    echo "========================================"
    echo "EC2 Detailed Diagnostics"
    echo "========================================"

    echo ""
    echo "5. Checking Docker containers status..."
    ssh -i "$SSH_KEY" $SSH_OPTS ubuntu@$INSTANCE_IP "cd ~/Resume-Analyzer && docker-compose ps" 2>/dev/null || echo "   ✗ Failed to check containers"

    echo ""
    echo "6. Checking disk space..."
    ssh -i "$SSH_KEY" $SSH_OPTS ubuntu@$INSTANCE_IP "df -h /" 2>/dev/null || echo "   ✗ Failed to check disk"

    echo ""
    echo "7. Checking memory usage..."
    ssh -i "$SSH_KEY" $SSH_OPTS ubuntu@$INSTANCE_IP "free -h" 2>/dev/null || echo "   ✗ Failed to check memory"

    echo ""
    echo "8. Recent API logs (last 20 lines)..."
    ssh -i "$SSH_KEY" $SSH_OPTS ubuntu@$INSTANCE_IP "cd ~/Resume-Analyzer && docker-compose logs --tail=20 api" 2>/dev/null || echo "   ✗ Failed to get API logs"

    echo ""
    echo "9. Recent worker logs (last 20 lines)..."
    ssh -i "$SSH_KEY" $SSH_OPTS ubuntu@$INSTANCE_IP "cd ~/Resume-Analyzer && docker-compose logs --tail=20 worker" 2>/dev/null || echo "   ✗ Failed to get worker logs"

    echo ""
    echo "10. Database migration status..."
    ssh -i "$SSH_KEY" $SSH_OPTS ubuntu@$INSTANCE_IP "cd ~/Resume-Analyzer && docker-compose exec -T api alembic current" 2>/dev/null || echo "   ✗ Failed to check migrations"

    echo ""
    echo "11. Recent errors in API logs..."
    ssh -i "$SSH_KEY" $SSH_OPTS ubuntu@$INSTANCE_IP "cd ~/Resume-Analyzer && docker-compose logs api 2>/dev/null | grep -i error | tail -10" || echo "   No recent errors found"

    echo ""
    echo "12. Container resource usage..."
    ssh -i "$SSH_KEY" $SSH_OPTS ubuntu@$INSTANCE_IP "docker stats --no-stream" 2>/dev/null || echo "   ✗ Failed to get container stats"

else
    echo ""
    echo "========================================"
    echo "⚠️  Cannot SSH to EC2"
    echo "========================================"
    echo ""
    echo "Possible causes:"
    echo "  1. EC2 instance is stopped or terminated"
    echo "  2. EC2 instance is frozen/hung"
    echo "  3. Security group blocking SSH"
    echo "  4. Network connectivity issue"
    echo ""
    echo "To fix:"
    echo "  1. Check EC2 instance state in AWS Console"
    echo "  2. Reboot the instance if frozen"
    echo "  3. Check security group allows port 22"
    echo ""
    echo "AWS Console:"
    echo "https://console.aws.amazon.com/ec2/home?region=us-east-1#Instances:instanceId=i-081c728682b8917d2"
fi

echo ""
echo "========================================"
echo "GitHub Actions Status"
echo "========================================"
echo "Check latest deployment:"
echo "https://github.com/gdsakelaris/Resume-Analyzer/actions"
echo ""

echo "Done!"
