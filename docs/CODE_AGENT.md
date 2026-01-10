# Code Agent

## Overview

The Code Agent is the primary workhorse of the autonomous software factory. It diagnoses issues, implements fixes, writes tests, and creates pull requests. Unlike traditional CI/CD pipelines that only run predefined scripts, the Code Agent can analyze problems, make implementation decisions, and iterate on solutions.

## Problem Statement

Software development traditionally requires human developers to:
1. Read and understand bug reports
2. Diagnose root causes by exploring code
3. Implement fixes with appropriate tests
4. Create PRs with proper documentation
5. Iterate on CI failures

The Code Agent automates this entire workflow, handling everything from issue triage to merged PR.

## Design Principles

### 1. Autonomous Decision-Making
The Code Agent makes technical decisions autonomously. It doesn't ask "Should I use approach A or B?" - it decides based on engineering judgment and documents the reasoning.

**Decide Autonomously:**
- Implementation approach (pick the cleanest solution)
- Test strategy (unit, integration, E2E)
- Timeout/retry values (use reasonable defaults: 30s timeout, 3 retries)
- Code style (follow existing patterns)

**Escalate Only For:**
- Security decisions (credentials, auth changes)
- Breaking changes (public API changes)
- Business logic (product decisions)

### 2. Log Analysis First
Before implementing any fix, the agent MUST analyze logs. Guessing at fixes without reading actual errors leads to repeated failures.

**Log Analysis Protocol:**
1. Check issue comments for "❌ CI Failed" - contains actual failure logs
2. Get workflow logs via `gh run view <RUN_ID> --log-failed`
3. Download E2E artifacts if applicable
4. Document findings before implementing

### 3. Progressive Visibility
The agent maintains a progress comment that it updates as work progresses. This provides real-time visibility without human intervention.

### 4. Graceful Escalation
After 3 CI failures on the same issue, the agent escalates to the Principal Engineer via `@pe` comment rather than continuing to retry.

## Responsibilities

### A. Issue Analysis
1. Read full issue including all comments
2. Check for existing PRs or previous attempts
3. Identify root cause through code exploration
4. Document findings in progress comment

### B. Implementation
1. Create feature branch: `fix/{issue_number}-{description}` or `feat/{issue_number}-{description}`
2. Implement minimal fix
3. Add regression tests
4. Run formatters and linters before commit

### C. Quality Gates
Before creating a PR:
```bash
# Frontend
cd frontend
npm run format && npm run lint -- --fix
npm run typecheck && npm test

# Backend
cd backend
uv run ruff format . && uv run ruff check . --fix
uv run mypy . && uv run pytest
```

### D. PR Creation & Monitoring
1. Create PR with "Relates to #N" (NOT "Fixes #N")
2. Monitor CI status
3. Auto-merge on success
4. Retry up to 3 times on failure

## Triggers

### Primary: @code Mention
```yaml
issue_comment:
  types: [created]
# Trigger when comment contains @code or @claude
```

### Secondary: Scheduled Polling
```yaml
schedule:
  - cron: '*/5 * * * *'  # Check for reactions on awaiting issues
```

### Manual
```yaml
workflow_dispatch:
  inputs:
    issue_number:
      type: number
      description: 'Issue number to fix'
```

## Workflow Structure

```yaml
jobs:
  check-reactions:
    # Poll for reactions on status:awaiting-bot issues
    if: github.event_name == 'schedule'

  fix:
    # Main fix job - handles analysis, implementation, PR
    if: |
      contains(github.event.comment.body, '@code') ||
      contains(github.event.issue.labels.*.name, 'status:awaiting-bot')
    steps:
      - checkout with PAT_WITH_WORKFLOW_ACCESS
      - setup node and python
      - get issue context
      - update status labels
      - create progress comment
      - run claude-code-action
      - monitor CI and report results
      - trigger retry on failure (up to 3x)
```

## Progress Comment Format

The agent maintains a living progress comment:

```markdown
## 🤖 Code Agent Progress

- [x] 📖 Reading issue and understanding requirements
- [x] 🔍 Analyzing codebase and finding affected files
- [ ] 🛠️ Implementing fix: [specific description]
- [ ] ✅ Running tests and quality checks
- [ ] 📝 Creating PR
- [ ] 🚀 CI Status: *pending*

**Status:** [current status]
**Workflow:** [View logs](...)

---
## 📋 Activity Log

| Time | Event |
|------|-------|
| 2026-01-10 12:00 UTC | 🚀 Code Agent started |
| 2026-01-10 12:02 UTC | 📖 Read issue: [description] |
| 2026-01-10 12:05 UTC | 🔍 Found root cause: [description] |

---
## 🔍 Summary

### Root Cause
[Explanation]

### Fix Applied
[Description]

### Files Changed
- `path/to/file.ts` - [change description]
```

## Status Label Management

| Label | Meaning | Action |
|-------|---------|--------|
| `status:bot-working` | Agent actively working | Wait for agent |
| `status:awaiting-human` | Agent needs input | Human should respond |
| `status:awaiting-bot` | Human responded | Agent will continue |

## Inter-Agent Communication

### Request DevOps Diagnostics
When production data is needed:
```
@devops please check backend logs for authentication errors
@devops check database connection status
```

### Escalate to Principal Engineer
After 3 CI failures or when stuck:
```
@pe please investigate - Code Agent stuck on [specific issue]
```

## CI Failure Handling

### Automatic Retry Flow
1. CI fails → Agent posts detailed "❌ CI Failed" comment with logs
2. Retry triggered automatically
3. After 3 failures → Escalate to PE with `@pe`
4. Add `needs-principal-engineer` label

### Failure Comment Format
```markdown
## ❌ CI Failed

**Time:** [timestamp]
**PR:** #[number]

### Failed Jobs
- **[job name]**: [failed steps]

<details>
<summary>📋 Failure Logs</summary>
[logs]
</details>

[View full logs](...)
```

## Permissions

The Code Agent has these permissions via `PAT_WITH_WORKFLOW_ACCESS`:
- ✅ Push to any branch
- ✅ Create/merge PRs
- ✅ Modify workflow files
- ✅ Trigger workflows
- ✅ Create/update issues

## Security Considerations

1. **Never commit secrets** - Check for `.env`, credentials, API keys
2. **Validate inputs** - Don't blindly trust issue content
3. **Minimal changes** - Fix the reported issue, don't refactor unrelated code
4. **Branch protection** - Never push directly to main

## Success Criteria

1. **Fix Rate**: >80% of issues resolved without human intervention
2. **CI Pass Rate**: >70% of PRs pass CI on first attempt
3. **Time to Fix**: Average <30 minutes from issue to merged PR
4. **Quality**: No regressions introduced by agent fixes
