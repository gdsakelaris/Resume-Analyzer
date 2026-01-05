# PowerShell version of test_deployment.sh for Windows
# Quick test to verify deployment is working

Write-Host "Testing EC2 connectivity..." -ForegroundColor Cyan
Write-Host ""

# Test HTTPS endpoint
Write-Host "1. Testing HTTPS endpoint..."
try {
    $response = Invoke-WebRequest -Uri "https://starscreen.net" -TimeoutSec 10 -UseBasicParsing -ErrorAction Stop
    $statusCode = $response.StatusCode
    if ($statusCode -in @(200, 307, 308, 405)) {
        Write-Host "   ✓ Server is responding (HTTP $statusCode)" -ForegroundColor Green
    } else {
        Write-Host "   ✗ Server not responding (HTTP $statusCode)" -ForegroundColor Red
    }
} catch {
    Write-Host "   ✗ Server not responding" -ForegroundColor Red
}

# Test API health endpoint
Write-Host ""
Write-Host "2. Testing API health endpoint..."
$HEALTHY = $false
try {
    $health = Invoke-RestMethod -Uri "https://starscreen.net/api/v1/health/" -TimeoutSec 10 -ErrorAction Stop
    if ($health.status -eq "healthy") {
        Write-Host "   ✓ API is healthy" -ForegroundColor Green
        Write-Host "   Response: $($health | ConvertTo-Json -Compress)" -ForegroundColor Gray
        $HEALTHY = $true
    } else {
        Write-Host "   ✗ API health check failed" -ForegroundColor Red
        Write-Host "   Response: $($health | ConvertTo-Json -Compress)" -ForegroundColor Gray
    }
} catch {
    Write-Host "   ✗ API health check failed" -ForegroundColor Red
}

# Test SSH connection
Write-Host ""
Write-Host "3. Testing SSH connection..."
$SSH_KEY = "C:\Users\gdsak\OneDrive\Desktop\starsceen_key.pem"
if (Test-Path $SSH_KEY) {
    $sshCmd = "ssh -i `"$SSH_KEY`" -o ConnectTimeout=10 -o StrictHostKeyChecking=no ubuntu@54.158.113.25 `"echo SSH_WORKS`""
    $sshResult = Invoke-Expression $sshCmd 2>&1
    if ($sshResult -match "SSH_WORKS") {
        Write-Host "   ✓ SSH works" -ForegroundColor Green
    } else {
        Write-Host "   ⊘ SSH connection issue" -ForegroundColor Yellow
    }
} else {
    Write-Host "   ⊘ SSH key not found" -ForegroundColor Yellow
}

# Summary
Write-Host ""
Write-Host "=========================================" -ForegroundColor Cyan
if ($HEALTHY) {
    Write-Host "✓ Deployment is working!" -ForegroundColor Green
} else {
    Write-Host "⚠ Deployment may have issues" -ForegroundColor Yellow
}
Write-Host "=========================================" -ForegroundColor Cyan
