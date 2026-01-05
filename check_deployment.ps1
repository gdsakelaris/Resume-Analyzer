# PowerShell version of check_deployment.sh for Windows
# Quick deployment health check for Starscreen

$INSTANCE_IP = "54.158.113.25"
$SSH_KEY = "C:\Users\gdsak\OneDrive\Desktop\starsceen_key.pem"

Write-Host "========================================" -ForegroundColor Cyan
Write-Host "Starscreen Deployment Health Check" -ForegroundColor Cyan
Write-Host "========================================" -ForegroundColor Cyan
Write-Host ""

# Test HTTPS endpoint
Write-Host "1. Testing HTTPS endpoint..."
try
{
    $response = Invoke-WebRequest -Uri "https://starscreen.net" -TimeoutSec 10 -UseBasicParsing -ErrorAction Stop
    $statusCode = $response.StatusCode
    if ($statusCode -in @(200, 307, 308, 405))
    {
        Write-Host "   ✓ Server is responding (HTTP $statusCode)" -ForegroundColor Green
    }
    else
    {
        Write-Host "   ✗ Server not responding (HTTP $statusCode)" -ForegroundColor Red
    }
}
catch
{
    Write-Host "   ✗ Server not responding" -ForegroundColor Red
}

# Test API health endpoint
Write-Host ""
Write-Host "2. Testing API health endpoint..."
try
{
    $health = Invoke-RestMethod -Uri "https://starscreen.net/api/v1/health/" -TimeoutSec 10 -ErrorAction Stop
    if ($health.status -eq "healthy")
    {
        Write-Host "   ✓ API is healthy" -ForegroundColor Green
        Write-Host "   Response: $($health | ConvertTo-Json -Compress)"
    }
    else
    {
        Write-Host "   ✗ API health check failed" -ForegroundColor Red
    }
}
catch
{
    Write-Host "   ✗ API not responding" -ForegroundColor Red
}

# Test SSH connectivity
Write-Host ""
Write-Host "3. Testing SSH connectivity..."
$SSH_WORKS = $false
if (Test-Path $SSH_KEY)
{
    try
    {
        $sshResult = & ssh -i $SSH_KEY -o ConnectTimeout=10 -o StrictHostKeyChecking=no ubuntu@$INSTANCE_IP "echo SSH_WORKS" 2>&1
        if ($sshResult -match "SSH_WORKS")
        {
            Write-Host "   ✓ SSH connection successful" -ForegroundColor Green
            $SSH_WORKS = $true
        }
        else
        {
            Write-Host "   ✗ SSH connection failed" -ForegroundColor Red
        }
    }
    catch
    {
        Write-Host "   ✗ SSH connection failed" -ForegroundColor Red
    }
}
else
{
    Write-Host "   ✗ SSH key not found at: $SSH_KEY" -ForegroundColor Red
}

# If SSH works, do detailed checks
if ($SSH_WORKS)
{
    Write-Host ""
    Write-Host "========================================" -ForegroundColor Cyan
    Write-Host "EC2 Detailed Diagnostics" -ForegroundColor Cyan
    Write-Host "========================================" -ForegroundColor Cyan

    Write-Host ""
    Write-Host "4. Checking Docker containers status..."
    & ssh -i $SSH_KEY -o ConnectTimeout=10 -o StrictHostKeyChecking=no ubuntu@$INSTANCE_IP "cd ~/Resume-Analyzer; docker-compose ps" 2>&1

    Write-Host ""
    Write-Host "5. Checking disk space..."
    & ssh -i $SSH_KEY -o ConnectTimeout=10 -o StrictHostKeyChecking=no ubuntu@$INSTANCE_IP "df -h /" 2>&1

    Write-Host ""
    Write-Host "6. Checking memory usage..."
    & ssh -i $SSH_KEY -o ConnectTimeout=10 -o StrictHostKeyChecking=no ubuntu@$INSTANCE_IP "free -h" 2>&1

    Write-Host ""
    Write-Host "7. Recent API logs (last 20 lines)..."
    & ssh -i $SSH_KEY -o ConnectTimeout=10 -o StrictHostKeyChecking=no ubuntu@$INSTANCE_IP "cd ~/Resume-Analyzer; docker-compose logs --tail=20 api" 2>&1

    Write-Host ""
    Write-Host "8. Container resource usage..."
    & ssh -i $SSH_KEY -o ConnectTimeout=10 -o StrictHostKeyChecking=no ubuntu@$INSTANCE_IP "docker stats --no-stream" 2>&1
}
else
{
    Write-Host ""
    Write-Host "========================================" -ForegroundColor Yellow
    Write-Host "⚠️  Cannot SSH to EC2" -ForegroundColor Yellow
    Write-Host "========================================" -ForegroundColor Yellow
    Write-Host ""
    Write-Host "AWS Console:" -ForegroundColor Cyan
    Write-Host "https://console.aws.amazon.com/ec2/home?region=us-east-1#Instances:instanceId=i-081c728682b8917d2"
}

Write-Host ""
Write-Host "========================================" -ForegroundColor Cyan
Write-Host "GitHub Actions Status" -ForegroundColor Cyan
Write-Host "========================================" -ForegroundColor Cyan
Write-Host "Check latest deployment:"
Write-Host "https://github.com/gdsakelaris/Resume-Analyzer/actions"
Write-Host ""
