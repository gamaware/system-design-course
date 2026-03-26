# validate-connectivity.ps1 — Automated connectivity tests for Lab 08 (Windows/PowerShell)
#
# Reads EC2 instance IPs from Terraform outputs and runs 5 tests:
#   1. Ping EC2-1 (ICMP reachability)
#   2. Ping EC2-2 (ICMP reachability)
#   3. HTTP response from EC2-1 (web server content check)
#   4. HTTP response from EC2-2 (web server content check)
#   5. SSH port 22 open on EC2-1 (TCP connectivity)
#
# Prerequisites: Terraform must have been applied (terraform.tfstate exists).
# Exit code: 0 if all tests pass, 1 if any test fails.
#
# Usage: .\scripts\validate-connectivity.ps1

$ErrorActionPreference = "Continue"

Push-Location "$PSScriptRoot\..\terraform"
$EC2_1_IP = terraform output -raw ec2_1_public_ip 2>$null
$EC2_2_IP = terraform output -raw ec2_2_public_ip 2>$null
Pop-Location

if (-not $EC2_1_IP -or -not $EC2_2_IP) {
    Write-Output "ERROR: Could not read Terraform outputs."
    Write-Output "Make sure you have run 'terraform apply' first."
    exit 1
}

Write-Output "========================================="
Write-Output "Lab 08 — Connectivity Validation"
Write-Output "========================================="
Write-Output ""
Write-Output "EC2-1 Public IP: $EC2_1_IP"
Write-Output "EC2-2 Public IP: $EC2_2_IP"
Write-Output ""

$Pass = 0
$Fail = 0

# --- Test 1: Ping EC2-1 ---
Write-Output "Test 1: Ping EC2-1 ($EC2_1_IP)..."
if (Test-Connection -ComputerName $EC2_1_IP -Count 2 -Quiet) {
    Write-Output "  PASS"
    $Pass++
} else {
    Write-Output "  FAIL — EC2-1 not reachable via ICMP"
    $Fail++
}

# --- Test 2: Ping EC2-2 ---
Write-Output "Test 2: Ping EC2-2 ($EC2_2_IP)..."
if (Test-Connection -ComputerName $EC2_2_IP -Count 2 -Quiet) {
    Write-Output "  PASS"
    $Pass++
} else {
    Write-Output "  FAIL — EC2-2 not reachable via ICMP"
    $Fail++
}

# --- Test 3: HTTP on EC2-1 ---
Write-Output "Test 3: HTTP response from EC2-1..."
try {
    $response = Invoke-WebRequest -Uri "http://$EC2_1_IP" -TimeoutSec 10 -UseBasicParsing
    if ($response.Content -match "EC2-1") {
        Write-Output "  PASS"
        $Pass++
    } else {
        Write-Output "  FAIL — Wrong content"
        $Fail++
    }
} catch {
    Write-Output "  FAIL — HTTP not responding"
    $Fail++
}

# --- Test 4: HTTP on EC2-2 ---
Write-Output "Test 4: HTTP response from EC2-2..."
try {
    $response = Invoke-WebRequest -Uri "http://$EC2_2_IP" -TimeoutSec 10 -UseBasicParsing
    if ($response.Content -match "EC2-2") {
        Write-Output "  PASS"
        $Pass++
    } else {
        Write-Output "  FAIL — Wrong content"
        $Fail++
    }
} catch {
    Write-Output "  FAIL — HTTP not responding"
    $Fail++
}

# --- Test 5: SSH port open on EC2-1 ---
Write-Output "Test 5: SSH port 22 open on EC2-1..."
try {
    $tcp = New-Object System.Net.Sockets.TcpClient
    $tcp.Connect($EC2_1_IP, 22)
    $tcp.Close()
    Write-Output "  PASS"
    $Pass++
} catch {
    Write-Output "  FAIL — SSH port not reachable"
    $Fail++
}

# --- Summary ---
Write-Output ""
Write-Output "========================================="
Write-Output "Results: $Pass passed, $Fail failed"
Write-Output "========================================="

if ($Fail -gt 0) { exit 1 }
