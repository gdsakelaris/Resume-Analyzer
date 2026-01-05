#!/bin/bash
# Quick test script to check if deployment is working

echo "Testing EC2 connectivity..."
echo ""

echo "1. Testing SSH connection..."
ssh -i "starsceen_key.pem" -o ConnectTimeout=10 ubuntu@54.158.113.25 'echo "✓ SSH works"' 2>&1

echo ""
echo "2. Testing HTTPS endpoint..."
curl -I --connect-timeout 10 https://starscreen.net 2>&1 | head -5

echo ""
echo "3. Testing API health..."
curl --connect-timeout 10 https://starscreen.net/api/v1/health/ 2>&1 | head -10

echo ""
echo "If all tests pass, your deployment is working!"
