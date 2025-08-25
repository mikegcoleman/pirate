@echo off
REM Pirate LLM API Deployment Script for Windows
REM Usage: deploy.bat [restart|rebuild|hub]

setlocal

set DEPLOY_TYPE=%1
if "%DEPLOY_TYPE%"=="" set DEPLOY_TYPE=restart

echo ========================================
echo 🏴‍☠️ Pirate LLM API Deployment
echo ========================================

if "%DEPLOY_TYPE%"=="hub" goto :deploy_hub
if "%DEPLOY_TYPE%"=="restart" goto :deploy_restart
if "%DEPLOY_TYPE%"=="rebuild" goto :deploy_rebuild

echo Invalid deployment type. Use 'restart', 'rebuild', or 'hub'
exit /b 1

:deploy_restart
echo 📍 Restarting with volume-mounted code (fast)
echo.

echo 🔄 Restarting container with new code...
docker-compose restart
if errorlevel 1 (
    echo ❌ Failed to restart container!
    exit /b 1
)

goto :verify

:deploy_rebuild
echo 📍 Full rebuild (slow - only when dependencies change)
echo.

echo ⏹️  Stopping existing container...
docker-compose down

echo 🔨 Building Docker image...
docker build -t mgc0216/pirate-api:latest .
if errorlevel 1 (
    echo ❌ Build failed!
    exit /b 1
)

echo 🟢 Starting new container...
docker-compose up -d
if errorlevel 1 (
    echo ❌ Failed to start container!
    exit /b 1
)

goto :verify

:deploy_hub
echo 📍 Deploying from Docker Hub
echo.

echo ⏹️  Stopping existing container...
docker-compose down

echo 📥 Pulling latest image from Docker Hub...
docker pull mgc0216/pirate-api:latest
if errorlevel 1 (
    echo ❌ Failed to pull image!
    exit /b 1
)

echo 🟢 Starting container with latest image...
docker-compose up -d
if errorlevel 1 (
    echo ❌ Failed to start container!
    exit /b 1
)

goto :verify

:verify
echo.
echo ⏳ Waiting for service to start...
timeout /t 5 /nobreak > nul

echo 🏥 Checking service health...
curl -f http://localhost:8080/health
if errorlevel 1 (
    echo ❌ Health check failed! Check logs with: docker-compose logs
    goto :show_status
)

echo ✅ Deployment successful!

:show_status
echo.
echo 📊 Current status:
docker ps --filter "name=pirate-api"

echo.
echo 📋 Recent logs:
docker-compose logs --tail=5

echo.
echo ========================================
echo 🎉 Deployment complete!
echo 📍 API available at: http://localhost:8080
echo 🏥 Health check: http://localhost:8080/health
echo 📋 View logs: docker-compose logs
echo ========================================