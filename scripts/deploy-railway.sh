#!/bin/bash
# Railway deployment script for Dining Philosophers
# This script helps set up and deploy to Railway

set -e

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
CYAN='\033[0;36m'
NC='\033[0m' # No Color

echo -e "${GREEN}Dining Philosophers - Railway Deployment${NC}"
echo ""

# Check if we're in the project root
if [ ! -f "CLAUDE.md" ]; then
    echo -e "${RED}Error: Please run this script from the project root directory${NC}"
    exit 1
fi

# Check for Railway CLI
if ! command -v railway &> /dev/null; then
    echo -e "${RED}Error: Railway CLI not installed${NC}"
    echo ""
    echo "Install it with:"
    echo -e "  ${CYAN}npm install -g @railway/cli${NC}"
    echo "  or"
    echo -e "  ${CYAN}brew install railway${NC}"
    echo ""
    echo "Then login with:"
    echo -e "  ${CYAN}railway login${NC}"
    exit 1
fi

echo -e "${GREEN}✓ Railway CLI found${NC}"

# Check if logged in
if ! railway whoami &> /dev/null; then
    echo -e "${YELLOW}Not logged in to Railway. Running 'railway login'...${NC}"
    railway login
fi

echo -e "${GREEN}✓ Logged in to Railway${NC}"
echo ""

# Menu
echo -e "${YELLOW}What would you like to do?${NC}"
echo "1) Create new Railway project (first time setup)"
echo "2) Deploy backend"
echo "3) Deploy frontend"
echo "4) Deploy both"
echo "5) Show deployment status"
echo "6) Open Railway dashboard"
echo ""
read -p "Enter choice [1-6]: " choice

case $choice in
    1)
        echo ""
        echo -e "${GREEN}=== Creating New Railway Project ===${NC}"
        echo ""
        echo -e "${YELLOW}This will create a new Railway project with:${NC}"
        echo "  - PostgreSQL database"
        echo "  - Backend service (FastAPI)"
        echo "  - Frontend service (Next.js)"
        echo ""
        echo -e "${CYAN}Steps to complete in Railway dashboard:${NC}"
        echo ""
        echo "1. Go to https://railway.app/new"
        echo "2. Click 'Empty Project'"
        echo ""
        echo -e "${CYAN}3. Add PostgreSQL:${NC}"
        echo "   - Click '+ New' → 'Database' → 'Add PostgreSQL'"
        echo ""
        echo -e "${CYAN}4. Add Backend service:${NC}"
        echo "   - Click '+ New' → 'GitHub Repo' → Select this repo"
        echo "   - Name it 'backend'"
        echo "   - Go to Settings → Build → Root Directory → set to 'backend'"
        echo "   - Go to Variables and add:"
        echo "     ANTHROPIC_API_KEY=<your-key>"
        echo "     DATABASE_URL=\${{Postgres.DATABASE_URL}}"
        echo "     CORS_ORIGINS=https://<frontend-url>.up.railway.app"
        echo ""
        echo -e "${CYAN}5. Add Frontend service:${NC}"
        echo "   - Click '+ New' → 'GitHub Repo' → Select this repo"
        echo "   - Name it 'frontend'"
        echo "   - Go to Settings → Build → Root Directory → set to 'frontend'"
        echo "   - Go to Variables and add:"
        echo "     NEXT_PUBLIC_API_URL=https://<backend-url>.up.railway.app"
        echo "     NEXT_PUBLIC_WS_URL=wss://<backend-url>.up.railway.app"
        echo ""
        echo -e "${CYAN}6. Generate domains:${NC}"
        echo "   - For each service: Settings → Networking → Generate Domain"
        echo "   - Update the CORS_ORIGINS and API URLs with the generated domains"
        echo ""
        echo -e "${RED}IMPORTANT: The Root Directory setting is required for monorepos!${NC}"
        echo ""
        echo -e "${YELLOW}Opening Railway dashboard...${NC}"
        open "https://railway.app/new" 2>/dev/null || echo "Visit: https://railway.app/new"
        ;;
    2)
        echo ""
        echo -e "${GREEN}=== Deploying Backend ===${NC}"
        echo -e "${YELLOW}Uploading backend/ as root directory...${NC}"
        railway up backend --service backend --path-as-root
        echo -e "${GREEN}Backend deployed!${NC}"
        ;;
    3)
        echo ""
        echo -e "${GREEN}=== Deploying Frontend ===${NC}"
        echo -e "${YELLOW}Uploading frontend/ as root directory...${NC}"
        railway up frontend --service frontend --path-as-root
        echo -e "${GREEN}Frontend deployed!${NC}"
        ;;
    4)
        echo ""
        echo -e "${GREEN}=== Deploying Both Services ===${NC}"
        echo ""
        echo -e "${YELLOW}Deploying backend...${NC}"
        railway up backend --service backend --path-as-root --detach
        echo ""
        echo -e "${YELLOW}Deploying frontend...${NC}"
        railway up frontend --service frontend --path-as-root --detach
        echo ""
        echo -e "${GREEN}Both services deploying! Check Railway dashboard for build status.${NC}"
        railway open 2>/dev/null || echo "Visit: https://railway.app/dashboard"
        ;;
    5)
        echo ""
        echo -e "${GREEN}=== Deployment Status ===${NC}"
        railway status
        ;;
    6)
        echo ""
        echo -e "${GREEN}Opening Railway dashboard...${NC}"
        railway open 2>/dev/null || echo "Run 'railway open' or visit https://railway.app/dashboard"
        ;;
    *)
        echo -e "${RED}Invalid choice${NC}"
        exit 1
        ;;
esac

echo ""
echo -e "${GREEN}Done!${NC}"
