# Release Engineering Agent

## Overview

The Release Engineering Agent is responsible for daily codebase maintenance - keeping dependencies updated, security vulnerabilities patched, CI/CD optimized, and documentation current. It runs as a scheduled job ensuring the codebase stays healthy without manual intervention.

## Problem Statement

Codebases require continuous maintenance:
1. Security vulnerabilities are discovered regularly in dependencies
2. Dependencies become outdated and may lose support
3. CI/CD pipelines slow down without optimization
4. Documentation drifts from actual implementation
5. Code health degrades (lint warnings, TODOs, deprecated APIs)

The Release Engineering Agent automates these maintenance tasks daily.

## Design Principles

### 1. Security First
Security vulnerabilities are always the highest priority. Critical and high-severity issues are fixed immediately; medium/low create tracking issues.

### 2. Conservative Updates
- **Patch versions** (x.y.Z): Update automatically
- **Minor versions** (x.Y.z): Update if changelog looks safe
- **Major versions** (X.y.z): Create issue for human review - NEVER auto-update

### 3. Non-Breaking Changes
The agent makes changes that should not break functionality. If there's risk of breakage, it creates an issue instead of making the change.

### 4. CI Performance Monitoring
Target CI duration is <10 minutes. If exceeded, the agent looks for optimization opportunities.

## Responsibilities

### 1. Security (CRITICAL - Always First)

```bash
# Frontend audit
cd frontend && npm audit --json > /tmp/frontend-audit.json

# Backend audit
cd backend && uv run pip-audit --format json > /tmp/backend-audit.json
```

**Response Matrix:**
| Severity | Action |
|----------|--------|
| Critical/High | Fix immediately |
| Medium/Low | Create tracking issue |

### 2. Dependency Management

**Patch Versions (x.y.Z):**
- Update automatically
- Run tests to verify
- Include in maintenance PR

**Minor Versions (x.Y.z):**
- Review changelog for breaking changes
- Update if safe
- Document reason in commit message

**Major Versions (X.y.z):**
- NEVER update automatically
- Create issue for human review
- Include migration guide if available

**Additional Tasks:**
- Keep lock files in sync
- Remove unused dependencies
- Update deprecated packages

### 3. CI/CD Optimization

**Monitor Performance:**
```bash
# Get recent CI run durations
gh run list --limit 20 --json databaseId,conclusion,updatedAt,createdAt \
  --jq '[.[] | {duration: (((.updatedAt | fromdateiso8601) - (.createdAt | fromdateiso8601)) / 60 | floor)}]'
```

**If avg > 10 minutes:**
- Identify slow steps
- Add/improve caching
- Optimize parallelization
- Split large jobs

**Hunt Flaky Tests:**
- Review recent CI failures
- Identify intermittent failures
- Fix or skip with issue reference

### 4. Code Health

**Lint Checks:**
```bash
# Frontend
cd frontend && npm run lint

# Backend
cd backend && uv run ruff check .
```

**Additional Checks:**
- Deprecated API usage
- Stale TODO/FIXME comments (>30 days old)
- Dead code
- Hardcoded secrets/credentials

### 5. Documentation

**Keep Current:**
- README reflects actual setup steps
- CHANGELOG includes recent changes
- Environment variable docs match code
- API documentation is accurate

### 6. Create Maintenance PR

Group related changes logically:
- Security fixes in separate commits
- Dependency updates grouped by type
- Clear commit messages
- Reference any issues fixed

## Triggers

### Scheduled (Primary)
```yaml
schedule:
  - cron: '0 3 * * *'  # Daily at 3am UTC
```

### Manual
```yaml
workflow_dispatch:
  # No inputs - runs full maintenance
```

## Workflow Structure

```yaml
jobs:
  maintain:
    timeout-minutes: 45
    steps:
      - checkout
      - setup node and python
      - install dependencies
      - run frontend security audit
      - run backend security audit
      - check outdated dependencies
      - analyze CI performance
      - run claude-code-action with maintenance prompt
```

## Pre-Workflow Analysis

Before the agent runs, the workflow collects:
1. Frontend vulnerability count
2. Backend vulnerability count
3. Average CI duration
4. List of outdated packages

This context helps the agent prioritize work.

## Output

The agent creates a maintenance PR containing:
1. Security vulnerability fixes
2. Dependency updates (patch/minor only)
3. Lint fixes
4. Documentation updates
5. CI optimizations

Each change has a clear commit message explaining the rationale.

## Issues Created

For items requiring human review:
- Major version updates
- Complex migrations
- Breaking changes
- Infrastructure decisions

## Rules

1. **NEVER upgrade major versions without human approval**
2. **ALWAYS run tests before creating PR**
3. **ALWAYS check CI passes before marking complete**
4. **Create issues for anything requiring human decision**
5. **Escalate if stuck or unsure**

## Permissions

The Release Engineering Agent has standard permissions:
- ✅ Read/write code
- ✅ Create PRs
- ✅ Create issues
- ✅ Run tests

## Security Considerations

1. **Don't expose audit details publicly** - Some vulnerabilities are sensitive
2. **Verify fixes don't introduce new issues** - Run full test suite
3. **Check dependency sources** - Avoid typosquatting packages
4. **Review changelog** - Ensure updates don't include malicious changes

## Success Criteria

1. **Vulnerability Response**: Critical/high vulns fixed within 24 hours
2. **Dependency Freshness**: No patch-level updates older than 7 days
3. **CI Performance**: Average duration stays under 10 minutes
4. **Documentation Accuracy**: README/CHANGELOG always current
5. **Session Completion**: >95% of maintenance runs complete successfully
