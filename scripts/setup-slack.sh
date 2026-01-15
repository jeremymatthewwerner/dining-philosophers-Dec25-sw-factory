#!/bin/bash
#
# Slack Bot Setup Wizard for Claude Software Factory
#
# This script guides you through setting up the Slack bot that provides
# a conversational interface to your software factory.
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

# Print functions
print_header() {
    echo ""
    echo -e "${BLUE}═══════════════════════════════════════════════════════════════${NC}"
    echo -e "${BOLD}  $1${NC}"
    echo -e "${BLUE}═══════════════════════════════════════════════════════════════${NC}"
    echo ""
}

print_step() {
    echo -e "${CYAN}→${NC} $1"
}

print_success() {
    echo -e "${GREEN}✓${NC} $1"
}

print_warning() {
    echo -e "${YELLOW}⚠${NC} $1"
}

print_error() {
    echo -e "${RED}✗${NC} $1"
}

print_info() {
    echo -e "${BLUE}ℹ${NC} $1"
}

# Check for required tools
check_requirements() {
    print_header "Checking Requirements"

    local missing=0

    # Check for gh CLI
    if command -v gh &> /dev/null; then
        print_success "GitHub CLI (gh) is installed"
        if gh auth status &> /dev/null; then
            print_success "GitHub CLI is authenticated"
        else
            print_warning "GitHub CLI is not authenticated. Run 'gh auth login' first."
            missing=1
        fi
    else
        print_error "GitHub CLI (gh) is not installed"
        print_info "Install from: https://cli.github.com/"
        missing=1
    fi

    # Check for Node.js
    if command -v node &> /dev/null; then
        local node_version=$(node --version | cut -d'v' -f2 | cut -d'.' -f1)
        if [ "$node_version" -ge 18 ]; then
            print_success "Node.js $(node --version) is installed"
        else
            print_warning "Node.js 18+ recommended, you have $(node --version)"
        fi
    else
        print_error "Node.js is not installed"
        missing=1
    fi

    if [ $missing -eq 1 ]; then
        echo ""
        print_error "Please install missing requirements and try again."
        exit 1
    fi
}

# Get repository info
get_repo_info() {
    if [ -z "$GITHUB_REPOSITORY" ]; then
        # Try to get from git remote
        local remote_url=$(git config --get remote.origin.url 2>/dev/null || echo "")
        if [ -n "$remote_url" ]; then
            # Extract owner/repo from URL
            GITHUB_REPOSITORY=$(echo "$remote_url" | sed -E 's/.*github.com[:/]([^/]+\/[^/.]+)(\.git)?$/\1/')
        fi
    fi
}

# Create Slack App instructions
show_slack_app_instructions() {
    print_header "Step 1: Create a Slack App"

    echo "We'll guide you through creating a Slack app with the right permissions."
    echo ""
    echo -e "${BOLD}Go to: https://api.slack.com/apps${NC}"
    echo ""
    echo "1. Click 'Create New App'"
    echo "2. Choose 'From scratch'"
    echo "3. Enter app name: 'Claude Factory' (or your preferred name)"
    echo "4. Select your workspace"
    echo "5. Click 'Create App'"
    echo ""
    read -p "Press Enter when you've created the app..."
}

# Configure OAuth scopes
configure_oauth_scopes() {
    print_header "Step 2: Configure Bot Permissions"

    echo "In your Slack app settings, go to:"
    echo -e "${BOLD}OAuth & Permissions → Bot Token Scopes${NC}"
    echo ""
    echo "Add these scopes:"
    echo ""
    echo "  • app_mentions:read     - Receive @mentions"
    echo "  • channels:history      - Read channel messages"
    echo "  • channels:read         - View channel info"
    echo "  • chat:write            - Send messages"
    echo "  • groups:history        - Read private channel messages"
    echo "  • groups:read           - View private channel info"
    echo "  • im:history            - Read direct messages"
    echo "  • im:read               - View direct message info"
    echo "  • im:write              - Send direct messages"
    echo "  • reactions:read        - View reactions"
    echo "  • users:read            - View user info"
    echo ""
    read -p "Press Enter when you've added all scopes..."
}

# Enable Socket Mode
configure_socket_mode() {
    print_header "Step 3: Enable Socket Mode"

    echo "In your Slack app settings, go to:"
    echo -e "${BOLD}Socket Mode${NC}"
    echo ""
    echo "1. Toggle 'Enable Socket Mode' ON"
    echo "2. Create an App-Level Token with scope: connections:write"
    echo "3. Name it: 'socket-token'"
    echo "4. Copy the token (starts with xapp-)"
    echo ""

    read -p "Enter your App-Level Token (xapp-...): " SLACK_APP_TOKEN

    if [[ ! "$SLACK_APP_TOKEN" =~ ^xapp- ]]; then
        print_warning "Token doesn't start with 'xapp-', make sure you copied the App-Level token"
    fi
}

# Subscribe to events
configure_events() {
    print_header "Step 4: Subscribe to Events"

    echo "In your Slack app settings, go to:"
    echo -e "${BOLD}Event Subscriptions${NC}"
    echo ""
    echo "1. Toggle 'Enable Events' ON"
    echo "2. Under 'Subscribe to bot events', add:"
    echo ""
    echo "   • app_mention        - When someone @mentions the bot"
    echo "   • message.channels   - Messages in public channels"
    echo "   • message.groups     - Messages in private channels"
    echo "   • message.im         - Direct messages"
    echo "   • reaction_added     - When reactions are added"
    echo ""
    echo "3. Click 'Save Changes'"
    echo ""
    read -p "Press Enter when you've configured events..."
}

# Install app to workspace
install_to_workspace() {
    print_header "Step 5: Install App to Workspace"

    echo "In your Slack app settings, go to:"
    echo -e "${BOLD}Install App${NC}"
    echo ""
    echo "1. Click 'Install to Workspace'"
    echo "2. Review and allow the permissions"
    echo "3. Copy the 'Bot User OAuth Token' (starts with xoxb-)"
    echo ""

    read -p "Enter your Bot User OAuth Token (xoxb-...): " SLACK_BOT_TOKEN

    if [[ ! "$SLACK_BOT_TOKEN" =~ ^xoxb- ]]; then
        print_warning "Token doesn't start with 'xoxb-', make sure you copied the Bot User OAuth Token"
    fi
}

# Get signing secret
get_signing_secret() {
    print_header "Step 6: Get Signing Secret"

    echo "In your Slack app settings, go to:"
    echo -e "${BOLD}Basic Information → App Credentials${NC}"
    echo ""
    echo "Copy the 'Signing Secret'"
    echo ""

    read -p "Enter your Signing Secret: " SLACK_SIGNING_SECRET
}

# Configure slash command (optional)
configure_slash_command() {
    print_header "Step 7: Configure Slash Command (Optional)"

    echo "Want to add a /claude slash command?"
    echo ""
    read -p "Add slash command? (y/N): " add_slash

    if [[ "$add_slash" =~ ^[Yy] ]]; then
        echo ""
        echo "In your Slack app settings, go to:"
        echo -e "${BOLD}Slash Commands → Create New Command${NC}"
        echo ""
        echo "Configure:"
        echo "  Command: /claude"
        echo "  Request URL: (we'll set this after deployment)"
        echo "  Short Description: Interact with Claude Software Factory"
        echo "  Usage Hint: [dispatch agent task] or [question]"
        echo ""
        read -p "Press Enter when you've created the command..."
        SETUP_SLASH_COMMAND="true"
    fi
}

# Set up GitHub secrets
setup_github_secrets() {
    print_header "Setting Up GitHub Secrets"

    get_repo_info

    if [ -z "$GITHUB_REPOSITORY" ]; then
        print_warning "Could not detect repository. Setting secrets manually..."
        echo ""
        echo "Add these secrets to your repository:"
        echo "  Settings → Secrets and variables → Actions → New repository secret"
        echo ""
        echo "  SLACK_BOT_TOKEN: $SLACK_BOT_TOKEN"
        echo "  SLACK_APP_TOKEN: $SLACK_APP_TOKEN"
        echo "  SLACK_SIGNING_SECRET: $SLACK_SIGNING_SECRET"
        return
    fi

    print_step "Adding Slack secrets to $GITHUB_REPOSITORY..."

    # Add secrets using gh CLI
    echo "$SLACK_BOT_TOKEN" | gh secret set SLACK_BOT_TOKEN --repo "$GITHUB_REPOSITORY"
    print_success "Added SLACK_BOT_TOKEN"

    echo "$SLACK_APP_TOKEN" | gh secret set SLACK_APP_TOKEN --repo "$GITHUB_REPOSITORY"
    print_success "Added SLACK_APP_TOKEN"

    echo "$SLACK_SIGNING_SECRET" | gh secret set SLACK_SIGNING_SECRET --repo "$GITHUB_REPOSITORY"
    print_success "Added SLACK_SIGNING_SECRET"

    # Generate a webhook secret
    WEBHOOK_SECRET=$(openssl rand -hex 32)
    echo "$WEBHOOK_SECRET" | gh secret set SLACK_WEBHOOK_SECRET --repo "$GITHUB_REPOSITORY"
    print_success "Added SLACK_WEBHOOK_SECRET (auto-generated)"
}

# Create environment file template
create_env_template() {
    print_header "Creating Environment Template"

    local env_file="services/slack-bot/.env.example"

    cat > "$env_file" << EOF
# Slack Configuration
SLACK_BOT_TOKEN=xoxb-your-bot-token
SLACK_APP_TOKEN=xapp-your-app-token
SLACK_SIGNING_SECRET=your-signing-secret

# Anthropic Configuration
ANTHROPIC_API_KEY=sk-ant-your-key

# GitHub Configuration
GITHUB_TOKEN=ghp_your-token
GITHUB_REPOSITORY=owner/repo

# Repository Configuration
REPO_BASE_PATH=/path/to/repos
DEFAULT_REPO=my-project

# Server Configuration
WEBHOOK_PORT=3001
WEBHOOK_SECRET=your-webhook-secret

# Logging
LOG_LEVEL=info
EOF

    print_success "Created $env_file"
}

# Show deployment instructions
show_deployment_instructions() {
    print_header "Deployment Instructions"

    echo "Your Slack bot is almost ready! Here's how to deploy it:"
    echo ""
    echo -e "${BOLD}Option 1: Railway (Recommended)${NC}"
    echo ""
    echo "1. In your Railway project, add a new service from this repo"
    echo "2. Set the root directory to: services/slack-bot"
    echo "3. Add environment variables from GitHub secrets"
    echo "4. Deploy!"
    echo ""
    echo -e "${BOLD}Option 2: Local Development${NC}"
    echo ""
    echo "  cd services/slack-bot"
    echo "  cp .env.example .env"
    echo "  # Edit .env with your values"
    echo "  npm install"
    echo "  npm run dev"
    echo ""
    echo -e "${BOLD}Option 3: Docker${NC}"
    echo ""
    echo "  cd services/slack-bot"
    echo "  docker build -t slack-bot ."
    echo "  docker run -p 3001:3001 --env-file .env slack-bot"
    echo ""

    if [ "$SETUP_SLASH_COMMAND" = "true" ]; then
        echo -e "${YELLOW}Note:${NC} After deploying, update your slash command URL to:"
        echo "  https://your-domain/webhooks/slack/commands"
        echo ""
    fi
}

# Show next steps
show_next_steps() {
    print_header "Setup Complete! 🎉"

    echo "Your Slack bot is configured. Next steps:"
    echo ""
    echo "  1. Deploy the bot (see instructions above)"
    echo "  2. Invite the bot to a channel: /invite @Claude Factory"
    echo "  3. Start chatting! @Claude Factory hello"
    echo ""
    echo "The bot can:"
    echo "  • Have conversations about your codebase"
    echo "  • Dispatch tasks to agents: 'dispatch code fix the login bug'"
    echo "  • Show status updates when agents complete work"
    echo "  • Help when workflows break"
    echo ""
    echo -e "${BOLD}Documentation:${NC} See services/slack-bot/README.md"
    echo ""
}

# Main script
main() {
    print_header "Claude Software Factory - Slack Bot Setup"

    echo "This wizard will help you set up a Slack bot that provides"
    echo "a conversational interface to your software factory."
    echo ""
    echo "You'll create a Slack app with the right permissions,"
    echo "and we'll configure the secrets in your GitHub repo."
    echo ""
    read -p "Ready to begin? (Y/n): " ready

    if [[ "$ready" =~ ^[Nn] ]]; then
        echo "Setup cancelled."
        exit 0
    fi

    check_requirements
    show_slack_app_instructions
    configure_oauth_scopes
    configure_socket_mode
    configure_events
    install_to_workspace
    get_signing_secret
    configure_slash_command
    setup_github_secrets
    create_env_template
    show_deployment_instructions
    show_next_steps
}

# Run main
main "$@"
