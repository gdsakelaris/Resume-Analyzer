#!/bin/bash
#
# CloudWatch Monitoring Setup for Starscreen
# Run this after EC2 is back online
#

set -e

INSTANCE_ID="i-081c728682b8917d2"
REGION="us-east-1"
SNS_TOPIC_NAME="starscreen-alerts"
EMAIL="gdsakelaris6@gmail.com"

echo "========================================"
echo "Setting up CloudWatch Monitoring"
echo "========================================"
echo ""

# Check AWS CLI configured
if ! aws sts get-caller-identity &> /dev/null; then
    echo "ERROR: AWS credentials not configured"
    echo "Run: aws configure"
    exit 1
fi

echo "Instance ID: $INSTANCE_ID"
echo "Region: $REGION"
echo "Alert Email: $EMAIL"
echo ""

# Create SNS topic for alerts
echo "1. Creating SNS topic for alerts..."
SNS_ARN=$(aws sns create-topic \
    --region $REGION \
    --name $SNS_TOPIC_NAME \
    --query 'TopicArn' \
    --output text 2>/dev/null || \
    aws sns list-topics \
        --region $REGION \
        --query "Topics[?contains(TopicArn, '$SNS_TOPIC_NAME')].TopicArn" \
        --output text)

echo "   SNS Topic ARN: $SNS_ARN"

# Subscribe email
echo ""
echo "2. Subscribing email to SNS topic..."
SUBSCRIPTION_ARN=$(aws sns subscribe \
    --region $REGION \
    --topic-arn "$SNS_ARN" \
    --protocol email \
    --notification-endpoint "$EMAIL" \
    --query 'SubscriptionArn' \
    --output text 2>&1 || echo "pending")

if [ "$SUBSCRIPTION_ARN" == "pending confirmation" ] || [[ $SUBSCRIPTION_ARN == *"pending"* ]]; then
    echo "   ⚠️  CHECK YOUR EMAIL ($EMAIL) and confirm the SNS subscription!"
else
    echo "   ✓ Email subscribed"
fi

# Wait for user to confirm
echo ""
read -p "Press Enter after confirming the SNS email subscription..."

# Create CPU alarm
echo ""
echo "3. Creating CPU utilization alarm (>80% for 5 minutes)..."
aws cloudwatch put-metric-alarm \
    --region $REGION \
    --alarm-name starscreen-high-cpu \
    --alarm-description "Starscreen CPU > 80%" \
    --metric-name CPUUtilization \
    --namespace AWS/EC2 \
    --statistic Average \
    --period 300 \
    --threshold 80 \
    --comparison-operator GreaterThanThreshold \
    --evaluation-periods 1 \
    --dimensions Name=InstanceId,Value="$INSTANCE_ID" \
    --alarm-actions "$SNS_ARN" \
    2>&1 | grep -v "^$" || echo "   ✓ CPU alarm created"

# Create status check alarm
echo ""
echo "4. Creating status check alarm..."
aws cloudwatch put-metric-alarm \
    --region $REGION \
    --alarm-name starscreen-status-check-failed \
    --alarm-description "Starscreen instance status check failed" \
    --metric-name StatusCheckFailed \
    --namespace AWS/EC2 \
    --statistic Maximum \
    --period 60 \
    --threshold 1 \
    --comparison-operator GreaterThanOrEqualToThreshold \
    --evaluation-periods 2 \
    --dimensions Name=InstanceId,Value="$INSTANCE_ID" \
    --alarm-actions "$SNS_ARN" \
    2>&1 | grep -v "^$" || echo "   ✓ Status check alarm created"

# Create disk space alarm (requires CloudWatch agent)
echo ""
echo "5. Creating disk usage alarm (>80%)..."
aws cloudwatch put-metric-alarm \
    --region $REGION \
    --alarm-name starscreen-high-disk-usage \
    --alarm-description "Starscreen disk usage > 80%" \
    --metric-name disk_used_percent \
    --namespace CWAgent \
    --statistic Average \
    --period 300 \
    --threshold 80 \
    --comparison-operator GreaterThanThreshold \
    --evaluation-periods 1 \
    --dimensions Name=InstanceId,Value="$INSTANCE_ID" Name=path,Value="/" Name=device,Value="xvda1" Name=fstype,Value="ext4" \
    --alarm-actions "$SNS_ARN" \
    2>&1 || echo "   ⚠️  Disk alarm requires CloudWatch Agent (see below)"

# Create memory alarm (requires CloudWatch agent)
echo ""
echo "6. Creating memory usage alarm (>80%)..."
aws cloudwatch put-metric-alarm \
    --region $REGION \
    --alarm-name starscreen-high-memory \
    --alarm-description "Starscreen memory usage > 80%" \
    --metric-name mem_used_percent \
    --namespace CWAgent \
    --statistic Average \
    --period 300 \
    --threshold 80 \
    --comparison-operator GreaterThanThreshold \
    --evaluation-periods 1 \
    --dimensions Name=InstanceId,Value="$INSTANCE_ID" \
    --alarm-actions "$SNS_ARN" \
    2>&1 || echo "   ⚠️  Memory alarm requires CloudWatch Agent (see below)"

echo ""
echo "========================================"
echo "✓ CloudWatch Alarms Created!"
echo "========================================"
echo ""
echo "View alarms:"
echo "https://console.aws.amazon.com/cloudwatch/home?region=$REGION#alarmsV2:"
echo ""

# Install CloudWatch Agent on EC2
echo "========================================"
echo "Installing CloudWatch Agent on EC2"
echo "========================================"
echo ""

read -p "Do you want to install CloudWatch Agent for disk/memory monitoring? (y/n): " -n 1 -r
echo ""

if [[ $REPLY =~ ^[Yy]$ ]]; then
    echo "Connecting to EC2 and installing CloudWatch Agent..."

    ssh -i "starsceen_key.pem" ubuntu@54.158.113.25 << 'EOF'
        set -e

        echo "Downloading CloudWatch Agent..."
        wget -q https://amazoncloudwatch-agent.s3.amazonaws.com/ubuntu/amd64/latest/amazon-cloudwatch-agent.deb

        echo "Installing CloudWatch Agent..."
        sudo dpkg -i -E ./amazon-cloudwatch-agent.deb
        rm amazon-cloudwatch-agent.deb

        echo "Creating CloudWatch Agent config..."
        sudo tee /opt/aws/amazon-cloudwatch-agent/etc/cloudwatch-config.json > /dev/null << 'CWCONFIG'
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
        "resources": [
          "*"
        ]
      },
      "diskio": {
        "measurement": [
          "io_time"
        ],
        "metrics_collection_interval": 60
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
        "measurement": [
          "tcp_established",
          "tcp_time_wait"
        ],
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
CWCONFIG

        echo "Starting CloudWatch Agent..."
        sudo /opt/aws/amazon-cloudwatch-agent/bin/amazon-cloudwatch-agent-ctl \
            -a fetch-config \
            -m ec2 \
            -s \
            -c file:/opt/aws/amazon-cloudwatch-agent/etc/cloudwatch-config.json

        echo ""
        echo "✓ CloudWatch Agent installed and running!"
        echo ""
        echo "Check agent status:"
        sudo /opt/aws/amazon-cloudwatch-agent/bin/amazon-cloudwatch-agent-ctl \
            -a query \
            -m ec2 \
            -c default
EOF

    echo ""
    echo "✓ CloudWatch Agent installed on EC2!"
    echo ""
    echo "Wait 5 minutes, then re-run this script to create disk/memory alarms."
fi

echo ""
echo "========================================"
echo "Summary"
echo "========================================"
echo "✓ SNS topic created: $SNS_ARN"
echo "✓ Email alerts sent to: $EMAIL"
echo "✓ CPU alarm created (>80%)"
echo "✓ Status check alarm created"
echo ""
echo "View metrics:"
echo "https://console.aws.amazon.com/cloudwatch/home?region=$REGION#metricsV2:graph=~();namespace=~'AWS*2fEC2"
echo ""
echo "View logs:"
echo "https://console.aws.amazon.com/cloudwatch/home?region=$REGION#logsV2:log-groups"
echo ""
echo "Done!"
