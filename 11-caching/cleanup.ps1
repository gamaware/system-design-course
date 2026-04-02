#Requires -Version 5.1
Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"

$ScriptDir = Split-Path -Parent $MyInvocation.MyCommand.Definition
Set-Location $ScriptDir

Write-Host "=== Lab 11: Cleanup ===" -ForegroundColor Cyan
Write-Host ""

Write-Host "Stopping all containers..."
docker compose --profile cpp --profile csharp --profile java down -v 2>$null
if ($LASTEXITCODE -ne 0) { Write-Host "  (no containers were running)" }

Write-Host "Removing locally built images..."
docker compose --profile cpp --profile csharp --profile java down --rmi local 2>$null
if ($LASTEXITCODE -ne 0) { Write-Host "  (no local images to remove)" }

Write-Host ""
Write-Host "Cleanup complete. All containers, volumes, and images removed." -ForegroundColor Green
