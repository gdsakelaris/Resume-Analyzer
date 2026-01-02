# Auto-Deployment Setup Guide

This guide shows you how to set up automatic deployment from GitHub to your EC2 instance.

## How It Works

```
You push to GitHub → GitHub webhook triggers → EC2 receives webhook → Runs deploy.sh → Pulls code & restarts services
```

## Setup Steps

### 1. Generate a Webhook Secret

On your local machine:
```bash
openssl rand -hex 32
```

Copy this secret - you'll need it for both GitHub and EC2.

### 2. Setup Files on EC2

SSH into your EC2 instance:
```bash
ssh ubuntu@your-ec2-ip
cd ~/Resume-Analyzer
git pull  # Get the latest files
```

Make the deploy script executable:
```bash
chmod +x deploy.sh
```

### 3. Configure the Webhook Secret

Edit the webhook service file:
```bash
nano webhook.service
```

Replace `your-secret-key-change-this` with the secret you generated in step 1.

### 4. Install the Webhook Service

```bash
sudo cp webhook.service /etc/systemd/system/
sudo systemctl daemon-reload
sudo systemctl enable webhook
sudo systemctl start webhook
```

Check if it's running:
```bash
sudo systemctl status webhook
```

You should see "active (running)".

### 5. Open Port 8000 in AWS Security Group

1. Go to AWS EC2 Console
2. Click on your instance → Security tab
3. Click on the security group
4. Edit inbound rules
5. Add rule:
   - Type: Custom TCP
   - Port: 8000
   - Source: 0.0.0.0/0 (or restrict to GitHub IPs)
   - Description: GitHub Webhook
6. Save rules

### 6. Configure GitHub Webhook

1. Go to your GitHub repository: https://github.com/gdsakelaris/Resume-Analyzer
2. Click **Settings** → **Webhooks** → **Add webhook**
3. Configure:
   - **Payload URL**: `http://your-ec2-public-ip:8000/webhook`
   - **Content type**: `application/json`
   - **Secret**: Paste the secret from step 1
   - **Which events**: Select "Just the push event"
   - **Active**: Check this box
4. Click **Add webhook**

### 7. Test the Setup

On your local machine:
```bash
# Make a small change
echo "# Auto-deploy test" >> README.md
git add README.md
git commit -m "Test auto-deployment"
git push
```

Then check on EC2:
```bash
# View webhook logs
sudo journalctl -u webhook -f

# Check if git pulled
cd ~/Resume-Analyzer
git log -1

# Check if services restarted
docker-compose ps
```

You should see:
- Webhook received the push event
- Git pulled the latest changes
- Docker services restarted

## Troubleshooting

### Check Webhook Service Status
```bash
sudo systemctl status webhook
```

### View Webhook Logs
```bash
sudo journalctl -u webhook -n 50
```

### Test Webhook Manually
```bash
curl -X POST http://localhost:8000/webhook \
  -H "Content-Type: application/json" \
  -d '{"ref":"refs/heads/main"}'
```

### Restart Webhook Service
```bash
sudo systemctl restart webhook
```

### GitHub Webhook Deliveries
Go to GitHub → Settings → Webhooks → Click on your webhook → Recent Deliveries

You'll see each webhook attempt and the response.

## Security Notes

1. **Change the webhook secret** - Don't use the default
2. **Restrict port 8000** to GitHub IPs if possible:
   - `192.30.252.0/22`
   - `185.199.108.0/22`
   - `140.82.112.0/20`
3. **Use HTTPS** in production (requires SSL certificate)
4. **Monitor logs** regularly for suspicious activity

## What Gets Deployed

Every push to `main` branch will:
1. Pull latest code from GitHub
2. Restart the `api` service (backend)
3. Static files (HTML/JS) are updated automatically (no restart needed)

## Advanced: Deploy on Specific Branches

Edit `webhook_server.py` to deploy on different branches:

```python
# Deploy on push to main OR staging
if ref in ['refs/heads/main', 'refs/heads/staging']:
    # Run deployment
```

## Advanced: Rebuild Docker Images

If you change Dockerfile or requirements.txt, modify `deploy.sh`:

```bash
# Add these lines before docker-compose restart
docker-compose build api
docker-compose up -d api
```

## Disable Auto-Deploy

```bash
sudo systemctl stop webhook
sudo systemctl disable webhook
```

## Remove Auto-Deploy

```bash
sudo systemctl stop webhook
sudo systemctl disable webhook
sudo rm /etc/systemd/system/webhook.service
sudo systemctl daemon-reload
```
