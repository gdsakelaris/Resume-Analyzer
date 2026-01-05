# Scripts Guide for Starscreen

Quick reference guide for which script to run where.

## Health Check Scripts

### `check_local_health.sh` - Run ON EC2
**Where**: Run directly ON your EC2 instance
**Purpose**: Quick local health check when you're SSH'd into the server

```bash
# SSH to EC2
ssh starscreen

# Run health check
cd ~/Resume-Analyzer
bash check_local_health.sh
```

**What it checks**:
- ✅ Disk space
- ✅ Memory usage
- ✅ Local API (http://localhost:8000)
- ✅ Public HTTPS (https://starscreen.net)
- ✅ Docker containers
- ✅ Recent errors
- ✅ System uptime

**Use when**: You're already SSH'd into the EC2 and want a quick status check

---

### `test_deployment.sh` / `test_deployment.ps1` - Run FROM local machine
**Where**: Run from your local Windows/Mac/Linux machine
**Purpose**: Quick test to verify the deployment is working

```bash
# Linux/Mac
bash test_deployment.sh

# Windows PowerShell
.\test_deployment.ps1
```

**What it checks**:
- ✅ HTTPS endpoint responding
- ✅ API health check
- ✅ SSH connectivity
- ✅ Docker containers running

**Use when**: You just pushed code and want to verify it deployed successfully

---

### `check_deployment.sh` / `check_deployment.ps1` - Run FROM local machine
**Where**: Run from your local Windows/Mac/Linux machine
**Purpose**: Comprehensive diagnostics (12 checks)

```bash
# Linux/Mac
bash check_deployment.sh

# Windows PowerShell
.\check_deployment.ps1
```

**What it checks**:
- 12 comprehensive checks including network, SSH, HTTPS, API, containers, disk, memory, logs, errors, and more

**Use when**: Something seems wrong and you need detailed diagnostics

---

## CloudWatch Setup Scripts

### `ec2_install_cloudwatch.sh` - Run ON EC2
**Where**: Run directly ON your EC2 instance
**Purpose**: Install CloudWatch Agent for disk/memory monitoring

```bash
# SSH to EC2
ssh starscreen
cd ~/Resume-Analyzer
bash ec2_install_cloudwatch.sh
```

**What it does**:
- Installs CloudWatch Agent
- Configures disk, memory, CPU metrics
- Starts sending metrics to CloudWatch

**Run this**: Once (or after instance rebuild)

---

### `local_create_alarms.sh` - Run FROM local machine
**Where**: Run from your local machine (requires AWS CLI)
**Purpose**: Create CloudWatch email alarms

```bash
# From project root on your local machine
bash local_create_alarms.sh
```

**What it does**:
- Creates SNS topic for email alerts
- Creates alarms for CPU, status checks, disk, memory
- Sends alerts to your email

**Run this**: Once (after installing CloudWatch Agent on EC2)

---

## Quick Reference Table

| Script | Run Where | Purpose | When to Use |
|--------|-----------|---------|-------------|
| `check_local_health.sh` | EC2 | Quick local health check | SSH'd into server |
| `test_deployment.sh` / `.cmd` | Local | Quick deployment test | After pushing code |
| `check_deployment.sh` | Local | Detailed diagnostics | Troubleshooting issues |
| `ec2_install_cloudwatch.sh` | EC2 | Install monitoring agent | One-time setup |
| `local_create_alarms.sh` | Local | Create CloudWatch alarms | One-time setup |

---

## Typical Workflows

### Daily Check
```bash
# From local machine
bash test_deployment.sh
```

### After Code Push
```bash
# Wait for GitHub Actions to complete
# Then from local machine:
bash test_deployment.sh
```

### Troubleshooting
```bash
# From local machine
bash check_deployment.sh

# Or if SSH'd into EC2
bash check_local_health.sh
```

### Initial CloudWatch Setup
```bash
# Step 1: On EC2
ssh starscreen
cd ~/Resume-Analyzer
bash ec2_install_cloudwatch.sh

# Step 2: On local machine
bash local_create_alarms.sh
```

---

## Important Notes

⚠️ **Don't run `check_deployment.sh` ON the EC2 instance** - it's meant for local machines and will hang on the ping command

✅ **Do run `check_local_health.sh` ON the EC2 instance** - it's optimized for local health checks

💻 **Windows users**:
   - **Recommended**: Use Git Bash - open Git Bash terminal and run `bash test_deployment.sh`
   - **Alternative**: Use `test_deployment.cmd` for basic checks (double-click or run in CMD)
   - **Best option**: SSH to EC2 and run `bash check_local_health.sh` there

---

## Questions?

- **EC2 down?** Run `check_deployment.sh` from local machine
- **Need quick status?** Run `check_local_health.sh` on EC2
- **Deployment failed?** Check GitHub Actions first, then run `test_deployment.sh`
- **Want monitoring?** Set up CloudWatch (see guide above)

---

For more details, see [CLOUDWATCH_MONITORING.md](CLOUDWATCH_MONITORING.md)
