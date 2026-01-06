#!/bin/bash
# SessionStart Hook: GitHub CLI Authentication Check
# Ensures gh CLI has workflow scope for pushing workflow files

set -euo pipefail

echo "🔐 Checking GitHub CLI authentication..."

# Check if gh is available
if ! command -v gh &> /dev/null; then
  echo "⚠️  gh CLI not found - skipping auth check"
  exit 0
fi

# Check current auth status and scopes
AUTH_STATUS=$(gh auth status 2>&1 || true)

if echo "$AUTH_STATUS" | grep -q "workflow"; then
  echo "✅ GitHub CLI authenticated with workflow scope"
  exit 0
fi

if echo "$AUTH_STATUS" | grep -q "Logged in"; then
  echo "⚠️  GitHub CLI authenticated but MISSING workflow scope"
  echo ""
  echo "To enable workflow file pushes, run:"
  echo "  gh auth login --scopes workflow"
  echo ""
  echo "Then follow the browser auth flow."
  exit 0
fi

echo "⚠️  GitHub CLI not authenticated"
echo ""
echo "To authenticate with workflow scope, run:"
echo "  gh auth login --scopes workflow"
echo ""
exit 0
