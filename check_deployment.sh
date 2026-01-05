#!/bin/bash
# Quick deployment check script for Starscreen

echo "=== Checking GitHub Actions Deployment ==="
echo "Visit: https://github.com/gdsakelaris/Resume-Analyzer/actions"
echo ""

echo "=== Checking EC2 Container Status ==="
ssh starscreen "cd ~/Resume-Analyzer && docker-compose ps"
echo ""

echo "=== Checking Recent Logs (last 30 lines) ==="
echo "--- API Logs ---"
ssh starscreen "cd ~/Resume-Analyzer && docker-compose logs --tail=30 api"
echo ""

echo "--- Worker Logs ---"
ssh starscreen "cd ~/Resume-Analyzer && docker-compose logs --tail=30 worker"
echo ""

echo "=== Checking Database Migration Status ==="
ssh starscreen "cd ~/Resume-Analyzer && docker-compose exec -T api alembic current"
echo ""

echo "=== Recent API Errors (if any) ==="
ssh starscreen "cd ~/Resume-Analyzer && docker-compose logs api | grep -i error | tail -10"
echo ""
