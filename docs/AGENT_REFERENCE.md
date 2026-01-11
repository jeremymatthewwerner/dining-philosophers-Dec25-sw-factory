# Agent Reference

This document lists all AI agents available in the software factory.

## Agent Summary

| Agent | Trigger | Purpose | Workflow |
|-------|---------|---------|----------|
| **Triage** | Issue opened | Classify, dedupe, prioritize, label | `triage.yml` |
| **Code Agent** | `@code` mention | Fix bugs, implement features | `bug-fix.yml` |
| **Principal Engineer** | `@pe` mention | Holistic debugging when Code Agent stuck | `principal-engineer.yml` |
| **Product Manager** | `@pm` mention | Process roadmaps, create tracking sub-issues | `product-manager.yml` |
| **Factory Manager** | Every 30 min + `@factory-manager` | Monitor factory health, detect stuck issues | `factory-manager.yml` |
| **CI Monitor** | CI failure on main | Auto-create issues and trigger Code Agent | `ci-failure-monitor.yml` |
| **DevOps** | Every 5 min + `@devops` | Production health, auto-merge ready PRs | `devops.yml` |
| **QA** | 2am UTC daily | Improve test coverage | `qa.yml` |
| **Release Eng** | 3am UTC daily | Security audits, dependencies | `release-eng.yml` |
| **Marketing** | On release | Update changelog, docs | `marketing.yml` |

## @Mentions

Use these @mentions to trigger agents:

| Mention | Agent | Use Case |
|---------|-------|----------|
| `@code` | Code Agent | Fix bugs, implement features |
| `@pe` | Principal Engineer | Holistic debugging, factory fixes |
| `@pm` | Product Manager | Process roadmaps, create tracking sub-issues |
| `@devops` | DevOps Agent | Production logs, diagnostics, service restarts |
| `@factory-manager` | Factory Manager | Check factory health, diagnose stuck issues |

### Examples

```
@code please fix this bug
@pe this issue needs holistic investigation
@pm please create tracking issues for this roadmap
@devops check backend logs for errors
@factory-manager why is this issue stuck?
```

## Status Labels

| Label | Meaning | Who Acts |
|-------|---------|----------|
| `status:bot-working` | Agent is actively working | Wait for agent |
| `status:awaiting-human` | Agent needs your input | You respond |
| `status:awaiting-bot` | You commented, agent will respond | Wait for agent |

## Agent Documentation

- [Code Agent](CODE_AGENT.md)
- [Principal Engineer](PRINCIPAL_ENGINEER.md)
- [DevOps](DEVOPS.md)
- [Factory Manager](FACTORY_MANAGER.md)
- [QA Agent](QA_AGENT.md)
- [Release Engineering](RELEASE_ENG.md)
- [Triage](TRIAGE.md)
