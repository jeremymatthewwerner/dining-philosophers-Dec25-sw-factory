# Triage Agent

## Overview

The Triage Agent is the first responder for all new GitHub issues. It classifies issues, detects duplicates, assigns priority labels, and routes issues to the appropriate specialized agent. Acting as an intelligent intake system, it ensures issues reach the right handler without human intervention.

## Problem Statement

Issue management traditionally requires human attention:
1. Reading and understanding new issues
2. Classifying as bug, feature, or question
3. Checking for duplicate issues
4. Assigning priority
5. Routing to the right team member

The Triage Agent automates this intake process, ensuring consistent classification and immediate routing.

## Design Principles

### 1. Fast Classification
The Triage Agent should process issues quickly (<2 minutes) to ensure rapid response to users.

### 2. Intelligent Routing
Issues are routed to specialized agents via @mentions based on content analysis:
- `@code` for bugs and features
- `@devops` for infrastructure issues
- `@factory-manager` for workflow/factory issues

### 3. Duplicate Prevention
Before routing, the agent searches for similar issues to avoid duplicate work.

### 4. Single @mention Rule
Each triage comment includes exactly ONE @mention to avoid triggering multiple agents simultaneously.

## Responsibilities

### A. Classification

**Bug vs Enhancement vs Question:**
- Bugs: Something isn't working as expected
- Enhancements: New feature requests
- Questions: Requests for information

### B. Duplicate Detection

```bash
# Search for similar issues
gh issue list --search "<relevant terms>" --state all
```

If duplicate found:
- Link to original issue
- Suggest closing as duplicate
- Don't trigger other agents

### C. Priority Assignment

| Priority | Criteria | Label |
|----------|----------|-------|
| P0 | Blocks most functionality (critical, system down) | `priority-high` |
| P1 | Blocks some functionality OR new feature | `priority-medium` |
| P2 | Optimizations, cleanup, minor improvements | `priority-low` |

### D. Intelligent Agent Routing

**Route to @factory-manager if issue mentions:**
- workflow, agent, triage, factory, CI/CD pipeline
- Bot stuck, agent not triggering, escalation problems
- How the autonomous factory works

**Route to @devops if issue mentions:**
- railway, deploy, deployment, logs, database, production
- Service health, health check, uptime, monitoring, incident
- Environment variables, secrets, infrastructure

**Route to @code for everything else:**
- Bug fixes (application bugs, errors, crashes)
- Feature requests (new functionality)
- Code changes (refactoring, optimization)
- Test issues (test failures, coverage)

### E. Triage Comment

Post a structured assessment:

```markdown
## 🤖 Triage Assessment

**Classification:** Bug/Enhancement
**Priority:** High/Medium/Low (P1/P2/P3)
**Status:** Ready for [Code Agent/DevOps/Factory Manager]

### Analysis
[Analysis of the issue]

### Next Steps
@[appropriate-agent] please investigate and fix this issue.

---
*Auto-triaged by Triage Agent*
```

## Triggers

### Primary: New Issue
```yaml
issues:
  types: [opened]  # Only NEW issues, not reopened
```

### Re-Triage Request
```yaml
issue_comment:
  types: [created]
# Trigger on @triage mentions for re-classification
```

### Manual
```yaml
workflow_dispatch:
  inputs:
    issue_number:
      type: number
      description: 'Issue number to triage'
```

## Workflow Structure

```yaml
jobs:
  triage:
    if: |
      !contains(github.event.issue.labels.*.name, 'factory-meta') &&
      (github.event_name == 'workflow_dispatch' ||
       github.event_name == 'issues' ||
       contains(github.event.comment.body, '@triage'))
    steps:
      - checkout
      - get issue number
      - check if already triaged
      - pre-install Claude Code
      - run claude-code-action with triage prompt
```

## Skip Conditions

The agent skips issues that:
1. Already have triage-related labels (`bug`, `enhancement`, `priority-*`, etc.)
2. Have the `factory-meta` label (handled by Factory Manager)

## Available Labels

The Triage Agent can add:
- `bug` - Something isn't working
- `enhancement` - Feature request
- `priority-high` - P0/P1 issues
- `priority-medium` - P1/P2 issues
- `priority-low` - P2/P3 issues
- `needs-human` - Requires human attention

## Important Rules

1. **Use EXACTLY ONE @mention** in "Next Steps"
2. **Do NOT add 'ai-ready' label** - @mentions trigger agents now
3. **When in doubt, route to @code** - It's the most general agent
4. **Multiple @mentions trigger MULTIPLE agents** - Avoid this!

## Routing Decision Tree

```
Is it about workflow/factory/agents?
├── Yes → @factory-manager
├── No ↓
    Is it about infrastructure/deploy/production?
    ├── Yes → @devops
    ├── No ↓
        → @code (default)
```

## Re-Triage Flow

When a user comments `@triage`:
1. Agent re-reads the issue
2. Re-evaluates classification and priority
3. Updates labels if needed
4. Posts new assessment
5. Routes to appropriate agent

This allows users to request reclassification if the initial triage was incorrect.

## Permissions

The Triage Agent has limited permissions:
- ✅ Read issues
- ✅ Add labels to issues
- ✅ Comment on issues
- ❌ Cannot modify code
- ❌ Cannot create PRs

## Security Considerations

1. **Don't trust issue content blindly** - Users can submit malicious content
2. **Don't include sensitive info in comments** - Triage comments are public
3. **Validate label names** - Only use predefined labels

## Success Criteria

1. **Classification Accuracy**: >95% of issues correctly classified
2. **Routing Accuracy**: >90% of issues routed to correct agent on first try
3. **Duplicate Detection**: >80% of duplicates caught before routing
4. **Response Time**: <2 minutes from issue creation to triage completion
5. **Re-Triage Rate**: <10% of issues need re-triage
