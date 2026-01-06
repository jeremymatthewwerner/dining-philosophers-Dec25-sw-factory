#!/bin/bash
#
# Fix script for dining-philosophers-Dec25-sw-factory
# Run this inside your existing repo directory
#

set -e

echo "🔧 Fixing workflows in dining-philosophers-Dec25-sw-factory..."

# Verify we're in the right place
if [ ! -f "CLAUDE.md" ]; then
  echo "❌ Error: Run this from inside the dining-philosophers-Dec25-sw-factory directory"
  exit 1
fi

# ============================================================================
# Fixed Workflows - removed allowed_tools, added proper permissions
# ============================================================================

cat > .github/workflows/triage.yml << 'EOF'
name: Triage Agent
on:
  issues:
    types: [opened, reopened]
  workflow_dispatch:
    inputs:
      issue_number:
        description: 'Issue number to triage'
        required: true
        type: number

permissions:
  contents: read
  issues: write
  id-token: write

jobs:
  triage:
    runs-on: ubuntu-latest
    timeout-minutes: 15
    steps:
      - uses: actions/checkout@v4
      
      - name: Get issue number
        id: issue
        run: |
          if [ "${{ github.event_name }}" == "workflow_dispatch" ]; then
            echo "number=${{ github.event.inputs.issue_number }}" >> $GITHUB_OUTPUT
          else
            echo "number=${{ github.event.issue.number }}" >> $GITHUB_OUTPUT
          fi
      
      - uses: anthropics/claude-code-action@v1
        with:
          prompt: |
            Read CLAUDE.md and .claude/agents/triage-product.md first.
            
            Triage issue #${{ steps.issue.outputs.number }}:
            1. Get issue details: gh issue view ${{ steps.issue.outputs.number }}
            2. Check for duplicates
            3. Classify (bug/feature/question)
            4. Add appropriate labels
            5. If ready for AI fixing, add 'ai-ready' label
            6. Comment with your assessment
          anthropic_api_key: ${{ secrets.ANTHROPIC_API_KEY }}
        env:
          GITHUB_TOKEN: ${{ secrets.GITHUB_TOKEN }}
EOF

cat > .github/workflows/bug-fix.yml << 'EOF'
name: Bug Fix Agent
on:
  issues:
    types: [labeled]
  workflow_dispatch:
    inputs:
      issue_number:
        description: 'Issue number to fix'
        required: true
        type: number

permissions:
  contents: write
  issues: write
  pull-requests: write
  id-token: write

jobs:
  fix:
    if: github.event_name == 'workflow_dispatch' || (github.event.label.name == 'ai-ready' && contains(github.event.issue.labels.*.name, 'bug'))
    runs-on: ubuntu-latest
    timeout-minutes: 60
    steps:
      - uses: actions/checkout@v4
        with:
          fetch-depth: 0
          
      - uses: actions/setup-node@v4
        with:
          node-version: '20'
          cache: 'npm'
        continue-on-error: true
        
      - name: Install dependencies
        run: npm ci || true
        
      - name: Get issue number
        id: issue
        run: |
          if [ "${{ github.event_name }}" == "workflow_dispatch" ]; then
            echo "number=${{ github.event.inputs.issue_number }}" >> $GITHUB_OUTPUT
          else
            echo "number=${{ github.event.issue.number }}" >> $GITHUB_OUTPUT
          fi
          
      - uses: anthropics/claude-code-action@v1
        with:
          prompt: |
            Read CLAUDE.md and .claude/agents/bug-fixer.md first.
            
            Fix issue #${{ steps.issue.outputs.number }}:
            1. Read the issue: gh issue view ${{ steps.issue.outputs.number }}
            2. Diagnose the root cause
            3. Create a fix branch
            4. Implement the fix
            5. Run quality gates: npm run lint && npm run typecheck && npm run test
            6. Create a PR
            
            If stuck for 30min or CI fails 3x, escalate to @jeremy.
          anthropic_api_key: ${{ secrets.ANTHROPIC_API_KEY }}
        env:
          GITHUB_TOKEN: ${{ secrets.GITHUB_TOKEN }}
EOF

cat > .github/workflows/qa.yml << 'EOF'
name: QA Agent
on:
  schedule:
    - cron: '0 2 * * *'
  workflow_dispatch:
    inputs:
      focus:
        description: 'Focus area'
        type: choice
        options:
          - coverage-sprint
          - flaky-hunt
          - integration-gaps

permissions:
  contents: write
  pull-requests: write
  id-token: write

jobs:
  qa:
    runs-on: ubuntu-latest
    timeout-minutes: 45
    steps:
      - uses: actions/checkout@v4
        with:
          fetch-depth: 0
          
      - uses: actions/setup-node@v4
        with:
          node-version: '20'
          cache: 'npm'
        continue-on-error: true
        
      - name: Install dependencies
        run: npm ci || true
        
      - uses: anthropics/claude-code-action@v1
        with:
          prompt: |
            Read CLAUDE.md and .claude/agents/qa-improver.md first.
            
            Focus: ${{ github.event.inputs.focus || 'coverage-sprint' }}
            
            Improve test quality:
            1. Generate coverage report
            2. Identify gaps
            3. Write meaningful tests
            4. Run tests 3x to check for flakiness
            5. Create PR with improvements
          anthropic_api_key: ${{ secrets.ANTHROPIC_API_KEY }}
        env:
          GITHUB_TOKEN: ${{ secrets.GITHUB_TOKEN }}
EOF

cat > .github/workflows/release-eng.yml << 'EOF'
name: Release Engineering Agent
on:
  schedule:
    - cron: '0 3 * * 0'
  workflow_dispatch:

permissions:
  contents: write
  pull-requests: write
  issues: write
  id-token: write

jobs:
  maintain:
    runs-on: ubuntu-latest
    timeout-minutes: 30
    steps:
      - uses: actions/checkout@v4
        with:
          fetch-depth: 0
          
      - uses: actions/setup-node@v4
        with:
          node-version: '20'
          cache: 'npm'
        continue-on-error: true
        
      - name: Install dependencies
        run: npm ci || true
        
      - name: Security audit
        id: audit
        run: |
          npm audit --json > /tmp/audit.json 2>/dev/null || true
          VULNS=$(cat /tmp/audit.json | jq '.metadata.vulnerabilities.total // 0' 2>/dev/null || echo "0")
          echo "vulnerabilities=$VULNS" >> $GITHUB_OUTPUT
          
      - uses: anthropics/claude-code-action@v1
        with:
          prompt: |
            Read CLAUDE.md and .claude/agents/release-engineer.md first.
            
            Vulnerabilities found: ${{ steps.audit.outputs.vulnerabilities }}
            
            Weekly maintenance:
            1. Fix critical/high security issues
            2. Update patch dependencies
            3. Analyze CI performance
            4. Create maintenance PR
            
            Do NOT upgrade major versions without human approval.
          anthropic_api_key: ${{ secrets.ANTHROPIC_API_KEY }}
        env:
          GITHUB_TOKEN: ${{ secrets.GITHUB_TOKEN }}
EOF

cat > .github/workflows/devops.yml << 'EOF'
name: DevOps Agent
on:
  schedule:
    - cron: '0 */6 * * *'
  workflow_dispatch:
    inputs:
      severity:
        description: 'Incident severity'
        type: choice
        options:
          - SEV1
          - SEV2
          - SEV3
      description:
        description: 'Incident description'
        type: string

permissions:
  contents: write
  issues: write
  id-token: write

jobs:
  health-check:
    if: github.event_name == 'schedule'
    runs-on: ubuntu-latest
    timeout-minutes: 10
    steps:
      - name: Check health
        id: health
        run: |
          HTTP=$(curl -s -o /dev/null -w "%{http_code}" --max-time 10 https://diningphilosophers.ai/api/health 2>/dev/null || echo "000")
          echo "status=$HTTP" >> $GITHUB_OUTPUT
          if [ "$HTTP" != "200" ]; then
            echo "unhealthy=true" >> $GITHUB_OUTPUT
          fi
          
      - name: Trigger incident if unhealthy
        if: steps.health.outputs.unhealthy == 'true'
        run: |
          gh workflow run devops.yml -f severity=SEV2 -f description="Health check failed: HTTP ${{ steps.health.outputs.status }}"
        env:
          GITHUB_TOKEN: ${{ secrets.GITHUB_TOKEN }}

  incident:
    if: github.event_name == 'workflow_dispatch'
    runs-on: ubuntu-latest
    timeout-minutes: 30
    steps:
      - uses: actions/checkout@v4
      
      - uses: anthropics/claude-code-action@v1
        with:
          prompt: |
            Read CLAUDE.md and .claude/agents/devops-sre.md first.
            
            INCIDENT: ${{ github.event.inputs.severity }} - ${{ github.event.inputs.description }}
            
            Response:
            1. Diagnose the issue
            2. Check logs and recent deployments
            3. Attempt mitigation (max 2 restarts)
            4. Create incident issue
            5. Escalate to @jeremy if SEV1 or can't resolve
          anthropic_api_key: ${{ secrets.ANTHROPIC_API_KEY }}
        env:
          GITHUB_TOKEN: ${{ secrets.GITHUB_TOKEN }}
EOF

cat > .github/workflows/marketing.yml << 'EOF'
name: Marketing Agent
on:
  release:
    types: [published]
  workflow_dispatch:

permissions:
  contents: write
  pull-requests: write
  id-token: write

jobs:
  content:
    runs-on: ubuntu-latest
    timeout-minutes: 30
    steps:
      - uses: actions/checkout@v4
        with:
          fetch-depth: 0
          
      - uses: anthropics/claude-code-action@v1
        with:
          prompt: |
            Read CLAUDE.md and .claude/agents/marketing-docs.md first.
            
            Update content for the latest release:
            1. Get release info: gh release view
            2. Update CHANGELOG.md with user-friendly entries
            3. Check if any new philosophers were added
            4. Update README if needed
            5. Create PR with content updates
          anthropic_api_key: ${{ secrets.ANTHROPIC_API_KEY }}
        env:
          GITHUB_TOKEN: ${{ secrets.GITHUB_TOKEN }}
EOF

# ============================================================================
# Commit and push
# ============================================================================

git add .github/workflows/
git commit -m "fix(ci): correct workflow permissions and inputs

- Remove invalid 'allowed_tools' input
- Add 'id-token: write' permission for OIDC
- Add proper permissions for each workflow
- Add workflow_dispatch to all workflows for manual testing
- Fix issue number handling for manual triggers"

git push

echo ""
echo "✅ Workflows fixed and pushed!"
echo ""
echo "Test it now:"
echo "  gh workflow run triage.yml -f issue_number=1"
echo ""
echo "Or create a new issue:"
echo "  gh issue create --title 'Test issue' --body 'Testing triage' --label 'bug'"
