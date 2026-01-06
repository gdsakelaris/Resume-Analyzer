#!/bin/bash
# Complete LinkedIn integration setup on EC2

echo "=========================================="
echo "LinkedIn Integration Setup"
echo "=========================================="

ssh -i "C:\Users\gdsak\OneDrive\Desktop\starsceen_key.pem" ubuntu@13.59.165.211 << 'SSH_EOF'
cd ~/Resume-Analyzer

echo -e "\n1. Pulling latest code from GitHub..."
git pull origin main

echo -e "\n2. Checking current code version..."
git log --oneline -1

echo -e "\n3. Verifying foreign_keys fix is deployed..."
grep -A 3 "oauth_connections" app/models/user.py | head -5

echo -e "\n4. Rebuilding containers with latest code..."
docker-compose up -d --build

echo -e "\n5. Waiting for containers to start..."
sleep 15

echo -e "\n6. Running database migration..."
docker-compose exec -T api alembic upgrade head

echo -e "\n7. Checking migration status..."
docker-compose exec -T api alembic current

echo -e "\n8. Generating encryption key..."
ENCRYPTION_KEY=$(python3 -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())")
echo "Generated ENCRYPTION_KEY: $ENCRYPTION_KEY"

echo -e "\n9. Current .env LinkedIn settings (before update)..."
grep -E "LINKEDIN_|ENCRYPTION_KEY" .env || echo "(No LinkedIn settings found)"

echo -e "\n=========================================="
echo "Next Steps:"
echo "=========================================="
echo ""
echo "1. Get LinkedIn OAuth credentials:"
echo "   - Go to: https://www.linkedin.com/developers/apps"
echo "   - Create an app (or use existing)"
echo "   - Copy Client ID and Client Secret"
echo ""
echo "2. Add these lines to .env file on EC2:"
echo ""
echo "   # LinkedIn Integration"
echo "   LINKEDIN_CLIENT_ID=your_client_id_here"
echo "   LINKEDIN_CLIENT_SECRET=your_client_secret_here"
echo "   LINKEDIN_REDIRECT_URI=https://starscreen.net/api/v1/linkedin/auth/callback"
echo ""
echo "   # Token Encryption"
echo "   ENCRYPTION_KEY=$ENCRYPTION_KEY"
echo ""
echo "3. Edit .env file:"
echo "   nano .env"
echo ""
echo "4. Restart API container:"
echo "   docker-compose restart api"
echo ""
echo "=========================================="
echo "Or run this quick setup command:"
echo "=========================================="
echo ""
echo "cat >> .env << 'ENV_EOF'"
echo ""
echo "# LinkedIn Integration"
echo "LINKEDIN_CLIENT_ID=paste_your_client_id_here"
echo "LINKEDIN_CLIENT_SECRET=paste_your_client_secret_here"
echo "LINKEDIN_REDIRECT_URI=https://starscreen.net/api/v1/linkedin/auth/callback"
echo ""
echo "# Token Encryption"
echo "ENCRYPTION_KEY=$ENCRYPTION_KEY"
echo "ENV_EOF"
echo ""
echo "Then: docker-compose restart api"
echo ""

SSH_EOF

echo -e "\nSetup script completed!"
echo "Follow the instructions above to complete LinkedIn configuration."
