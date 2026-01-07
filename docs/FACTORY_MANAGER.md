# Factory Manager Agent

## Overview

The Factory Manager is a meta-agent that monitors and maintains the autonomous software factory. Unlike other agents that work on product issues, the Factory Manager focuses on ensuring the factory itself operates correctly.

## Problem Statement

The autonomous factory has recurring failure modes:
1. **Stuck issues** - Issues that should trigger agents but don't
2. **Silent failures** - Workflows that fail without proper escalation
3. **Behavioral drift** - Agents not following critical requirements
4. **Trigger failures** - Race conditions preventing agent activation
5. **Data corruption** - Progress comments losing information

Currently, these issues require human intervention to detect and fix. The Factory Manager automates this monitoring and repair.

## Design Principles

### 1. Meta-Work Separation
Factory Manager work is "meta-work" - work about how agents work. This must be separated from product work to avoid:
- Code Agent picking up factory issues
- Circular triggers where Factory Manager triggers itself
- Confusion between product bugs and factory bugs

**Solution:** Use `factory-meta` label on all Factory Manager issues. Update all other agent triggers to exclude this label.

### 2. Proactive Monitoring
Factory Manager runs on schedule (every 30 minutes) to detect issues before humans notice:
- Check for stuck issues (labeled but no agent activity)
- Check for failed workflows
- Check for incomplete progress tracking
- Check for trigger failures

### 3. Self-Healing Priority
When issues are detected, prefer automated fixes over escalation:
1. Try to fix automatically (restart workflow, re-trigger agent)
2. If auto-fix fails, create a factory-meta issue with diagnosis
3. Only escalate to human if truly stuck

### 4. Audit Trail
All Factory Manager actions are logged in issues for visibility:
- Weekly summary issues showing factory health
- Incident issues when problems are detected and fixed
- Learning issues when patterns suggest systemic improvements

## Responsibilities

### A. Issue Health Monitoring

**Check every 30 minutes:**
1. **Stuck Issue Detection**
   - Find issues with `ai-ready` + (`bug` OR `enhancement`) that have no bot activity in 30 min
   - Find issues with `status:bot-working` that have no activity in 60 min
   - Find issues with `status:awaiting-bot` that have no bot response in 30 min

2. **Resolution:**
   - Post `@code please investigate` to re-trigger Code Agent
   - If already attempted, escalate to `@pe`
   - If PE also stuck, add `factory-meta` label and diagnose

### B. Workflow Health Monitoring

**Check every 30 minutes:**
1. **Failed Workflow Detection**
   - Find workflows that failed without creating issues
   - Find scheduled workflows that didn't run when expected
   - Find long-running workflows (>45 min) that may be hung

2. **Resolution:**
   - Create `factory-meta` issue documenting the failure
   - Attempt to re-run failed workflows
   - Diagnose root cause

### C. Progress Tracking Quality

**Check daily:**
1. **Activity Log Completeness**
   - Sample closed issues from past 24 hours
   - Check that progress comments have >=3 activity log entries
   - Flag issues where agents completed work without proper tracking

2. **Resolution:**
   - Track metrics over time (% of issues with good tracking)
   - If quality drops below threshold, investigate prompt effectiveness

### D. Trigger Verification

**Check weekly:**
1. **Trigger Testing**
   - Create test issue with `bug` label first, then `ai-ready`
   - Create test issue with `ai-ready` label first, then `bug`
   - Verify Code Agent triggers for both orderings

2. **Resolution:**
   - If trigger fails, create factory-meta issue with diagnosis
   - Propose workflow fix

### E. Agent Health Metrics

**Report weekly:**
1. **Metrics to Track**
   - Issues created vs closed
   - Average time from creation to agent pickup
   - Agent success rate (PRs merged vs issues escalated)
   - CI pass rate on agent PRs

2. **Resolution:**
   - Create weekly "Factory Health Report" issue
   - Track trends over time
   - Alert if metrics degrade

## Issue Labeling

### Factory Manager Labels

| Label | Purpose |
|-------|---------|
| `factory-meta` | All Factory Manager issues - NEVER picked up by other agents |
| `factory-health` | Health check results and metrics |
| `factory-incident` | Detected and (usually) auto-resolved incidents |
| `factory-learning` | Patterns that suggest systemic improvements |

### Label Exclusion Rules

All other agents MUST exclude `factory-meta` label:
```yaml
# In all agent workflows:
if: |
  !contains(github.event.issue.labels.*.name, 'factory-meta') &&
  ... (existing conditions)
```

## Triggers

### Scheduled (Primary)
```yaml
schedule:
  - cron: '*/30 * * * *'  # Every 30 minutes for health checks
  - cron: '0 6 * * 1'     # Weekly report on Monday 6am UTC
```

### Manual
```yaml
workflow_dispatch:
  inputs:
    action:
      type: choice
      options:
        - full-health-check
        - trigger-verification
        - weekly-report
        - diagnose-issue
    issue_number:
      type: number
      description: 'Issue to diagnose (for diagnose-issue action)'
```

### Comment-Triggered
```yaml
issue_comment:
  types: [created]
# Trigger on @factory-manager mentions
```

## Workflow Structure

```yaml
name: Factory Manager

on:
  schedule:
    - cron: '*/30 * * * *'
    - cron: '0 6 * * 1'
  workflow_dispatch:
    inputs:
      action:
        type: choice
        options: [full-health-check, trigger-verification, weekly-report, diagnose-issue]
      issue_number:
        type: number
  issue_comment:
    types: [created]

jobs:
  health-check:
    if: github.event_name == 'schedule' && github.event.schedule == '*/30 * * * *'
    # ... check for stuck issues, failed workflows, etc.

  weekly-report:
    if: github.event_name == 'schedule' && github.event.schedule == '0 6 * * 1'
    # ... generate weekly health report

  respond:
    if: |
      github.event_name == 'issue_comment' &&
      contains(github.event.comment.body, '@factory-manager')
    # ... respond to mentions

  manual:
    if: github.event_name == 'workflow_dispatch'
    # ... run specified action
```

## Detection Logic

### Stuck Issue Detection

```bash
# Issues that should have agent activity but don't
STUCK_ISSUES=$(gh issue list \
  --label "ai-ready" \
  --state open \
  --json number,labels,updatedAt \
  --jq '[.[] | select(
    (.labels | map(.name) | (contains(["bug"]) or contains(["enhancement"]))) and
    (.labels | map(.name) | contains(["factory-meta"]) | not) and
    (.labels | map(.name) | contains(["needs-human"]) | not) and
    ((.updatedAt | fromdateiso8601) < (now - 1800))
  )] | .[].number')
```

### Failed Workflow Detection

```bash
# Recent failed workflow runs
FAILED_RUNS=$(gh run list \
  --status failure \
  --limit 10 \
  --json databaseId,name,conclusion,headBranch,createdAt \
  --jq '[.[] | select(
    (.createdAt | fromdateiso8601) > (now - 3600)
  )]')
```

## Auto-Fix Actions

### Re-trigger Stuck Issue
```bash
# Post @code comment to re-trigger
gh issue comment "$ISSUE_NUMBER" \
  --body "@code [Factory Manager] This issue appears stuck. Please investigate."
```

### Re-run Failed Workflow
```bash
gh run rerun "$RUN_ID"
```

### Create Incident Issue
```bash
gh issue create \
  --title "[Factory Incident] $INCIDENT_TYPE" \
  --label "factory-meta,factory-incident" \
  --body "## Incident Details\n\n$DETAILS\n\n## Auto-Fix Attempted\n\n$FIX_RESULT"
```

## Weekly Health Report Format

```markdown
# Factory Health Report - Week of [DATE]

## Summary
- Issues processed: X
- Success rate: Y%
- Average pickup time: Z min
- Factory incidents: N

## Issue Flow
| Metric | This Week | Last Week | Trend |
|--------|-----------|-----------|-------|
| Created | X | Y | +/-% |
| Closed | X | Y | +/-% |
| Stuck | X | Y | +/-% |
| Escalated | X | Y | +/-% |

## Agent Performance
| Agent | Issues | Success | Avg Time |
|-------|--------|---------|----------|
| Code Agent | X | Y% | Z min |
| QA Agent | X | Y% | Z min |
| DevOps | X | Y% | Z min |

## Incidents
- [List of factory-incident issues this week]

## Recommendations
- [Any patterns suggesting systemic improvements]
```

## Implementation Phases

### Phase 1: Basic Monitoring (MVP)
- Stuck issue detection
- Re-trigger capability
- Basic incident logging

### Phase 2: Workflow Monitoring
- Failed workflow detection
- Re-run capability
- Workflow health metrics

### Phase 3: Quality Monitoring
- Progress tracking quality checks
- Trigger verification tests
- Weekly reports

### Phase 4: Self-Improvement
- Pattern detection
- Automatic prompt improvements
- Workflow fixes

## Security Considerations

1. **Rate Limiting**: Don't spam issues with re-triggers
   - Max 1 re-trigger per issue per hour
   - Max 10 total re-triggers per 30-min cycle

2. **Infinite Loop Prevention**:
   - Never trigger on `factory-meta` issues
   - Track re-trigger attempts, escalate after 3

3. **Audit Trail**: All actions logged in issues

## Success Criteria

1. **Detection Time**: Stuck issues detected within 30 minutes (vs hours with human monitoring)
2. **Auto-Resolution Rate**: >50% of stuck issues resolved without human intervention
3. **False Positive Rate**: <10% of detected issues are false positives
4. **Coverage**: 100% of factory failure modes have detection logic
