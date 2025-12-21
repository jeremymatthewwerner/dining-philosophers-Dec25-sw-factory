#!/bin/bash
# Initial setup script for Dining Philosophers development

set -e

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

echo -e "${GREEN}Setting up Dining Philosophers Development Environment${NC}"
echo ""

# Check if we're in the project root
if [ ! -f "CLAUDE.md" ]; then
    echo -e "${RED}Error: Please run this script from the project root directory${NC}"
    exit 1
fi

# Check prerequisites
echo -e "${YELLOW}Checking prerequisites...${NC}"

if ! command -v uv &> /dev/null; then
    echo -e "${RED}Error: 'uv' is not installed. Install it from https://docs.astral.sh/uv/${NC}"
    exit 1
fi
echo -e "${GREEN}✓ uv found${NC}"

if ! command -v node &> /dev/null; then
    echo -e "${RED}Error: 'node' is not installed. Install it from https://nodejs.org/${NC}"
    exit 1
fi
echo -e "${GREEN}✓ node found ($(node --version))${NC}"

if ! command -v npm &> /dev/null; then
    echo -e "${RED}Error: 'npm' is not installed${NC}"
    exit 1
fi
echo -e "${GREEN}✓ npm found ($(npm --version))${NC}"

echo ""

# Setup backend
echo -e "${YELLOW}Setting up backend...${NC}"
cd backend

# Install Python dependencies
echo "Installing Python dependencies..."
uv sync

# Create .env if it doesn't exist
if [ ! -f ".env" ]; then
    cp .env.example .env
    echo -e "${GREEN}Created backend/.env from template${NC}"
    echo -e "${YELLOW}Note: Add your ANTHROPIC_API_KEY to backend/.env for Claude-powered responses${NC}"
fi

cd ..

# Setup frontend
echo ""
echo -e "${YELLOW}Setting up frontend...${NC}"
cd frontend

# Install Node dependencies
echo "Installing Node dependencies..."
npm install

# Create .env.local if it doesn't exist
if [ ! -f ".env.local" ]; then
    cp .env.local.example .env.local
    echo -e "${GREEN}Created frontend/.env.local from template${NC}"
fi

cd ..

# Make scripts executable
chmod +x scripts/*.sh

echo ""
echo -e "${GREEN}========================================${NC}"
echo -e "${GREEN}Setup complete!${NC}"
echo -e "${GREEN}========================================${NC}"
echo ""
echo "To start development:"
echo -e "  ${YELLOW}./scripts/dev.sh${NC}"
echo ""
echo "To run tests:"
echo -e "  ${YELLOW}./scripts/test-all.sh${NC}"
echo ""
echo -e "${YELLOW}Don't forget to add your ANTHROPIC_API_KEY to backend/.env${NC}"
echo "Without it, the app will use mock thinker responses."
echo ""
