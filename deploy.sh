#!/bin/bash
# Auto-deployment script for Resume-Analyzer
# This script pulls latest changes from GitHub and restarts services

set -e  # Exit on any error

echo "=========================================="
echo "Starting auto-deployment..."
echo "Time: $(date)"
echo "=========================================="

# Navigate to project directory
cd /home/ubuntu/Resume-Analyzer

# Pull latest changes from GitHub
echo "Pulling latest changes from GitHub..."
git pull origin main

# Restart Docker services
echo "Restarting Docker services..."
docker-compose restart api

echo "=========================================="
echo "Deployment completed successfully!"
echo "Time: $(date)"
echo "=========================================="
