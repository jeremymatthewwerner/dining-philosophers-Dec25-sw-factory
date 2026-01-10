# DevOps Agent

## Overview

The DevOps Agent manages infrastructure health, incident response, and production diagnostics. It serves as the bridge between the autonomous software factory and the Railway deployment platform, providing real-time monitoring and automated recovery capabilities.

## Problem Statement

Production systems require continuous monitoring and rapid incident response:
1. Health checks must run frequently to detect issues early
2. Incidents need immediate triage and resolution
3. Other agents need production data for debugging
4. PRs with passing CI should be auto-merged and deployed
5. Stuck PRs with conflicts need automatic resolution

The DevOps Agent automates these operational concerns, ensuring the factory runs smoothly.

## Design Principles

### 1. Continuous Monitoring
Health checks run every 5 minutes to detect issues before users notice. The agent checks:
- Backend health endpoint
- Frontend accessibility
- Authentication flow
- Database connectivity

### 2. Incident Severity Classification
Incidents are classified by severity to prioritize response:
- **SEV1**: Production down → Fix or escalate immediately
- **SEV2**: Major feature broken → Fix within 15 minutes
- **SEV3**: Minor issue → Create issue for tracking

### 3. Self-Healing
The agent attempts automatic recovery before escalating:
- Redeploy services to recover from crashes
- Clear stale sessions
- Restart hung processes

### 4. Inter-Agent Support
Other agents can request production diagnostics via `@devops` mentions:
```
@devops please check backend logs for authentication errors
@devops check database connection status
```

## Responsibilities

### A. Health Monitoring (Every 5 Minutes)
1. Check backend `/health` endpoint
2. Check frontend loads correctly
3. Test authentication flow with canary user
4. Check for stuck PRs needing merge
5. Auto-merge PRs with passing CI

### B. Incident Response
1. Detect health check failures
2. Collect Railway logs for context
3. Create production incident issue
4. Trigger Code Agent for fixes
5. Track incident until resolved

### C. Diagnostic Requests
When `@devops` is mentioned:
1. Parse the request from comment
2. Query Railway API for logs
3. Check relevant health endpoints
4. Post diagnostic results back to issue

### D. Auto-Rebase (On Push to Main)
1. Check all open PRs for merge conflicts
2. Attempt automatic rebase
3. If rebase fails, close PR and trigger Code Agent to recreate

### E. Weekly Monitoring Audit (Sunday 6am UTC)
1. Review health endpoint completeness
2. Check logging structure
3. Audit alerting configuration
4. Verify dashboard completeness
5. Create audit report issue

### F. Feedback Processing (Every 5 Minutes)
1. Fetch pending user feedback from backend
2. Create GitHub issues from feedback
3. Trigger Triage Agent for classification
4. Mark feedback as processed

## Triggers

### Scheduled
```yaml
schedule:
  # Health checks every 5 minutes
  - cron: '*/5 * * * *'
  # Weekly monitoring audit (Sunday 6am UTC)
  - cron: '0 6 * * 0'
```

### Event-Based
```yaml
push:
  branches: [main]  # Auto-rebase conflicting PRs

issue_comment:
  types: [created]  # @devops mentions
```

### Manual
```yaml
workflow_dispatch:
  inputs:
    action:
      type: choice
      options:
        - incident-response
        - view-logs
        - restart-service
        - manage-variables
        - provision-infrastructure
        - diagnose
```

## Workflow Structure

```yaml
jobs:
  # Respond to @devops mentions
  diagnostic-request:
    if: contains(github.event.comment.body, '@devops')
    steps:
      - install Railway CLI
      - query logs and service status
      - post results to issue

  # Scheduled health checks
  smoke-test:
    if: github.event_name == 'schedule'
    steps:
      - check backend health
      - check frontend
      - test auth flow
      - check for stuck PRs
      - summarize results

  # Create incident on failure
  create-incident:
    needs: smoke-test
    if: needs.smoke-test.outputs.healthy == 'false'
    steps:
      - collect Railway logs
      - create or update incident issue
      - trigger Code Agent

  # Auto-rebase on push to main
  auto-rebase:
    if: github.event_name == 'push'
    steps:
      - find PRs with conflicts
      - attempt rebase
      - close and recreate if failed
```

## Railway CLI Commands

### Viewing Logs
```bash
railway logs --service backend -n 50     # Last 50 lines from backend
railway logs --service frontend -n 50    # Last 50 lines from frontend
railway logs -n 100                      # All services
railway logs --build                     # Build logs
```

### Service Management
```bash
railway status                           # Project status
railway redeploy                         # Redeploy latest
railway down                             # Remove deployment (CAREFUL!)
```

### Environment Variables
```bash
railway variables                        # List all
railway variables --set "KEY=value"      # Set variable
railway variables --service backend      # Service-specific
```

### Database Access
```bash
railway connect postgres                 # Open psql shell
```

### Provisioning
```bash
railway add --database postgres          # Add PostgreSQL
railway add --database redis             # Add Redis
railway add --service myservice          # Add empty service
```

## DevOps API Endpoints

The backend provides protected endpoints for database operations:

| Endpoint | Method | Purpose |
|----------|--------|---------|
| `/api/devops/health` | GET | Verify authentication |
| `/api/devops/stats` | GET | Database statistics |
| `/api/devops/cleanup/stale-sessions` | DELETE | Remove old sessions |
| `/api/devops/cleanup/orphans` | DELETE | Remove orphaned records |

All require `X-DevOps-Secret` header.

## Incident Issue Format

```markdown
## 🚨 Production Incident

**Severity:** SEV1/SEV2/SEV3
**Failed Checks:** backend, auth
**Detected:** [timestamp]

### Railway Logs (last 30 lines)

<details>
<summary>Backend Logs</summary>
[logs]
</details>

### Actions
- [View workflow logs](...)
- Check Railway dashboard
- Use `railway logs --service backend` locally
```

## Diagnostic Results Format

```markdown
## 🔧 DevOps Diagnostic Results

<details>
<summary>📋 Diagnostic Output</summary>

=== Railway CLI Info ===
[version info]

=== Service Status ===
[status output]

=== Recent Backend Logs ===
[log entries]

</details>

---
**Need more info?** You can request:
- `@devops check user <username>` - User-related logs
- `@devops check database` - DB connection status
- `@devops check logs <service>` - Service logs
```

## Required Secrets

| Secret | Purpose |
|--------|---------|
| `RAILWAY_TOKEN_SW_FACTORY` | Railway Project Token (CLI commands) |
| `RAILWAY_WORKSPACE_TOKEN` | Railway Workspace Token (GraphQL API) |
| `RAILWAY_WORKSPACE_ID` | Railway workspace UUID |
| `PRODUCTION_BACKEND_URL` | Backend URL for health checks |
| `PRODUCTION_FRONTEND_URL` | Frontend URL for health checks |
| `DEVOPS_API_SECRET` | Auth for DevOps API endpoints |
| `FEEDBACK_PROCESSOR_SECRET` | Auth for feedback processing |

## Security Considerations

1. **Never expose secrets** - Don't log tokens or credentials
2. **Rate limiting** - Don't spam Railway API
3. **Audit trail** - All actions logged in GitHub issues
4. **Minimal access** - Only query what's needed for diagnosis
5. **Service restart limits** - Max 2 restarts before escalation

## Success Criteria

1. **Detection Time**: Health issues detected within 5 minutes
2. **Incident Response**: SEV1 incidents addressed within 10 minutes
3. **Auto-Recovery Rate**: >50% of incidents resolved without human intervention
4. **PR Staleness**: No PRs stuck with passing CI for >1 hour
5. **Diagnostic Response**: @devops requests answered within 5 minutes
