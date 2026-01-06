@echo off
REM Quick deployment test for Windows (uses curl)

echo Testing EC2 connectivity...
echo.

echo 1. Testing HTTPS endpoint...
curl -s -o nul -w "   HTTP %%{http_code}\n" --connect-timeout 10 https://starscreen.net
echo.

echo 2. Testing API health endpoint...
curl -s --connect-timeout 10 https://starscreen.net/api/v1/health/
echo.
echo.

echo 3. For detailed diagnostics, SSH to EC2:
echo    ssh starscreen
echo    bash check_local_health.sh
echo.
