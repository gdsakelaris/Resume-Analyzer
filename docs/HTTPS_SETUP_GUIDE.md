# HTTPS Setup Guide for starscreen.net

## Overview
This guide will help you set up HTTPS for your starscreen.net domain so that Stripe webhooks can function properly.

---

## Step 1: Configure DNS Settings

You need to point your domain to your EC2 instance.

### In Your Domain Registrar (where you bought starscreen.net):

1. **Log in to your domain registrar** (GoDaddy, Namecheap, Google Domains, etc.)

2. **Find DNS Settings** (usually called "DNS Management" or "Name Servers")

3. **Add these A records**:

   ```
   Type: A
   Name: @ (or leave blank for root domain)
   Value: 44.223.41.116
   TTL: 3600 (or default)

   Type: A
   Name: www
   Value: 44.223.41.116
   TTL: 3600 (or default)
   ```

4. **Save changes**

   ⏱️ DNS propagation can take 5 minutes to 48 hours (usually 15-30 minutes)

5. **Test DNS propagation**:
   ```bash
   # On your local machine, run:
   nslookup starscreen.net

   # Should show: 44.223.41.116
   ```

---

## Step 2: Install Nginx and Certbot on EC2

Once DNS is pointing to your server, SSH into EC2:

```bash
ssh starscreen-ec2
```

### Install required packages:

```bash
# Update package list
sudo apt update

# Install Nginx (web server/reverse proxy)
sudo apt install -y nginx

# Install Certbot (Let's Encrypt SSL certificate tool)
sudo apt install -y certbot python3-certbot-nginx

# Verify installation
nginx -v
certbot --version
```

---

## Step 3: Configure Nginx as Reverse Proxy

### Create Nginx configuration file:

```bash
sudo nano /etc/nginx/sites-available/starscreen
```

### Paste this configuration:

```nginx
server {
    listen 80;
    server_name starscreen.net www.starscreen.net;

    # Increase client body size for file uploads (resumes)
    client_max_body_size 100M;

    # Proxy all requests to Docker container
    location / {
        proxy_pass http://localhost:8000;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;

        # WebSocket support (if needed in future)
        proxy_http_version 1.1;
        proxy_set_header Upgrade $http_upgrade;
        proxy_set_header Connection "upgrade";
    }

    # Health check endpoint
    location /health {
        access_log off;
        return 200 "healthy\n";
        add_header Content-Type text/plain;
    }
}
```

**Save**: Press `Ctrl+X`, then `Y`, then `Enter`

### Enable the site:

```bash
# Create symbolic link to enable the site
sudo ln -s /etc/nginx/sites-available/starscreen /etc/nginx/sites-enabled/

# Remove default site (optional)
sudo rm -f /etc/nginx/sites-enabled/default

# Test configuration
sudo nginx -t

# Should output: "syntax is ok" and "test is successful"
```

### Start Nginx:

```bash
# Start Nginx
sudo systemctl start nginx

# Enable Nginx to start on boot
sudo systemctl enable nginx

# Check status
sudo systemctl status nginx
```

---

## Step 4: Configure EC2 Security Group

Make sure EC2 allows HTTPS traffic:

1. **Go to AWS Console → EC2 → Security Groups**

2. **Find your instance's security group**

3. **Add Inbound Rules**:
   ```
   Type: HTTP
   Protocol: TCP
   Port: 80
   Source: 0.0.0.0/0 (Anywhere IPv4)

   Type: HTTPS
   Protocol: TCP
   Port: 443
   Source: 0.0.0.0/0 (Anywhere IPv4)
   ```

4. **Save rules**

---

## Step 5: Test HTTP Access

Before getting SSL certificate, verify HTTP works:

```bash
# From your local machine:
curl http://starscreen.net

# Should return your app's HTML
```

Or visit in browser:
```
http://starscreen.net
```

You should see your app running! ✅

---

## Step 6: Get SSL Certificate with Let's Encrypt

Back on EC2, run Certbot:

```bash
sudo certbot --nginx -d starscreen.net -d www.starscreen.net
```

### You'll be prompted for:

1. **Email address**: Enter your email (for renewal notifications)
2. **Terms of Service**: Type `Y` to agree
3. **Share email**: Type `N` (optional)

Certbot will:
- Automatically verify domain ownership
- Get SSL certificate
- Update Nginx configuration
- Set up auto-renewal

### Expected output:
```
Successfully received certificate.
Certificate is saved at: /etc/letsencrypt/live/starscreen.net/fullchain.pem
Key is saved at:         /etc/letsencrypt/live/starscreen.net/privkey.pem

Deploying certificate
Successfully deployed certificate for starscreen.net to /etc/nginx/sites-enabled/starscreen
Congratulations! You have successfully enabled HTTPS on https://starscreen.net
```

---

## Step 7: Test HTTPS

```bash
# Test HTTPS access
curl https://starscreen.net

# Check SSL certificate
curl -I https://starscreen.net
```

Or visit in browser:
```
https://starscreen.net
```

You should see:
- 🔒 Lock icon in browser
- No certificate warnings
- Your app loads normally

---

## Step 8: Update Environment Variables

Update your `.env` file with the new HTTPS URL:

```bash
cd ~/Resume-Analyzer
nano .env
```

**Update this line**:
```bash
FRONTEND_URL=https://starscreen.net
```

**Save**: `Ctrl+X`, `Y`, `Enter`

### Restart the API to load new environment:

```bash
docker-compose restart api
```

---

## Step 9: Set Up Stripe Webhook (Finally!)

Now you can create the webhook with HTTPS:

1. **Go to Stripe Dashboard** → Developers → Webhooks

2. **Click "Add endpoint"**

3. **Configure webhook**:
   ```
   Endpoint URL: https://starscreen.net/api/v1/webhooks/stripe
   ```

4. **Select events to listen for**:
   - `customer.subscription.created`
   - `customer.subscription.updated`
   - `customer.subscription.deleted`
   - `invoice.payment_succeeded`
   - `invoice.payment_failed`

5. **Click "Add endpoint"**

6. **Copy the "Signing secret"** (starts with `whsec_`)

7. **Update .env on EC2**:
   ```bash
   nano .env
   ```

   Add/update:
   ```bash
   STRIPE_WEBHOOK_SECRET=whsec_YOUR_SIGNING_SECRET_HERE
   ```

8. **Restart API again**:
   ```bash
   docker-compose restart api
   ```

---

## Step 10: Test Webhook

Test that Stripe can reach your webhook:

1. **In Stripe Dashboard** → Webhooks → Click your endpoint

2. **Click "Send test webhook"**

3. **Select event**: `customer.subscription.created`

4. **Click "Send test webhook"**

5. **Check response**: Should see `200 OK`

---

## Step 11: Test Complete Payment Flow

1. **Visit**: `https://starscreen.net/static/pricing.html`

2. **Click "Start Free Trial"** on any paid plan

3. **Use Stripe test card**:
   ```
   Card: 4242 4242 4242 4242
   Expiry: Any future date
   CVC: Any 3 digits
   ZIP: Any 5 digits
   ```

4. **Complete checkout**

5. **Verify**:
   - Subscription created in Stripe Dashboard
   - Webhook events received
   - Database updated with subscription

---

## Certificate Auto-Renewal

Let's Encrypt certificates expire after 90 days, but Certbot sets up automatic renewal.

### Test auto-renewal:

```bash
sudo certbot renew --dry-run
```

Should output: "Congratulations, all simulated renewals succeeded"

### Check renewal timer:

```bash
sudo systemctl status certbot.timer
```

Should show: "active (waiting)"

---

## Troubleshooting

### DNS not resolving?
```bash
# Check DNS
nslookup starscreen.net

# Wait 15-30 minutes for propagation
# Clear your DNS cache:
# Windows: ipconfig /flushdns
# Mac: sudo dscacheutil -flushcache
# Linux: sudo systemd-resolve --flush-caches
```

### Nginx won't start?
```bash
# Check configuration
sudo nginx -t

# Check error logs
sudo tail -f /var/log/nginx/error.log
```

### Certificate failed?
```bash
# Check Certbot logs
sudo tail -f /var/log/letsencrypt/letsencrypt.log

# Make sure DNS is working first
# Make sure port 80 is accessible
```

### Stripe webhook failing?
```bash
# Check API logs
docker-compose logs -f api

# Test webhook endpoint manually
curl -X POST https://starscreen.net/api/v1/webhooks/stripe

# Should return error about missing signature (that's OK - means endpoint is reachable)
```

---

## Summary Checklist

- [ ] DNS A records pointing to 44.223.41.116
- [ ] DNS propagation complete (nslookup shows correct IP)
- [ ] Nginx installed and running
- [ ] Nginx configuration created and enabled
- [ ] EC2 Security Group allows ports 80 and 443
- [ ] HTTP access works (http://starscreen.net)
- [ ] SSL certificate obtained with Certbot
- [ ] HTTPS access works (https://starscreen.net)
- [ ] FRONTEND_URL updated in .env
- [ ] Stripe webhook created with HTTPS URL
- [ ] STRIPE_WEBHOOK_SECRET added to .env
- [ ] API restarted to load new env vars
- [ ] Test webhook sent successfully
- [ ] Complete payment flow tested

---

## Quick Reference Commands

```bash
# Check Nginx status
sudo systemctl status nginx

# Restart Nginx
sudo systemctl restart nginx

# View Nginx logs
sudo tail -f /var/log/nginx/access.log
sudo tail -f /var/log/nginx/error.log

# Renew SSL certificate manually
sudo certbot renew

# Check certificate expiry
sudo certbot certificates

# Restart Docker services
docker-compose restart api

# View API logs
docker-compose logs -f api
```

---

**Status**: Ready to implement
**Next Step**: Configure DNS at your domain registrar
**Estimated Time**: 30-60 minutes (mostly waiting for DNS propagation)
