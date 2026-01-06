#!/bin/bash
#
# CloudWatch Alarms Setup Script
# Run this script FROM YOUR LOCAL MACHINE (requires AWS CLI configured)
#

set -e

INSTANCE_ID="i-081c728682b8917d2"
REGION="us-east-1"
SNS_TOPIC_NAME="starscreen-alerts"
EMAIL="gdsakelaris6@gmail.com"

echo "========================================="
echo "CloudWatch Alarms Setup"
echo "========================================="
echo ""

# Check AWS CLI
if ! command -v aws &> /dev/null; then
    echo "✗ AWS CLI not found. Install from: https://aws.amazon.com/cli/"
    exit 1
fi

# Check AWS credentials
echo "1. Checking AWS credentials..."
if ! aws sts get-caller-identity &> /dev/null; then
    echo "   ✗ AWS credentials not configured"
    echo ""
    echo "   Run: aws configure"
    echo "   You'll need your AWS Access Key ID and Secret Access Key"
    exit 1
fi
echo "   ✓ AWS credentials configured"

echo ""
echo "2. Creating SNS topic for email alerts..."
SNS_ARN=$(aws sns create-topic \
    --region $REGION \
    --name $SNS_TOPIC_NAME \
    --query 'TopicArn' \
    --output text 2>/dev/null || \
    aws sns list-topics \
        --region $REGION \
        --query "Topics[?contains(TopicArn, '$SNS_TOPIC_NAME')].TopicArn" \
        --output text)

echo "   SNS Topic: $SNS_TOPIC_NAME"
echo "   ARN: $SNS_ARN"

echo ""
echo "3. Subscribing email to alerts..."
aws sns subscribe \
    --region $REGION \
    --topic-arn "$SNS_ARN" \
    --protocol email \
    --notification-endpoint "$EMAIL" \
    --output text > /dev/null 2>&1 || echo "   (Already subscribed)"

echo "   ✓ Subscription created"
echo "   ⚠️  CHECK YOUR EMAIL ($EMAIL) and confirm the subscription!"
echo ""
read -p "Press Enter after confirming the email subscription..."

echo ""
echo "4. Creating CPU utilization alarm (>80% for 5 minutes)..."
aws cloudwatch put-metric-alarm \
    --region $REGION \
    --alarm-name starscreen-high-cpu \
    --alarm-description "Starscreen CPU usage exceeds 80%" \
    --metric-name CPUUtilization \
    --namespace AWS/EC2 \
    --statistic Average \
    --period 300 \
    --threshold 80 \
    --comparison-operator GreaterThanThreshold \
    --evaluation-periods 1 \
    --dimensions Name=InstanceId,Value=$INSTANCE_ID \
    --alarm-actions "$SNS_ARN" \
    > /dev/null 2>&1
echo "   ✓ CPU alarm created"

echo ""
echo "5. Creating status check alarm..."
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
    --dimensions Name=InstanceId,Value=$INSTANCE_ID \
    --alarm-actions "$SNS_ARN" \
    > /dev/null 2>&1
echo "   ✓ Status check alarm created"

echo ""
echo "6. Creating disk usage alarm (>80%)..."
aws cloudwatch put-metric-alarm \
    --region $REGION \
    --alarm-name starscreen-high-disk-usage \
    --alarm-description "Starscreen disk usage exceeds 80%" \
    --metric-name disk_used_percent \
    --namespace CWAgent \
    --statistic Average \
    --period 300 \
    --threshold 80 \
    --comparison-operator GreaterThanThreshold \
    --evaluation-periods 1 \
    --dimensions Name=InstanceId,Value=$INSTANCE_ID Name=path,Value="/" Name=device,Value="xvda1" Name=fstype,Value="ext4" \
    --alarm-actions "$SNS_ARN" \
    > /dev/null 2>&1 && echo "   ✓ Disk usage alarm created" || echo "   ⚠️  Disk alarm creation failed (CloudWatch Agent may not be running yet)"

echo ""
echo "7. Creating memory usage alarm (>80%)..."
aws cloudwatch put-metric-alarm \
    --region $REGION \
    --alarm-name starscreen-high-memory \
    --alarm-description "Starscreen memory usage exceeds 80%" \
    --metric-name mem_used_percent \
    --namespace CWAgent \
    --statistic Average \
    --period 300 \
    --threshold 80 \
    --comparison-operator GreaterThanThreshold \
    --evaluation-periods 1 \
    --dimensions Name=InstanceId,Value=$INSTANCE_ID \
    --alarm-actions "$SNS_ARN" \
    > /dev/null 2>&1 && echo "   ✓ Memory usage alarm created" || echo "   ⚠️  Memory alarm creation failed (CloudWatch Agent may not be running yet)"

echo ""
echo "========================================="
echo "✓ CloudWatch Alarms Created!"
echo "========================================="
echo ""
echo "Alarms created:"
echo "  1. CPU usage >80%"
echo "  2. Status check failures"
echo "  3. Disk usage >80% (requires CloudWatch Agent)"
echo "  4. Memory usage >80% (requires CloudWatch Agent)"
echo ""
echo "You will receive email alerts at: $EMAIL"
echo ""
echo "View alarms in CloudWatch Console:"
echo "https://console.aws.amazon.com/cloudwatch/home?region=$REGION#alarmsV2:"
echo ""
echo "Note: Disk and memory alarms require CloudWatch Agent running on EC2."
echo "If those alarms failed, install the agent on EC2:"
echo "  ssh starscreen 'bash ~/Resume-Analyzer/ec2_install_cloudwatch.sh'"
echo ""
