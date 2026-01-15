#!/bin/bash
#
# Claude Software Factory - Automated Setup
#
# This script automates the setup of a Claude Software Factory for your repo.
# It handles:
# 1. GitHub repository configuration (labels, secrets)
# 2. Slack app creation guidance
# 3. Railway deployment
# 4. Validation that everything works
#
# Prerequisites:
# - gh CLI (GitHub CLI) installed and authenticated
# - railway CLI installed and authenticated (optional, for Railway deployment)
# - A GitHub repository (this one or a fork)
#
# Usage:
#   ./scripts/setup-factory.sh
#
set -e

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
CYAN='\033[0;36m'
NC='\033[0m' # No Color
BOLD='\033[1m'

# State file to track progress
STATE_FILE=".factory-setup-state"

print_header() {
    echo ""
    echo -e "${BLUE}${BOLD}═══════════════════════════════════════════════════════════════${NC}"
    echo -e "${BLUE}${BOLD}  $1${NC}"
    echo -e "${BLUE}${BOLD}═══════════════════════════════════════════════════════════════${NC}"
    echo ""
}

print_step() {
    echo -e "${CYAN}▶ $1${NC}"
}

print_success() {
    echo -e "${GREEN}✓ $1${NC}"
}

print_warning() {
    echo -e "${YELLOW}⚠ $1${NC}"
}

print_error() {
    echo -e "${RED}✗ $1${NC}"
}

print_info() {
    echo -e "${BLUE}ℹ $1${NC}"
}

# Check if a command exists
command_exists() {
    command -v "$1" >/dev/null 2>&1
}

# Save state
save_state() {
    echo "$1=$2" >> "$STATE_FILE"
}

# Load state
load_state() {
    if [ -f "$STATE_FILE" ]; then
        source "$STATE_FILE"
    fi
}

# Check prerequisites
check_prerequisites() {
    print_header "Checking Prerequisites"

    local missing=0

    # Check gh CLI
    if command_exists gh; then
        if gh auth status >/dev/null 2>&1; then
            print_success "GitHub CLI (gh) installed and authenticated"
        else
            print_error "GitHub CLI not authenticated. Run: gh auth login"
            missing=1
        fi
    else
        print_error "GitHub CLI (gh) not installed. Install from: https://cli.github.com"
        missing=1
    fi

    # Check railway CLI (optional)
    if command_exists railway; then
        if railway whoami >/dev/null 2>&1; then
            print_success "Railway CLI installed and authenticated"
            RAILWAY_AVAILABLE=true
        else
            print_warning "Railway CLI not authenticated. Run: railway login"
            RAILWAY_AVAILABLE=false
        fi
    else
        print_warning "Railway CLI not installed (optional). Install from: https://docs.railway.app/develop/cli"
        RAILWAY_AVAILABLE=false
    fi

    # Check we're in a git repo
    if git rev-parse --git-dir >/dev/null 2>&1; then
        REPO_ROOT=$(git rev-parse --show-toplevel)
        REPO_NAME=$(gh repo view --json nameWithOwner -q .nameWithOwner 2>/dev/null || echo "")
        if [ -n "$REPO_NAME" ]; then
            print_success "In git repository: $REPO_NAME"
        else
            print_error "Could not determine repository name"
            missing=1
        fi
    else
        print_error "Not in a git repository"
        missing=1
    fi

    if [ $missing -eq 1 ]; then
        echo ""
        print_error "Please fix the above issues and run this script again."
        exit 1
    fi

    echo ""
    print_success "All prerequisites met!"
}

# Setup GitHub labels
setup_github_labels() {
    print_header "Setting Up GitHub Labels"

    print_step "Creating factory labels..."

    # Define labels
    declare -A LABELS=(
        ["ai-ready"]="0E8A16:Ready for AI agent to work on"
        ["needs-principal-engineer"]="D93F0B:Escalated - needs PE review"
        ["needs-human"]="B60205:Requires human intervention"
        ["bug"]="D73A4A:Something isn't working"
        ["enhancement"]="A2EEEF:New feature or request"
        ["priority-high"]="B60205:P0 - Critical priority"
        ["priority-medium"]="FBCA04:P1 - Medium priority"
        ["priority-low"]="0E8A16:P2 - Low priority"
        ["status:bot-working"]="1D76DB:Bot is actively working"
        ["status:awaiting-human"]="FBCA04:Waiting for human input"
        ["status:awaiting-bot"]="0E8A16:Waiting for bot to respond"
    )

    for label in "${!LABELS[@]}"; do
        IFS=':' read -r color description <<< "${LABELS[$label]}"
        if gh label create "$label" --color "$color" --description "$description" 2>/dev/null; then
            print_success "Created label: $label"
        else
            print_info "Label already exists: $label"
        fi
    done

    echo ""
    print_success "GitHub labels configured!"
}

# Collect secrets interactively
collect_secrets() {
    print_header "Collecting Configuration"

    load_state

    echo "I'll guide you through collecting the necessary secrets."
    echo "You can skip any step if you've already configured it."
    echo ""

    # GitHub Token
    if [ -z "$GITHUB_TOKEN" ]; then
        print_step "GitHub Personal Access Token"
        echo "  Create a PAT at: https://github.com/settings/tokens"
        echo "  Required scopes: repo, workflow"
        echo ""
        read -p "  Enter GitHub PAT (or press Enter to skip): " -s GITHUB_TOKEN
        echo ""
        if [ -n "$GITHUB_TOKEN" ]; then
            save_state "GITHUB_TOKEN" "$GITHUB_TOKEN"
            print_success "GitHub token saved"
        fi
    else
        print_info "GitHub token already configured"
    fi

    # Anthropic API Key
    if [ -z "$ANTHROPIC_API_KEY" ]; then
        echo ""
        print_step "Anthropic API Key"
        echo "  Get your API key from: https://console.anthropic.com/settings/keys"
        echo ""
        read -p "  Enter Anthropic API Key (or press Enter to skip): " -s ANTHROPIC_API_KEY
        echo ""
        if [ -n "$ANTHROPIC_API_KEY" ]; then
            save_state "ANTHROPIC_API_KEY" "$ANTHROPIC_API_KEY"
            print_success "Anthropic key saved"
        fi
    else
        print_info "Anthropic API key already configured"
    fi

    # Slack tokens
    echo ""
    print_step "Slack App Configuration"
    echo ""
    echo "  To create your Slack app easily, use the app manifest:"
    echo ""
    echo "  1. Go to: ${CYAN}https://api.slack.com/apps${NC}"
    echo "  2. Click 'Create New App' → 'From an app manifest'"
    echo "  3. Select your workspace"
    echo "  4. Copy the manifest from: ${CYAN}services/slack-bot/slack-app-manifest.yaml${NC}"
    echo "  5. Create the app and install to workspace"
    echo ""
    read -p "  Press Enter when you've created the Slack app..."

    if [ -z "$SLACK_BOT_TOKEN" ]; then
        echo ""
        echo "  Find Bot Token at: OAuth & Permissions → Bot User OAuth Token"
        read -p "  Enter Slack Bot Token (xoxb-...): " SLACK_BOT_TOKEN
        if [ -n "$SLACK_BOT_TOKEN" ]; then
            save_state "SLACK_BOT_TOKEN" "$SLACK_BOT_TOKEN"
            print_success "Slack bot token saved"
        fi
    else
        print_info "Slack bot token already configured"
    fi

    if [ -z "$SLACK_APP_TOKEN" ]; then
        echo ""
        echo "  Find App Token at: Basic Information → App-Level Tokens"
        echo "  (Create one with 'connections:write' scope if needed)"
        read -p "  Enter Slack App Token (xapp-...): " SLACK_APP_TOKEN
        if [ -n "$SLACK_APP_TOKEN" ]; then
            save_state "SLACK_APP_TOKEN" "$SLACK_APP_TOKEN"
            print_success "Slack app token saved"
        fi
    else
        print_info "Slack app token already configured"
    fi

    if [ -z "$SLACK_SIGNING_SECRET" ]; then
        echo ""
        echo "  Find Signing Secret at: Basic Information → App Credentials"
        read -p "  Enter Slack Signing Secret: " SLACK_SIGNING_SECRET
        if [ -n "$SLACK_SIGNING_SECRET" ]; then
            save_state "SLACK_SIGNING_SECRET" "$SLACK_SIGNING_SECRET"
            print_success "Slack signing secret saved"
        fi
    else
        print_info "Slack signing secret already configured"
    fi

    if [ -z "$SLACK_WEBHOOK_SECRET" ]; then
        echo ""
        print_step "Slack Webhook Secret (for secure webhook callbacks)"
        echo "  Generate a random secret for webhook authentication."
        echo "  You can use: openssl rand -hex 32"
        echo ""
        read -p "  Enter Slack Webhook Secret (or press Enter to auto-generate): " SLACK_WEBHOOK_SECRET
        if [ -z "$SLACK_WEBHOOK_SECRET" ]; then
            SLACK_WEBHOOK_SECRET=$(openssl rand -hex 32)
            echo "  Auto-generated: ${SLACK_WEBHOOK_SECRET:0:16}..."
        fi
        save_state "SLACK_WEBHOOK_SECRET" "$SLACK_WEBHOOK_SECRET"
        print_success "Slack webhook secret saved"
    else
        print_info "Slack webhook secret already configured"
    fi

    echo ""
    print_success "Configuration collected!"
}

# Setup GitHub secrets
setup_github_secrets() {
    print_header "Setting Up GitHub Secrets"

    load_state

    print_step "Adding secrets to GitHub repository..."

    if [ -n "$GITHUB_TOKEN" ]; then
        echo "$GITHUB_TOKEN" | gh secret set PAT_WITH_WORKFLOW_ACCESS
        print_success "Set PAT_WITH_WORKFLOW_ACCESS"
    fi

    if [ -n "$ANTHROPIC_API_KEY" ]; then
        echo "$ANTHROPIC_API_KEY" | gh secret set ANTHROPIC_API_KEY
        print_success "Set ANTHROPIC_API_KEY"
    fi

    if [ -n "$SLACK_BOT_TOKEN" ]; then
        echo "$SLACK_BOT_TOKEN" | gh secret set SLACK_BOT_TOKEN
        print_success "Set SLACK_BOT_TOKEN"
    fi

    if [ -n "$SLACK_APP_TOKEN" ]; then
        echo "$SLACK_APP_TOKEN" | gh secret set SLACK_APP_TOKEN
        print_success "Set SLACK_APP_TOKEN"
    fi

    if [ -n "$SLACK_SIGNING_SECRET" ]; then
        echo "$SLACK_SIGNING_SECRET" | gh secret set SLACK_SIGNING_SECRET
        print_success "Set SLACK_SIGNING_SECRET"
    fi

    if [ -n "$SLACK_WEBHOOK_URL" ]; then
        echo "$SLACK_WEBHOOK_URL" | gh secret set SLACK_WEBHOOK_URL
        print_success "Set SLACK_WEBHOOK_URL"
    fi

    if [ -n "$SLACK_WEBHOOK_SECRET" ]; then
        echo "$SLACK_WEBHOOK_SECRET" | gh secret set SLACK_WEBHOOK_SECRET
        print_success "Set SLACK_WEBHOOK_SECRET"
    fi

    echo ""
    print_success "GitHub secrets configured!"
}

# Deploy to Railway
deploy_railway() {
    print_header "Deploying to Railway"

    if [ "$RAILWAY_AVAILABLE" != "true" ]; then
        print_warning "Railway CLI not available. Manual deployment required."
        echo ""
        echo "  To deploy manually:"
        echo "  1. Go to https://railway.app/new"
        echo "  2. Select 'Deploy from GitHub repo'"
        echo "  3. Choose this repository"
        echo "  4. Set root directory to: services/slack-bot"
        echo "  5. Add environment variables (see .factory-setup-state)"
        echo ""
        return
    fi

    load_state

    print_step "Creating Railway project..."

    cd "$REPO_ROOT/services/slack-bot"

    # Initialize Railway project if needed
    if [ ! -f "railway.json" ] || ! railway status >/dev/null 2>&1; then
        railway init --name "claude-factory-slack-bot" 2>/dev/null || true
    fi

    print_step "Setting Railway environment variables..."

    [ -n "$GITHUB_TOKEN" ] && railway variables set GITHUB_TOKEN="$GITHUB_TOKEN"
    [ -n "$ANTHROPIC_API_KEY" ] && railway variables set ANTHROPIC_API_KEY="$ANTHROPIC_API_KEY"
    [ -n "$SLACK_BOT_TOKEN" ] && railway variables set SLACK_BOT_TOKEN="$SLACK_BOT_TOKEN"
    [ -n "$SLACK_APP_TOKEN" ] && railway variables set SLACK_APP_TOKEN="$SLACK_APP_TOKEN"
    [ -n "$SLACK_SIGNING_SECRET" ] && railway variables set SLACK_SIGNING_SECRET="$SLACK_SIGNING_SECRET"
    [ -n "$SLACK_WEBHOOK_SECRET" ] && railway variables set SLACK_WEBHOOK_SECRET="$SLACK_WEBHOOK_SECRET"
    railway variables set GITHUB_REPOSITORY="$REPO_NAME"
    railway variables set GITHUB_OWNER="${REPO_NAME%%/*}"
    railway variables set PORT="3000"

    print_step "Deploying to Railway..."
    railway up --detach

    # Get the deployment URL
    sleep 5
    RAILWAY_URL=$(railway domain 2>/dev/null || echo "")

    if [ -n "$RAILWAY_URL" ]; then
        save_state "SLACK_WEBHOOK_URL" "https://$RAILWAY_URL"
        railway variables set SLACK_WEBHOOK_URL="https://$RAILWAY_URL"
        print_success "Deployed to: https://$RAILWAY_URL"
    else
        print_warning "Could not determine Railway URL. Check Railway dashboard."
    fi

    cd "$REPO_ROOT"

    echo ""
    print_success "Railway deployment initiated!"
}

# Validate setup
validate_setup() {
    print_header "Validating Setup"

    load_state
    local issues=0

    # Check GitHub token
    print_step "Checking GitHub API access..."
    if [ -n "$GITHUB_TOKEN" ]; then
        if curl -s -H "Authorization: token $GITHUB_TOKEN" https://api.github.com/user >/dev/null; then
            print_success "GitHub API accessible"
        else
            print_error "GitHub token invalid or expired"
            issues=$((issues + 1))
        fi
    else
        print_warning "GitHub token not configured"
        issues=$((issues + 1))
    fi

    # Check Anthropic key
    print_step "Checking Anthropic API access..."
    if [ -n "$ANTHROPIC_API_KEY" ]; then
        # Simple validation - check key format
        if [[ "$ANTHROPIC_API_KEY" == sk-ant-* ]]; then
            print_success "Anthropic API key format valid"
        else
            print_warning "Anthropic API key format unexpected"
        fi
    else
        print_warning "Anthropic API key not configured"
        issues=$((issues + 1))
    fi

    # Check Slack tokens
    print_step "Checking Slack configuration..."
    if [ -n "$SLACK_BOT_TOKEN" ] && [ -n "$SLACK_APP_TOKEN" ]; then
        print_success "Slack tokens configured"
    else
        print_warning "Slack tokens not fully configured"
        issues=$((issues + 1))
    fi

    # Check Railway deployment
    print_step "Checking deployment..."
    if [ -n "$SLACK_WEBHOOK_URL" ]; then
        if curl -s "$SLACK_WEBHOOK_URL/health" >/dev/null 2>&1; then
            print_success "Deployment accessible at $SLACK_WEBHOOK_URL"
        else
            print_warning "Deployment not responding (may still be starting)"
        fi
    else
        print_warning "Deployment URL not configured"
    fi

    echo ""
    if [ $issues -eq 0 ]; then
        print_success "All validations passed!"
    else
        print_warning "$issues issue(s) found. Review above and fix as needed."
    fi
}

# Print summary
print_summary() {
    print_header "Setup Complete!"

    load_state

    echo "Your Claude Software Factory is configured!"
    echo ""
    echo -e "${BOLD}Repository:${NC} $REPO_NAME"
    [ -n "$SLACK_WEBHOOK_URL" ] && echo -e "${BOLD}Bot URL:${NC} $SLACK_WEBHOOK_URL"
    echo ""
    echo -e "${BOLD}Next Steps:${NC}"
    echo "  1. Test the bot: Message it in Slack with 'factory status'"
    echo "  2. Create a test issue with 'ai-ready' label"
    echo "  3. Watch the factory work!"
    echo ""
    echo -e "${BOLD}Useful Commands:${NC}"
    echo "  factory status     - Check factory health"
    echo "  failures           - See CI failure patterns"
    echo "  agent performance  - Check agent autonomy rate"
    echo "  dispatch code X    - Create issue for code agent"
    echo ""
    echo -e "${BOLD}Documentation:${NC}"
    echo "  - CLAUDE.md        - Factory configuration"
    echo "  - README.md        - General setup guide"
    echo ""

    # Cleanup state file (contains secrets)
    if [ -f "$STATE_FILE" ]; then
        print_warning "Removing state file (contained secrets): $STATE_FILE"
        rm -f "$STATE_FILE"
    fi
}

# Main menu
main_menu() {
    print_header "Claude Software Factory Setup"

    echo "This wizard will help you set up your software factory."
    echo ""
    echo "What would you like to do?"
    echo ""
    echo "  1) Full setup (recommended for new repos)"
    echo "  2) Setup GitHub labels only"
    echo "  3) Setup GitHub secrets only"
    echo "  4) Deploy to Railway only"
    echo "  5) Validate existing setup"
    echo "  6) Exit"
    echo ""
    read -p "Enter choice [1-6]: " choice

    case $choice in
        1)
            check_prerequisites
            setup_github_labels
            collect_secrets
            setup_github_secrets
            deploy_railway
            validate_setup
            print_summary
            ;;
        2)
            check_prerequisites
            setup_github_labels
            ;;
        3)
            check_prerequisites
            collect_secrets
            setup_github_secrets
            ;;
        4)
            check_prerequisites
            collect_secrets
            deploy_railway
            ;;
        5)
            check_prerequisites
            validate_setup
            ;;
        6)
            echo "Goodbye!"
            exit 0
            ;;
        *)
            print_error "Invalid choice"
            exit 1
            ;;
    esac
}

# Run
main_menu
