#!/bin/bash
# Setup GitHub Apps for the Autonomous Software Factory
#
# This script guides you through creating GitHub Apps for each agent role.
# Each agent will have its own identity, enabling:
# - Distinct @mentions that trigger workflows
# - Issue assignment to agent accounts
# - Clear audit trail of which agent did what
#
# Usage: ./scripts/setup-github-apps.sh

set -euo pipefail

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Get repo info
REPO_OWNER=$(gh repo view --json owner -q '.owner.login' 2>/dev/null || echo "")
REPO_NAME=$(gh repo view --json name -q '.name' 2>/dev/null || echo "")

if [ -z "$REPO_OWNER" ] || [ -z "$REPO_NAME" ]; then
    echo -e "${RED}Error: Could not determine repository. Run this from the repo root with gh CLI authenticated.${NC}"
    exit 1
fi

echo -e "${BLUE}========================================${NC}"
echo -e "${BLUE}GitHub Apps Setup for Software Factory${NC}"
echo -e "${BLUE}========================================${NC}"
echo ""
echo -e "Repository: ${GREEN}$REPO_OWNER/$REPO_NAME${NC}"
echo ""

# Define the apps to create
declare -A APPS=(
    ["code-agent"]="DP Code Agent|Fixes bugs and implements features"
    ["factory-manager"]="DP Factory Manager|Monitors and maintains the factory"
    ["devops"]="DP DevOps Agent|Infrastructure and incident response"
    ["triage"]="DP Triage Agent|Classifies issues and adds labels"
    ["qa"]="DP QA Agent|Test quality improvement"
)

# Check if manifests exist
MANIFEST_DIR=".github/apps"
if [ ! -d "$MANIFEST_DIR" ]; then
    echo -e "${RED}Error: Manifest directory $MANIFEST_DIR not found.${NC}"
    exit 1
fi

echo -e "${YELLOW}This script will guide you through creating 5 GitHub Apps.${NC}"
echo ""
echo "For each app, you will:"
echo "  1. Click a link to create the app on GitHub"
echo "  2. Confirm the settings (pre-filled from manifest)"
echo "  3. Generate a private key"
echo "  4. Save the App ID and private key"
echo ""
echo -e "${YELLOW}The apps will be created under your account: $REPO_OWNER${NC}"
echo ""
read -p "Press Enter to continue or Ctrl+C to cancel..."

# Store created apps info
CREATED_APPS=""

for app_key in "${!APPS[@]}"; do
    IFS='|' read -r app_name app_desc <<< "${APPS[$app_key]}"
    manifest_file="$MANIFEST_DIR/$app_key.json"

    if [ ! -f "$manifest_file" ]; then
        echo -e "${YELLOW}Warning: Manifest not found for $app_key, skipping.${NC}"
        continue
    fi

    echo ""
    echo -e "${BLUE}========================================${NC}"
    echo -e "${BLUE}Creating: $app_name${NC}"
    echo -e "${BLUE}========================================${NC}"
    echo -e "Description: $app_desc"
    echo ""

    # Read the manifest
    MANIFEST_CONTENT=$(cat "$manifest_file")

    # URL-encode the manifest for the creation URL
    # Note: GitHub's manifest flow uses a POST, but we can link to the creation page
    echo -e "To create this app:"
    echo ""
    echo -e "  1. Go to: ${GREEN}https://github.com/settings/apps/new${NC}"
    echo ""
    echo -e "  2. Fill in these settings:"
    echo -e "     - GitHub App name: ${GREEN}$app_name${NC}"
    echo -e "     - Homepage URL: ${GREEN}https://github.com/$REPO_OWNER/$REPO_NAME${NC}"
    echo -e "     - Uncheck 'Active' under Webhook (we don't need webhooks)"
    echo ""
    echo -e "  3. Set permissions (from manifest):"

    # Parse and display permissions from manifest
    echo "$MANIFEST_CONTENT" | jq -r '.default_permissions | to_entries[] | "     - \(.key): \(.value)"'

    echo ""
    echo -e "  4. Subscribe to events:"
    echo "$MANIFEST_CONTENT" | jq -r '.default_events[]? | "     - \(.)"'

    echo ""
    echo -e "  5. Set 'Where can this GitHub App be installed?' to:"
    echo -e "     ${GREEN}Only on this account${NC}"
    echo ""
    echo -e "  6. Click 'Create GitHub App'"
    echo ""
    echo -e "  7. After creation, note the ${GREEN}App ID${NC} shown on the app page"
    echo ""
    echo -e "  8. Scroll down to 'Private keys' and click ${GREEN}Generate a private key${NC}"
    echo -e "     (A .pem file will download)"
    echo ""

    read -p "Press Enter when you've created '$app_name' and have the App ID and private key..."

    # Prompt for App ID
    read -p "Enter the App ID for $app_name: " APP_ID

    # Prompt for private key file path
    echo "Enter the path to the downloaded private key file (.pem):"
    read -p "Path: " PEM_PATH

    if [ ! -f "$PEM_PATH" ]; then
        echo -e "${RED}Warning: File not found at $PEM_PATH${NC}"
        read -p "Continue anyway? (y/n): " CONTINUE
        if [ "$CONTINUE" != "y" ]; then
            continue
        fi
    fi

    # Convert app_key to uppercase for secret names
    SECRET_PREFIX=$(echo "$app_key" | tr '[:lower:]-' '[:upper:]_')
    APP_ID_SECRET="${SECRET_PREFIX}_APP_ID"
    PRIVATE_KEY_SECRET="${SECRET_PREFIX}_PRIVATE_KEY"

    echo ""
    echo -e "Storing secrets in repository..."

    # Store App ID as secret
    echo "$APP_ID" | gh secret set "$APP_ID_SECRET" --repo "$REPO_OWNER/$REPO_NAME"
    echo -e "${GREEN}✓ Stored $APP_ID_SECRET${NC}"

    # Store private key as secret
    if [ -f "$PEM_PATH" ]; then
        gh secret set "$PRIVATE_KEY_SECRET" --repo "$REPO_OWNER/$REPO_NAME" < "$PEM_PATH"
        echo -e "${GREEN}✓ Stored $PRIVATE_KEY_SECRET${NC}"
    fi

    CREATED_APPS="$CREATED_APPS\n  - $app_name (App ID: $APP_ID)"

    echo ""
    echo -e "${GREEN}✓ $app_name setup complete!${NC}"
    echo ""

    # Install the app on the repo
    echo -e "Now install the app on this repository:"
    echo -e "  1. Go to: ${GREEN}https://github.com/settings/apps/${app_name// /-}/installations${NC}"
    echo -e "  2. Click 'Install'"
    echo -e "  3. Select 'Only select repositories' and choose ${GREEN}$REPO_NAME${NC}"
    echo ""
    read -p "Press Enter when installation is complete..."
done

echo ""
echo -e "${GREEN}========================================${NC}"
echo -e "${GREEN}Setup Complete!${NC}"
echo -e "${GREEN}========================================${NC}"
echo ""
echo -e "Created apps:${CREATED_APPS}"
echo ""
echo "Secrets stored in repository:"
for app_key in "${!APPS[@]}"; do
    SECRET_PREFIX=$(echo "$app_key" | tr '[:lower:]-' '[:upper:]_')
    echo "  - ${SECRET_PREFIX}_APP_ID"
    echo "  - ${SECRET_PREFIX}_PRIVATE_KEY"
done
echo ""
echo -e "${YELLOW}Next steps:${NC}"
echo "  1. Update workflow files to use the new app tokens"
echo "  2. See docs/GITHUB_APPS.md for workflow integration guide"
echo ""
