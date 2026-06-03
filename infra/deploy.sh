
#!/bin/bash
# Agent Assembler SaaS Deployment Script for ECS
# Usage: bash deploy.sh

echo "🚀 Starting Agent Assembler SaaS Deployment..."

# 1. Install Docker (if not present)
if ! [ -x "$(command -v docker)" ]; then
  echo "📦 Installing Docker..."
  curl -fsSL https://get.docker.com | bash
  sudo usermod -aG docker $USER
  echo "✅ Docker installed. Please logout/login and run this script again if needed."
  exit 0
fi

# 2. Build and Run
echo "🔨 Building Docker image..."
sudo docker compose build

echo "🏃 Starting service..."
sudo docker compose up -d

echo "✅ Deployment Complete!"
echo "🌐 Web Dashboard should be available at http://YOUR_ECS_IP:8501"
echo "🔒 Remember to configure Nginx + SSL for production (blackandwhite.vip)."
