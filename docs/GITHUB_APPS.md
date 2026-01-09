# GitHub Apps for the Autonomous Software Factory

This document describes the GitHub Apps architecture that gives each agent a distinct identity.

## Overview

Instead of all agents appearing as `claude[bot]` or `github-actions[bot]`, each agent role has its own GitHub App:

| Agent | App Name | Purpose |
|-------|----------|---------|
| Code Agent | `DP Code Agent` | Fixes bugs, implements features |
| Factory Manager | `DP Factory Manager` | Monitors factory, handles workflow changes |
| DevOps | `DP DevOps Agent` | Infrastructure, incident response |
| Triage | `DP Triage Agent` | Classifies issues, adds labels |
| QA | `DP QA Agent` | Test quality improvement |

## Benefits

1. **Distinct identities** - Each agent's comments show their specific identity
2. **Assignable** - Issues can be assigned to agent bot accounts
3. **Real @mentions** - `@dp-code-agent[bot]` is a real GitHub user
4. **Workflow triggers** - App comments CAN trigger workflows (unlike GITHUB_TOKEN)
5. **Scoped permissions** - Each app only has permissions it needs
6. **Clear audit trail** - Easy to see which agent did what

## Setup

### Prerequisites

- GitHub CLI (`gh`) installed and authenticated
- Repository admin access

### Creating the Apps

Run the setup script:

```bash
./scripts/setup-github-apps.sh
```

This will guide you through:
1. Creating each GitHub App
2. Setting permissions from manifests
3. Generating private keys
4. Storing secrets in the repository
5. Installing apps on the repository

### Manual Setup

If you prefer manual setup:

1. Go to **Settings → Developer settings → GitHub Apps → New GitHub App**

2. For each app, use the manifest in `.github/apps/<agent>.json`:
   - `code-agent.json`
   - `factory-manager.json`
   - `devops.json`
   - `triage.json`
   - `qa.json`

3. After creating each app:
   - Note the **App ID**
   - Generate a **Private Key** (.pem file)
   - Install the app on your repository

4. Store secrets in the repository:
   - `CODE_AGENT_APP_ID` / `CODE_AGENT_PRIVATE_KEY`
   - `FACTORY_MANAGER_APP_ID` / `FACTORY_MANAGER_PRIVATE_KEY`
   - `DEVOPS_APP_ID` / `DEVOPS_PRIVATE_KEY`
   - `TRIAGE_APP_ID` / `TRIAGE_PRIVATE_KEY`
   - `QA_APP_ID` / `QA_PRIVATE_KEY`

## Using Apps in Workflows

### Generating Installation Tokens

Use the `actions/create-github-app-token` action to get an installation token:

```yaml
steps:
  - name: Generate App Token
    id: app-token
    uses: actions/create-github-app-token@v1
    with:
      app-id: ${{ secrets.CODE_AGENT_APP_ID }}
      private-key: ${{ secrets.CODE_AGENT_PRIVATE_KEY }}

  - name: Use the token
    env:
      GH_TOKEN: ${{ steps.app-token.outputs.token }}
    run: |
      # This comment will appear from "DP Code Agent[bot]"
      gh issue comment 123 --body "Hello from Code Agent!"
```

### Example: Code Agent Workflow

```yaml
name: Code Agent

on:
  issue_comment:
    types: [created]

jobs:
  fix:
    if: contains(github.event.comment.body, '@dp-code-agent')
    runs-on: ubuntu-latest
    steps:
      - name: Generate Code Agent Token
        id: app-token
        uses: actions/create-github-app-token@v1
        with:
          app-id: ${{ secrets.CODE_AGENT_APP_ID }}
          private-key: ${{ secrets.CODE_AGENT_PRIVATE_KEY }}

      - uses: actions/checkout@v4
        with:
          token: ${{ steps.app-token.outputs.token }}

      # ... rest of workflow
      # All comments/commits will appear from "DP Code Agent[bot]"
```

## Assignment-Based Workflow (Future)

With GitHub Apps, we can potentially use **issue assignment** instead of labels/mentions:

```yaml
on:
  issues:
    types: [assigned]

jobs:
  process:
    # Check if assigned to our bot
    if: github.event.assignee.login == 'dp-code-agent[bot]'
    runs-on: ubuntu-latest
    steps:
      # ...
```

This would allow:
- Drag issues to agent columns in Projects
- Assign issues to agents like human developers
- Clear visual representation of who's working on what

## Secrets Reference

| Secret | Description |
|--------|-------------|
| `CODE_AGENT_APP_ID` | App ID for Code Agent |
| `CODE_AGENT_PRIVATE_KEY` | Private key for Code Agent |
| `FACTORY_MANAGER_APP_ID` | App ID for Factory Manager |
| `FACTORY_MANAGER_PRIVATE_KEY` | Private key for Factory Manager |
| `DEVOPS_APP_ID` | App ID for DevOps Agent |
| `DEVOPS_PRIVATE_KEY` | Private key for DevOps Agent |
| `TRIAGE_APP_ID` | App ID for Triage Agent |
| `TRIAGE_PRIVATE_KEY` | Private key for Triage Agent |
| `QA_APP_ID` | App ID for QA Agent |
| `QA_PRIVATE_KEY` | Private key for QA Agent |

## Migrating from PAT-based Authentication

The current factory uses `PAT_WITH_WORKFLOW_ACCESS` for all agents. To migrate:

1. Run the setup script to create apps
2. Update each workflow to use the appropriate app token
3. Test that each agent appears with its correct identity
4. Remove the old PAT once migration is verified

See the migration PR for specific workflow changes.

## Troubleshooting

### "Resource not accessible by integration"

The app doesn't have the required permission. Check:
- App permissions in GitHub Settings → Developer settings → GitHub Apps
- App installation on the repository

### "Bad credentials"

- Verify the App ID matches the installed app
- Regenerate the private key if it's been rotated

### Comments not triggering workflows

Ensure the app has the relevant event subscriptions:
- `issue_comment` for comment triggers
- `issues` for issue triggers
- `pull_request` for PR triggers
