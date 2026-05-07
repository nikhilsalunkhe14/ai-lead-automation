#!/bin/bash

# AI Lead Automation - Deployment Script
echo "🚀 Starting AI Lead Automation Deployment..."

# Check if required tools are installed
command -v render >/dev/null 2>&1 || { echo "❌ Render CLI not installed. Please install: pip install render-cli"; exit 1; }
command -v git >/dev/null 2>&1 || { echo "❌ Git not installed. Please install Git."; exit 1; }

# Validate environment
echo "📋 Validating deployment environment..."
if [ ! -f ".env.production" ]; then
    echo "❌ .env.production file not found. Please create it with production variables."
    exit 1
fi

# Check required environment variables
source .env.production
required_vars=("MONGODB_URI" "GROQ_API_KEY" "RESEND_API_KEY" "FLASK_SECRET_KEY")
for var in "${required_vars[@]}"; do
    if [ -z "${!var}" ] || [ "${!var}" = "your_${var,,}_here" ]; then
        echo "❌ Required environment variable $var is not set in .env.production"
        exit 1
    fi
done

echo "✅ Environment validation passed"

# Run tests before deployment
echo "🧪 Running pre-deployment tests..."
python -m pytest tests/ -v
if [ $? -ne 0 ]; then
    echo "❌ Tests failed. Deployment aborted."
    exit 1
fi

echo "✅ All tests passed"

# Deploy to Render
echo "🚀 Deploying to Render..."
render deploy

# Verify deployment
echo "🔍 Verifying deployment..."
sleep 30
HEALTH_CHECK=$(curl -s -o /dev/null -w "%{http_code}" https://your-app-name.onrender.com/api/health)
if [ "$HEALTH_CHECK" = "200" ]; then
    echo "✅ Deployment successful! Application is healthy."
else
    echo "❌ Deployment verification failed. Health check returned: $HEALTH_CHECK"
    exit 1
fi

echo "🎉 AI Lead Automation deployed successfully!"
echo "🌐 Live at: https://your-app-name.onrender.com"
echo "📊 Admin Dashboard: https://your-app-name.onrender.com/admin_dashboard"
echo "🧠 Context Analytics: https://your-app-name.onrender.com/context_dashboard"
