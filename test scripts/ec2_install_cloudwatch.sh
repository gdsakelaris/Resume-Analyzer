#!/bin/bash
#
# CloudWatch Agent Installation Script
# Run this script ON your EC2 instance (ssh starscreen, then run this)
#

set -e

echo "========================================="
echo "CloudWatch Agent Installation"
echo "========================================="
echo ""

# Check if running on EC2
if [ ! -f /sys/hypervisor/uuid ] && [ ! -d /sys/class/dmi/id ]; then
    echo "⚠️  Warning: This doesn't look like an EC2 instance"
    read -p "Continue anyway? (y/n): " -n 1 -r
    echo ""
    if [[ ! $REPLY =~ ^[Yy]$ ]]; then
        exit 1
    fi
fi

echo "1. Checking disk space..."
DISK_AVAIL=$(df / | tail -1 | awk '{print $4}')
echo "   Available: ${DISK_AVAIL}K"
if [ "$DISK_AVAIL" -lt 500000 ]; then
    echo "   ⚠️  Warning: Less than 500MB available"
fi

echo ""
echo "2. Downloading CloudWatch Agent..."
cd /tmp
wget -q https://amazoncloudwatch-agent.s3.amazonaws.com/ubuntu/amd64/latest/amazon-cloudwatch-agent.deb
echo "   ✓ Downloaded"

echo ""
echo "3. Installing CloudWatch Agent..."
sudo dpkg -i -E ./amazon-cloudwatch-agent.deb
rm amazon-cloudwatch-agent.deb
echo "   ✓ Installed"

echo ""
echo "4. Creating CloudWatch Agent configuration..."
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
        "measurement": [
          {
            "name": "cpu_usage_idle",
            "rename": "CPU_IDLE",
            "unit": "Percent"
          },
          "cpu_usage_iowait"
        ],
        "metrics_collection_interval": 60,
        "totalcpu": false
      },
      "disk": {
        "measurement": [
          {
            "name": "used_percent",
            "rename": "disk_used_percent",
            "unit": "Percent"
          },
          "inodes_free"
        ],
        "metrics_collection_interval": 60,
        "resources": ["/"]
      },
      "diskio": {
        "measurement": ["io_time", "write_bytes", "read_bytes"],
        "metrics_collection_interval": 60
      },
      "mem": {
        "measurement": [
          {
            "name": "mem_used_percent",
            "rename": "mem_used_percent",
            "unit": "Percent"
          },
          "mem_available"
        ],
        "metrics_collection_interval": 60
      },
      "netstat": {
        "measurement": ["tcp_established", "tcp_time_wait"],
        "metrics_collection_interval": 60
      },
      "swap": {
        "measurement": [
          {
            "name": "swap_used_percent",
            "rename": "swap_used_percent",
            "unit": "Percent"
          }
        ],
        "metrics_collection_interval": 60
      }
    }
  },
  "logs": {
    "logs_collected": {
      "files": {
        "collect_list": [
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
echo "   ✓ Configuration created"

echo ""
echo "5. Starting CloudWatch Agent..."
sudo /opt/aws/amazon-cloudwatch-agent/bin/amazon-cloudwatch-agent-ctl \
    -a fetch-config \
    -m ec2 \
    -s \
    -c file:/opt/aws/amazon-cloudwatch-agent/etc/cloudwatch-config.json

echo ""
echo "6. Verifying agent is running..."
sleep 2
STATUS=$(sudo /opt/aws/amazon-cloudwatch-agent/bin/amazon-cloudwatch-agent-ctl \
    -a query \
    -m ec2 \
    -c default | grep -c "running" || echo "0")

if [ "$STATUS" -gt 0 ]; then
    echo "   ✓ CloudWatch Agent is running!"
else
    echo "   ✗ Agent may not be running. Check logs:"
    echo "     sudo journalctl -u amazon-cloudwatch-agent -n 50"
    exit 1
fi

echo ""
echo "========================================="
echo "✓ CloudWatch Agent Installed!"
echo "========================================="
echo ""
echo "The agent is now sending metrics to CloudWatch:"
echo "  - CPU usage"
echo "  - Memory usage"
echo "  - Disk usage"
echo "  - Network connections"
echo "  - System logs"
echo ""
echo "View metrics in CloudWatch Console:"
echo "https://console.aws.amazon.com/cloudwatch/home?region=us-east-1#metricsV2:namespace=CWAgent"
echo ""
echo "Next step: Create CloudWatch alarms from your local machine"
echo "Run: bash local_create_alarms.sh"
echo ""
