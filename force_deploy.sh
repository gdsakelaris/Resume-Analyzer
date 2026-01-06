#!/bin/bash
# Force rebuild and restart on EC2

echo "Forcing rebuild on EC2..."

ssh -o StrictHostKeyChecking=no -i "C:\Users\gdsak\OneDrive\Desktop\starsceen_key.pem" ubuntu@13.59.165.211 << 'SSH_EOF'
cd ~/Resume-Analyzer

echo "1. Checking current deployed version..."
git log --oneline -1

echo -e "\n2. Pulling latest code..."
git pull origin main

echo -e "\n3. Checking if fix is deployed..."
grep "foreign_keys" app/models/user.py

echo -e "\n4. Force rebuild all containers..."
docker-compose down
docker-compose up -d --build --force-recreate

echo -e "\n5. Waiting for containers to start..."
sleep 10

echo -e "\n6. Container status..."
docker-compose ps

echo -e "\n7. Checking API logs..."
docker-compose logs api --tail 30
SSH_EOF

echo -e "\nDeployment forced. Check logs above for any errors."
