#!/bin/bash
#
# Claude Software Factory - Setup Validation
#
# This script validates that your factory is correctly configured
# and all components are working together.
#
# Usage:
#   ./scripts/validate-factory.sh
#
set -e

# Colors
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
CYAN='\033[0;36m'
NC='\033[0m'
BOLD='\033[1m'

# Counters
PASSED=0
FAILED=0
WARNINGS=0

print_header() {
    echo ""
    echo -e "${BLUE}${BOLD}═══════════════════════════════════════════════════════════════${NC}"
    echo -e "${BLUE}${BOLD}  $1${NC}"
    echo -e "${BLUE}${BOLD}═══════════════════════════════════════════════════════════════${NC}"
    echo ""
}

check_pass() {
    echo -e "${GREEN}✓ PASS:${NC} $1"
    PASSED=$((PASSED + 1))
}

check_fail() {
    echo -e "${RED}✗ FAIL:${NC} $1"
    FAILED=$((FAILED + 1))
}

check_warn() {
    echo -e "${YELLOW}⚠ WARN:${NC} $1"
    WARNINGS=$((WARNINGS + 1))
}

check_info() {
    echo -e "${CYAN}ℹ INFO:${NC} $1"
}

# Validate GitHub CLI
validate_gh_cli() {
    print_header "GitHub CLI Validation"

    if command -v gh >/dev/null 2>&1; then
        check_pass "GitHub CLI installed"

        if gh auth status >/dev/null 2>&1; then
            check_pass "GitHub CLI authenticated"

            REPO=$(gh repo view --json nameWithOwner -q .nameWithOwner 2>/dev/null || echo "")
            if [ -n "$REPO" ]; then
                check_pass "Repository detected: $REPO"
            else
                check_fail "Could not detect repository"
            fi
        else
            check_fail "GitHub CLI not authenticated"
        fi
    else
        check_fail "GitHub CLI not installed"
    fi
}

# Validate GitHub labels
validate_labels() {
    print_header "GitHub Labels Validation"

    REQUIRED_LABELS=("ai-ready" "bug" "enhancement" "needs-principal-engineer" "needs-human")

    for label in "${REQUIRED_LABELS[@]}"; do
        if gh label list | grep -q "^$label"; then
            check_pass "Label exists: $label"
        else
            check_fail "Missing label: $label"
        fi
    done
}

# Validate GitHub secrets
validate_secrets() {
    print_header "GitHub Secrets Validation"

    # Note: We can only check if secrets exist, not their values
    SECRETS=$(gh secret list 2>/dev/null || echo "")

    REQUIRED_SECRETS=("ANTHROPIC_API_KEY")
    OPTIONAL_SECRETS=("FACTORY_GITHUB_TOKEN" "SLACK_BOT_TOKEN" "SLACK_WEBHOOK_URL")

    for secret in "${REQUIRED_SECRETS[@]}"; do
        if echo "$SECRETS" | grep -q "$secret"; then
            check_pass "Secret exists: $secret"
        else
            check_fail "Missing required secret: $secret"
        fi
    done

    for secret in "${OPTIONAL_SECRETS[@]}"; do
        if echo "$SECRETS" | grep -q "$secret"; then
            check_pass "Secret exists: $secret"
        else
            check_warn "Optional secret missing: $secret"
        fi
    done
}

# Validate workflows
validate_workflows() {
    print_header "GitHub Workflows Validation"

    WORKFLOW_DIR=".github/workflows"

    if [ -d "$WORKFLOW_DIR" ]; then
        check_pass "Workflows directory exists"

        # Check for key workflow files
        WORKFLOWS=("triage.yml" "bug-fix.yml" "ci.yml")

        for workflow in "${WORKFLOWS[@]}"; do
            if [ -f "$WORKFLOW_DIR/$workflow" ]; then
                check_pass "Workflow exists: $workflow"
            else
                check_warn "Workflow missing: $workflow"
            fi
        done

        # Check workflow runs
        RECENT_RUNS=$(gh run list --limit 5 2>/dev/null || echo "")
        if [ -n "$RECENT_RUNS" ]; then
            check_pass "Workflows have run recently"
            check_info "Recent runs:"
            echo "$RECENT_RUNS" | head -5 | while read -r line; do
                echo "    $line"
            done
        else
            check_warn "No recent workflow runs found"
        fi
    else
        check_fail "Workflows directory not found: $WORKFLOW_DIR"
    fi
}

# Validate Slack bot deployment
validate_slack_bot() {
    print_header "Slack Bot Validation"

    # Check if slack-bot directory exists
    if [ -d "services/slack-bot" ]; then
        check_pass "Slack bot code exists"
    else
        check_warn "Slack bot code not found"
        return
    fi

    # Try to get webhook URL from various sources
    WEBHOOK_URL=""

    # From environment
    [ -n "$SLACK_WEBHOOK_URL" ] && WEBHOOK_URL="$SLACK_WEBHOOK_URL"

    # From Railway (if available)
    if [ -z "$WEBHOOK_URL" ] && command -v railway >/dev/null 2>&1; then
        WEBHOOK_URL=$(cd services/slack-bot && railway domain 2>/dev/null || echo "")
        [ -n "$WEBHOOK_URL" ] && WEBHOOK_URL="https://$WEBHOOK_URL"
    fi

    if [ -n "$WEBHOOK_URL" ]; then
        check_info "Testing webhook URL: $WEBHOOK_URL"

        # Test health endpoint
        HTTP_CODE=$(curl -s -o /dev/null -w "%{http_code}" "$WEBHOOK_URL/health" 2>/dev/null || echo "000")

        if [ "$HTTP_CODE" = "200" ]; then
            check_pass "Slack bot is responding (HTTP 200)"

            # Get health response
            HEALTH=$(curl -s "$WEBHOOK_URL/health" 2>/dev/null || echo "{}")
            check_info "Health response: $HEALTH"
        else
            check_fail "Slack bot not responding (HTTP $HTTP_CODE)"
        fi
    else
        check_warn "Slack webhook URL not configured"
    fi
}

# Validate test project
validate_test_project() {
    print_header "Test Project Validation"

    if [ -d "test-project" ]; then
        check_pass "Test project exists"

        if [ -f "test-project/package.json" ]; then
            check_pass "Test project has package.json"
        else
            check_fail "Test project missing package.json"
        fi

        if [ -f "test-project/src/calculator.ts" ]; then
            check_pass "Test project has source code"
        else
            check_fail "Test project missing source code"
        fi

        if [ -d "test-project/tests" ]; then
            check_pass "Test project has tests directory"
        else
            check_fail "Test project missing tests"
        fi
    else
        check_warn "Test project not found"
    fi
}

# Validate CLAUDE.md
validate_claude_md() {
    print_header "CLAUDE.md Validation"

    if [ -f "CLAUDE.md" ]; then
        check_pass "CLAUDE.md exists"

        # Check for key sections
        if grep -q "## Tech Stack" "CLAUDE.md"; then
            check_pass "CLAUDE.md has Tech Stack section"
        else
            check_warn "CLAUDE.md missing Tech Stack section"
        fi

        if grep -q "## Autonomous Agents" "CLAUDE.md" || grep -q "## Autonomous Software Factory" "CLAUDE.md"; then
            check_pass "CLAUDE.md has Agents section"
        else
            check_warn "CLAUDE.md missing Agents section"
        fi
    else
        check_fail "CLAUDE.md not found"
    fi
}

# End-to-end test
run_e2e_test() {
    print_header "End-to-End Test (Optional)"

    echo "This test will create a real issue to verify the factory works."
    echo ""
    read -p "Run E2E test? This creates a real GitHub issue. [y/N] " -n 1 -r
    echo ""

    if [[ $REPLY =~ ^[Yy]$ ]]; then
        check_info "Creating test issue..."

        ISSUE_URL=$(gh issue create \
            --title "[Factory Test] Automated validation - $(date +%Y%m%d-%H%M%S)" \
            --body "This issue was created by the factory validation script to test that the system is working correctly.

This issue should:
1. Be triaged automatically (if triage workflow is enabled)
2. NOT trigger the code agent (no 'ai-ready' label)

You can safely close this issue after reviewing." \
            --label "enhancement" \
            2>/dev/null || echo "")

        if [ -n "$ISSUE_URL" ]; then
            check_pass "Test issue created: $ISSUE_URL"
            check_info "Watch for triage bot activity on this issue"
        else
            check_fail "Could not create test issue"
        fi
    else
        check_info "Skipping E2E test"
    fi
}

# Print summary
print_summary() {
    print_header "Validation Summary"

    echo -e "  ${GREEN}Passed:${NC}   $PASSED"
    echo -e "  ${RED}Failed:${NC}   $FAILED"
    echo -e "  ${YELLOW}Warnings:${NC} $WARNINGS"
    echo ""

    if [ $FAILED -eq 0 ]; then
        if [ $WARNINGS -eq 0 ]; then
            echo -e "${GREEN}${BOLD}✓ All validations passed! Your factory is ready.${NC}"
        else
            echo -e "${YELLOW}${BOLD}⚠ Validation passed with warnings. Review above for improvements.${NC}"
        fi
    else
        echo -e "${RED}${BOLD}✗ Validation failed. Please fix the issues above.${NC}"
        exit 1
    fi
}

# Main
main() {
    print_header "Claude Software Factory Validation"

    echo "This script will validate your factory setup."
    echo ""

    validate_gh_cli
    validate_labels
    validate_secrets
    validate_workflows
    validate_slack_bot
    validate_test_project
    validate_claude_md
    run_e2e_test
    print_summary
}

main
