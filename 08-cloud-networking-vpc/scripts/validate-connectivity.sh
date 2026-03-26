#!/bin/bash
# validate-connectivity.sh — Automated connectivity tests for Lab 08
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
# Usage: ./scripts/validate-connectivity.sh

set -euo pipefail

SCRIPT_DIR="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" >/dev/null 2>&1 && pwd -P)"
cd "$SCRIPT_DIR/.."

echo "========================================="
echo "Lab 08 — Connectivity Validation"
echo "========================================="
echo ""

# --- Get instance IPs from Terraform outputs ---
cd terraform
EC2_1_IP=$(terraform output -raw ec2_1_public_ip 2>/dev/null || echo "")
EC2_2_IP=$(terraform output -raw ec2_2_public_ip 2>/dev/null || echo "")
cd ..

if [ "$EC2_1_IP" = "" ] || [ "$EC2_2_IP" = "" ]; then
  echo "ERROR: Could not read Terraform outputs."
  echo "Make sure you have run 'terraform apply' first."
  exit 1
fi

echo "EC2-1 Public IP: $EC2_1_IP"
echo "EC2-2 Public IP: $EC2_2_IP"
echo ""

PASS=0
FAIL=0

# --- Test 1: Ping EC2-1 ---
echo "Test 1: Ping EC2-1 ($EC2_1_IP)..."
if ping -c 2 -W 5 "$EC2_1_IP" >/dev/null 2>&1; then
  echo "  PASS"
  PASS=$((PASS + 1))
else
  echo "  FAIL — EC2-1 not reachable via ICMP"
  FAIL=$((FAIL + 1))
fi

# --- Test 2: Ping EC2-2 ---
echo "Test 2: Ping EC2-2 ($EC2_2_IP)..."
if ping -c 2 -W 5 "$EC2_2_IP" >/dev/null 2>&1; then
  echo "  PASS"
  PASS=$((PASS + 1))
else
  echo "  FAIL — EC2-2 not reachable via ICMP"
  FAIL=$((FAIL + 1))
fi

# --- Test 3: HTTP on EC2-1 ---
echo "Test 3: HTTP response from EC2-1..."
if curl -s --max-time 10 "http://$EC2_1_IP" | grep -q "EC2-1"; then
  echo "  PASS"
  PASS=$((PASS + 1))
else
  echo "  FAIL — HTTP not responding or wrong content"
  FAIL=$((FAIL + 1))
fi

# --- Test 4: HTTP on EC2-2 ---
echo "Test 4: HTTP response from EC2-2..."
if curl -s --max-time 10 "http://$EC2_2_IP" | grep -q "EC2-2"; then
  echo "  PASS"
  PASS=$((PASS + 1))
else
  echo "  FAIL — HTTP not responding or wrong content"
  FAIL=$((FAIL + 1))
fi

# --- Test 5: SSH port open on EC2-1 ---
echo "Test 5: SSH port 22 open on EC2-1..."
if nc -z -w 5 "$EC2_1_IP" 22 2>/dev/null; then
  echo "  PASS"
  PASS=$((PASS + 1))
else
  echo "  FAIL — SSH port not reachable"
  FAIL=$((FAIL + 1))
fi

# --- Summary ---
echo ""
echo "========================================="
echo "Results: $PASS passed, $FAIL failed"
echo "========================================="

if [ "$FAIL" -gt 0 ]; then
  exit 1
fi
