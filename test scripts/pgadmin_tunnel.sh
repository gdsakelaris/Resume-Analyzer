#!/bin/bash
#
# pgAdmin SSH Tunnel Helper
# This creates a secure SSH tunnel to access pgAdmin
#

SSH_KEY="C:/Users/gdsak/OneDrive/Desktop/starsceen_key.pem"
INSTANCE_IP="54.158.113.25"

echo "========================================="
echo "pgAdmin SSH Tunnel"
echo "========================================="
echo ""
echo "Starting SSH tunnel to pgAdmin..."
echo ""
echo "Once connected:"
echo "  1. Open browser: http://localhost:5050"
echo "  2. Login with:"
echo "     Email: admin@starscreen.net"
echo "     Password: Starscreen2026!"
echo ""
echo "  3. Add database server:"
echo "     Name: Starscreen Production"
echo "     Host: db"
echo "     Port: 5432"
echo "     Database: starscreen_prod"
echo "     Username: starscreen_user"
echo "     Password: Ilikecode1!"
echo ""
echo "Press Ctrl+C to stop the tunnel"
echo "========================================="
echo ""

# Create SSH tunnel
ssh -i "$SSH_KEY" -L 5050:localhost:5050 ubuntu@$INSTANCE_IP -N
