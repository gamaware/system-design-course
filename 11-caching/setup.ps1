#Requires -Version 5.1
Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"

$ScriptDir = Split-Path -Parent $MyInvocation.MyCommand.Definition
Set-Location $ScriptDir

Write-Host "=== Lab 11: Caching Patterns with Redis ===" -ForegroundColor Cyan
Write-Host ""

# Check prerequisites
Write-Host "Checking prerequisites..."

try {
    $null = Get-Command docker -ErrorAction Stop
} catch {
    Write-Host "ERROR: Docker is not installed." -ForegroundColor Red
    Write-Host "Install Docker Desktop from https://www.docker.com/products/docker-desktop/"
    exit 1
}

try {
    $null = docker info 2>$null
} catch {
    Write-Host "ERROR: Docker daemon is not running. Start Docker Desktop first." -ForegroundColor Red
    exit 1
}

try {
    $null = docker compose version 2>$null
} catch {
    Write-Host "ERROR: Docker Compose is not available." -ForegroundColor Red
    Write-Host "Docker Compose is included with Docker Desktop."
    exit 1
}

Write-Host "  Docker:         $(docker --version)"
Write-Host "  Docker Compose: $(docker compose version --short)"
Write-Host ""

# Build and start infrastructure
Write-Host "Building and starting Redis + backend..."
docker compose up -d --build redis backend

Write-Host ""
Write-Host "Waiting for services to be healthy..."
$maxAttempts = 30
for ($i = 1; $i -le $maxAttempts; $i++) {
    $redisOk = $false
    $backendOk = $false

    try {
        $ping = docker exec redis-cache redis-cli ping 2>$null
        if ($ping -match "PONG") { $redisOk = $true }
    } catch {}

    try {
        $response = Invoke-WebRequest -Uri "http://localhost:5050/health" -UseBasicParsing -TimeoutSec 2 2>$null
        if ($response.StatusCode -eq 200) { $backendOk = $true }
    } catch {}

    if ($redisOk -and $backendOk) {
        Write-Host "  Redis:   ready"
        Write-Host "  Backend: ready (100 products, 500ms delay per request)"
        break
    }

    if ($i -eq $maxAttempts) {
        Write-Host "ERROR: Services did not become healthy within 30 seconds." -ForegroundColor Red
        Write-Host "Run 'docker compose logs' to check for errors."
        exit 1
    }

    Start-Sleep -Seconds 1
}

# Verify data
Write-Host ""
Write-Host "Verifying backend data..."
foreach ($id in @(1, 50, 100)) {
    try {
        $response = Invoke-WebRequest -Uri "http://localhost:5050/products/$id" -UseBasicParsing -TimeoutSec 5
        if ($response.StatusCode -ne 200) {
            Write-Host "ERROR: Backend returned $($response.StatusCode) for product $id" -ForegroundColor Red
            exit 1
        }
    } catch {
        Write-Host "ERROR: Could not reach backend for product $id" -ForegroundColor Red
        exit 1
    }
}
Write-Host "Backend is running with product data (100 products available)."

Write-Host ""
Write-Host "=== Environment ready ===" -ForegroundColor Green
Write-Host ""
Write-Host "Choose your language and start the lab:"
Write-Host ""
Write-Host "  C++:    docker compose --profile cpp up --build"
Write-Host "  C#:     docker compose --profile csharp up --build"
Write-Host "  Java:   docker compose --profile java up --build"
Write-Host ""
Write-Host "Redis CLI (for monitoring):"
Write-Host "  docker exec -it redis-cache redis-cli"
Write-Host "  docker exec -it redis-cache redis-cli MONITOR"
Write-Host ""
Write-Host "Follow the instructions in LAB-WINDOWS.md for the full walkthrough."
