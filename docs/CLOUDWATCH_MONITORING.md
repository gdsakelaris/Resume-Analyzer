# CloudWatch Monitoring Guide for Starscreen

This guide explains how to monitor your Starscreen deployment using AWS CloudWatch.

## What Happened: EC2 Instance Down

### The Issue

On 2026-01-04, the EC2 instance (i-081c728682b8917d2) became unresponsive:
- **SSH**: Connection timeout
- **HTTPS**: HTTP 522 (CloudFlare origin server timeout)
- **Instance State**: Running (but frozen/hung)

### Root Cause

The EC2 instance was running but completely unresponsive, likely due to:
- Out of memory (OOM) killing processes
- Disk full preventing Docker from operating
- System hang due to resource exhaustion
- Docker daemon crash

### The Fix

**Reboot the EC2 instance** via AWS Console:

1. Go to: https://console.aws.amazon.com/ec2/home?region=us-east-1#Instances:instanceId=i-081c728682b8917d2
2. Right-click instance → **Instance State** → **Reboot instance**
3. Wait 2-3 minutes
4. Run `bash test_deployment.sh` to verify it's back up

---

## Setting Up CloudWatch Monitoring

To prevent this from happening again, set up CloudWatch monitoring in two steps:

### Quick Setup (Recommended)

**Step 1: Install CloudWatch Agent ON your EC2 instance**

```bash
# SSH to your EC2
ssh starscreen

# Navigate to project directory
cd ~/Resume-Analyzer

# Pull latest scripts
git pull

# Run installation script
bash ec2_install_cloudwatch.sh
```

This installs the CloudWatch Agent to collect disk, memory, and log metrics.

**Step 2: Create CloudWatch Alarms FROM your local machine**

```bash
# On your local machine (requires AWS CLI configured)
bash local_create_alarms.sh
```

This creates email alerts for:
- CPU usage >80%
- Instance status check failures
- Disk usage >80%
- Memory usage >80%

**Total time**: ~5 minutes

### Manual Setup

#### 1. Create SNS Topic for Alerts

```bash
aws sns create-topic \
    --region us-east-1 \
    --name starscreen-alerts

# Subscribe your email
aws sns subscribe \
    --region us-east-1 \
    --topic-arn "arn:aws:sns:us-east-1:593989447165:starscreen-alerts" \
    --protocol email \
    --notification-endpoint "gdsakelaris6@gmail.com"

# Check your email and confirm the subscription!
```

#### 2. Create CPU Alarm

```bash
aws cloudwatch put-metric-alarm \
    --region us-east-1 \
    --alarm-name starscreen-high-cpu \
    --alarm-description "Alert when CPU exceeds 80%" \
    --metric-name CPUUtilization \
    --namespace AWS/EC2 \
    --statistic Average \
    --period 300 \
    --threshold 80 \
    --comparison-operator GreaterThanThreshold \
    --evaluation-periods 1 \
    --dimensions Name=InstanceId,Value=i-081c728682b8917d2 \
    --alarm-actions "arn:aws:sns:us-east-1:593989447165:starscreen-alerts"
```

#### 3. Create Status Check Alarm

```bash
aws cloudwatch put-metric-alarm \
    --region us-east-1 \
    --alarm-name starscreen-status-check-failed \
    --alarm-description "Alert when instance status check fails" \
    --metric-name StatusCheckFailed \
    --namespace AWS/EC2 \
    --statistic Maximum \
    --period 60 \
    --threshold 1 \
    --comparison-operator GreaterThanOrEqualToThreshold \
    --evaluation-periods 2 \
    --dimensions Name=InstanceId,Value=i-081c728682b8917d2 \
    --alarm-actions "arn:aws:sns:us-east-1:593989447165:starscreen-alerts"
```

---

## Installing CloudWatch Agent (For Disk/Memory Monitoring)

The CloudWatch Agent is required to monitor:
- Disk usage
- Memory usage
- Custom application logs

### Install on EC2

SSH into your EC2 instance:

```bash
ssh -i "starsceen_key.pem" ubuntu@54.158.113.25

# Download and install agent
wget https://amazoncloudwatch-agent.s3.amazonaws.com/ubuntu/amd64/latest/amazon-cloudwatch-agent.deb
sudo dpkg -i -E ./amazon-cloudwatch-agent.deb
rm amazon-cloudwatch-agent.deb
```

### Configure CloudWatch Agent

Create config file:

```bash
sudo tee /opt/aws/amazon-cloudwatch-agent/etc/cloudwatch-config.json > /dev/null << 'EOF'
{
  "agent": {
    "metrics_collection_interval": 60,
    "run_as_user": "cwagent"
  },
  "metrics": {
    "namespace": "CWAgent",
    "metrics_collected": {
      "cpu": {
        "measurement": ["cpu_usage_idle", "cpu_usage_iowait"],
        "metrics_collection_interval": 60,
        "totalcpu": false
      },
      "disk": {
        "measurement": [
          {
            "name": "used_percent",
            "rename": "disk_used_percent",
            "unit": "Percent"
          }
        ],
        "metrics_collection_interval": 60,
        "resources": ["*"]
      },
      "mem": {
        "measurement": [
          {
            "name": "mem_used_percent",
            "rename": "mem_used_percent",
            "unit": "Percent"
          }
        ],
        "metrics_collection_interval": 60
      },
      "netstat": {
        "measurement": ["tcp_established", "tcp_time_wait"],
        "metrics_collection_interval": 60
      }
    }
  },
  "logs": {
    "logs_collected": {
      "files": {
        "collect_list": [
          {
            "file_path": "/home/ubuntu/Resume-Analyzer/logs/api.log",
            "log_group_name": "/starscreen/api",
            "log_stream_name": "{instance_id}",
            "timezone": "UTC"
          },
          {
            "file_path": "/var/log/syslog",
            "log_group_name": "/starscreen/syslog",
            "log_stream_name": "{instance_id}",
            "timezone": "UTC"
          }
        ]
      }
    }
  }
}
EOF
```

### Start CloudWatch Agent

```bash
sudo /opt/aws/amazon-cloudwatch-agent/bin/amazon-cloudwatch-agent-ctl \
    -a fetch-config \
    -m ec2 \
    -s \
    -c file:/opt/aws/amazon-cloudwatch-agent/etc/cloudwatch-config.json

# Verify it's running
sudo /opt/aws/amazon-cloudwatch-agent/bin/amazon-cloudwatch-agent-ctl \
    -a query \
    -m ec2 \
    -c default
```

---

## Viewing CloudWatch Metrics and Logs

### CloudWatch Console Links

- **Alarms**: https://console.aws.amazon.com/cloudwatch/home?region=us-east-1#alarmsV2:
- **Metrics**: https://console.aws.amazon.com/cloudwatch/home?region=us-east-1#metricsV2:graph=~()
- **Logs**: https://console.aws.amazon.com/cloudwatch/home?region=us-east-1#logsV2:log-groups
- **Dashboards**: https://console.aws.amazon.com/cloudwatch/home?region=us-east-1#dashboards:

### Key Metrics to Monitor

| Metric | Threshold | Action |
|--------|-----------|--------|
| CPU Utilization | >80% for 5 min | Check for runaway processes |
| Memory Usage | >80% | Restart containers or upgrade instance |
| Disk Usage | >80% | Clean up logs, old Docker images |
| Status Check Failed | ≥1 | Reboot instance |

### Using AWS CLI to View Metrics

```bash
# Get CPU utilization for last hour
aws cloudwatch get-metric-statistics \
    --region us-east-1 \
    --namespace AWS/EC2 \
    --metric-name CPUUtilization \
    --dimensions Name=InstanceId,Value=i-081c728682b8917d2 \
    --start-time $(date -u -d '1 hour ago' +%Y-%m-%dT%H:%M:%S) \
    --end-time $(date -u +%Y-%m-%dT%H:%M:%S) \
    --period 300 \
    --statistics Average

# View alarm status
aws cloudwatch describe-alarms \
    --region us-east-1 \
    --alarm-names starscreen-high-cpu starscreen-status-check-failed

# View recent log events
aws logs tail /starscreen/api --region us-east-1 --follow
```

---

## Troubleshooting with CloudWatch

### When You Get an Alert Email

1. **Check the alarm** to see which metric triggered:
   - Go to CloudWatch Console → Alarms
   - Click on the alarm name
   - View the graph to see when the spike occurred

2. **SSH into EC2** and investigate:
   ```bash
   ssh -i "starsceen_key.pem" ubuntu@54.158.113.25

   # Check disk space
   df -h

   # Check memory
   free -h

   # Check container status
   cd ~/Resume-Analyzer
   docker-compose ps

   # Check container resource usage
   docker stats --no-stream

   # View recent logs
   docker-compose logs --tail=50 api
   ```

3. **Common fixes**:
   - **High CPU**: Restart worker container: `docker-compose restart worker`
   - **High Memory**: Restart all containers: `docker-compose restart`
   - **High Disk**: Clean up Docker: `docker system prune -a --volumes -f`
   - **Status Check Failed**: Reboot instance via AWS Console

### Automated Recovery (Optional)

You can configure EC2 to automatically recover on status check failure:

```bash
aws cloudwatch put-metric-alarm \
    --region us-east-1 \
    --alarm-name starscreen-auto-recover \
    --alarm-description "Auto-recover instance on status check failure" \
    --metric-name StatusCheckFailed_System \
    --namespace AWS/EC2 \
    --statistic Maximum \
    --period 60 \
    --threshold 1 \
    --comparison-operator GreaterThanOrEqualToThreshold \
    --evaluation-periods 2 \
    --dimensions Name=InstanceId,Value=i-081c728682b8917d2 \
    --alarm-actions "arn:aws:automate:us-east-1:ec2:recover"
```

---

## Cost Estimate

CloudWatch costs for Starscreen:

| Service | Usage | Monthly Cost |
|---------|-------|--------------|
| Basic EC2 metrics (free) | CPU, disk, network | $0 |
| CloudWatch alarms | 5 alarms | $0.50 ($0.10/alarm) |
| Custom metrics (CWAgent) | ~20 metrics | $6.00 ($0.30/metric) |
| Log ingestion | ~1 GB/month | $0.50 |
| Log storage | ~5 GB | $0.25 |
| **Total** | | **~$7/month** |

**Tip**: You can reduce costs by:
- Using only basic alarms (no CloudWatch Agent) = **$0.50/month**
- Reducing log retention to 7 days instead of 30 days
- Filtering logs to only errors/warnings

---

## Daily Monitoring Checklist

Use these scripts to check your deployment health:

```bash
# Quick health check
bash test_deployment.sh

# Detailed diagnostics (if something seems wrong)
bash check_deployment.sh
```

### What to Monitor Daily

- ✅ API is responding: https://starscreen.net/api/v1/health/
- ✅ No alarm emails received
- ✅ GitHub Actions deployments succeeding

### Weekly Monitoring

- Check CloudWatch metrics for trends
- Review CloudWatch logs for errors
- Clean up old Docker images: `docker system prune -a -f`

---

## Additional Resources

- [AWS CloudWatch User Guide](https://docs.aws.amazon.com/AmazonCloudWatch/latest/monitoring/)
- [CloudWatch Agent Configuration](https://docs.aws.amazon.com/AmazonCloudWatch/latest/monitoring/create-cloudwatch-agent-configuration-file.html)
- [CloudWatch Pricing](https://aws.amazon.com/cloudwatch/pricing/)

---

## Questions?

If you have issues with CloudWatch or need help debugging:
- Check the CloudWatch Console first
- Review recent logs: `aws logs tail /starscreen/api --follow`
- Email: support@starscreen.net
