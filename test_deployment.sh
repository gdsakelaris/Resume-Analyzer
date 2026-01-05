#!/bin/bash
# Quick test script to check if deployment is working

echo "Testing EC2 connectivity..."
echo ""

echo "1. Testing HTTPS endpoint..."
HTTP_CODE=$(curl -s -o /dev/null -w "%{http_code}" --connect-timeout 10 https://starscreen.net)
if [ "$HTTP_CODE" = "200" ] || [ "$HTTP_CODE" = "307" ] || [ "$HTTP_CODE" = "308" ] || [ "$HTTP_CODE" = "405" ]; then
    echo "   ✓ Server is responding (HTTP $HTTP_CODE)"
else
    echo "   ✗ Server not responding (HTTP $HTTP_CODE)"
fi

echo ""
echo "2. Testing API health endpoint..."
HEALTH=$(curl -L -s --connect-timeout 10 https://starscreen.net/api/v1/health/)
if [[ $HEALTH == *"healthy"* ]] || [[ $HEALTH == *"status"* ]]; then
    echo "   ✓ API is healthy"
    echo "   Response: $HEALTH"
else
    echo "   ✗ API health check failed"
    echo "   Response: $HEALTH"
fi

echo ""
echo "3. Testing SSH connection (from local machine only)..."
if [ -f "starsceen_key.pem" ]; then
    # Fix permissions if on Linux/Mac
    chmod 400 starsceen_key.pem 2>/dev/null || echo "   (Skip permission fix on Windows)"

    ssh -i "starsceen_key.pem" -o ConnectTimeout=10 -o StrictHostKeyChecking=no ubuntu@54.158.113.25 'echo "✓ SSH works"' 2>&1 | grep -v "Warning" | grep -v "@@@" | grep -v "UNPROTECTED"
else
    echo "   ⊘ SSH key not found (run this from project root)"
fi

echo ""
echo "4. Testing Docker containers (via SSH)..."
if [ -f "starsceen_key.pem" ]; then
    ssh -i "starsceen_key.pem" -o ConnectTimeout=10 -o StrictHostKeyChecking=no ubuntu@54.158.113.25 'cd ~/Resume-Analyzer && docker-compose ps' 2>/dev/null | grep -E "Name|api|worker|db|redis" || echo "   ✗ Cannot check containers"
else
    echo "   ⊘ Skipped (no SSH key)"
fi

echo ""
echo "========================================="
if [[ $HEALTH == *"healthy"* ]]; then
    echo "✓ Deployment is working!"
else
    echo "⚠ Deployment may have issues"
fi
echo "========================================="
