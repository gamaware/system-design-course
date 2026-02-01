#!/bin/bash
deactivate 2>/dev/null || true
unset AWS_DEFAULT_REGION AWS_REGION AWS_ACCOUNT_ID WORKSHOP_NAME CLUSTER_NAME
echo "✅ Environment deactivated!"
