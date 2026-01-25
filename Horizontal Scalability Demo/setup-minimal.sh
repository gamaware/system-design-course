#!/bin/bash

# Ultra-minimal ECS Workshop Setup Script
# Assumes: Homebrew, AWS CLI, CDK already installed and AWS authenticated

set -e

echo "🚀 Setting up ECS Workshop environment..."

# Create Python virtual environment
echo "🐍 Creating Python virtual environment..."
python3 -m venv venv

# Activate and install Python packages
echo "📦 Installing Python packages..."
source venv/bin/activate
pip install --upgrade pip
pip install -r requirements.txt

# Create environment configuration
echo "⚙️  Setting up environment variables..."
cat > .env << EOF
export AWS_DEFAULT_REGION=us-east-1
export AWS_REGION=us-east-1
export AWS_ACCOUNT_ID=311141527383
export WORKSHOP_NAME=ecsworkshop
export CLUSTER_NAME=container-demo
EOF

# Create activation script
cat > activate.sh << 'EOF'
#!/bin/bash
source venv/bin/activate
source .env
echo "✅ ECS Workshop environment activated!"
echo "Region: $AWS_REGION | Account: $AWS_ACCOUNT_ID"
EOF

chmod +x activate.sh

# Create deactivation script
cat > deactivate.sh << 'EOF'
#!/bin/bash
deactivate 2>/dev/null || true
unset AWS_DEFAULT_REGION AWS_REGION AWS_ACCOUNT_ID WORKSHOP_NAME CLUSTER_NAME
echo "✅ Environment deactivated!"
EOF

chmod +x deactivate.sh

echo ""
echo "🎉 Setup complete!"
echo "📋 Next: source activate.sh"
