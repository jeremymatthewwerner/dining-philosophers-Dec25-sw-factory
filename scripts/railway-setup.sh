#!/bin/bash
# Railway deployment setup script
# This script configures Railway services for the thinkers-chat monorepo

set -e

echo "=== Railway Setup for Dining Philosophers ==="
echo ""

# Check if railway CLI is installed
if ! command -v railway &> /dev/null; then
    echo "Error: Railway CLI not installed. Install with: npm install -g @railway/cli"
    exit 1
fi

# Check if logged in
if ! railway whoami &> /dev/null; then
    echo "Please login to Railway first:"
    railway login
fi

echo "This script will set up the backend and frontend services."
echo "Make sure you have already:"
echo "  1. Created a Railway project"
echo "  2. Added a PostgreSQL database"
echo "  3. Connected the GitHub repo"
echo ""
read -p "Press Enter to continue or Ctrl+C to cancel..."

# Link to project (interactive)
echo ""
echo "=== Linking to Railway project ==="
railway link

# Setup backend service
echo ""
echo "=== Setting up Backend Service ==="
railway service link backend

# Set backend environment variables
echo "Setting backend variables..."
railway variables --set "RAILWAY_DOCKERFILE_PATH=backend/Dockerfile"

echo ""
echo "Backend configured. You must manually set in dashboard:"
echo "  - Settings > Root Directory: / (leave empty or set to /)"
echo "  - Settings > Build > Dockerfile Path: backend/Dockerfile"
echo ""

# Setup frontend service
echo "=== Setting up Frontend Service ==="
railway service link frontend

# Set frontend environment variables
echo "Setting frontend variables..."
railway variables --set "RAILWAY_DOCKERFILE_PATH=frontend/Dockerfile"

echo ""
echo "Frontend configured. You must manually set in dashboard:"
echo "  - Settings > Root Directory: / (leave empty or set to /)"
echo "  - Settings > Build > Dockerfile Path: frontend/Dockerfile"
echo ""

echo "=== Setup Complete ==="
echo ""
echo "Required environment variables (set in Railway dashboard):"
echo ""
echo "Backend:"
echo "  - ANTHROPIC_API_KEY: Your Anthropic API key"
echo "  - DATABASE_URL: (auto-set if using Railway PostgreSQL)"
echo "  - CORS_ORIGINS: https://your-frontend-domain.up.railway.app"
echo ""
echo "Frontend:"
echo "  - NEXT_PUBLIC_API_URL: https://your-backend-domain.up.railway.app"
echo "  - NEXT_PUBLIC_WS_URL: wss://your-backend-domain.up.railway.app"
echo ""
echo "After setting variables, trigger a redeploy for each service."
