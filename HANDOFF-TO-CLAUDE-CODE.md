# Dining Philosophers - Autonomous Software Factory

## Session Summary (Dec 20, 2025)

This document captures the context from a Claude.ai conversation to continue work in Claude Code.

---

## What We Built

An **autonomous software factory** for the Dining Philosophers chat app - a real-time chat application where users converse with AI-simulated historical philosophers.

### Repository
- **Name**: `dining-philosophers-Dec25-sw-factory`
- **URL**: https://github.com/jeremymatthewwerner/dining-philosophers-Dec25-sw-factory
- **Visibility**: Public
- **Owner**: @jeremymatthewwerner (Jeremy)

### Tech Stack
- **Runtime**: Node.js 20
- **Framework**: Next.js 14 (App Router)
- **Database**: PostgreSQL (Prisma)
- **Real-time**: Socket.io
- **AI**: Anthropic Claude API
- **Hosting**: Railway
- **Domain**: https://diningphilosophers.ai

---

## 6 Autonomous Agents

All agents are configured with GitHub Actions workflows in `.github/workflows/`:

| Agent | File | Trigger | Purpose |
|-------|------|---------|---------|
| **Triage** | `triage.yml` | Issue opened, `workflow_dispatch` | Classifies issues, detects duplicates, adds labels, evaluates features |
| **Bug Fixer** | `bug-fix.yml` | `ai-ready` + `bug` labels, `workflow_dispatch` | Diagnoses and fixes bugs, creates PRs |
| **QA** | `qa.yml` | Nightly 2am UTC, `workflow_dispatch` | Improves test coverage, hunts flaky tests |
| **Release Eng** | `release-eng.yml` | Weekly Sunday 3am, `workflow_dispatch` | Security audits, dependency updates |
| **DevOps** | `devops.yml` | Every 6 hours, `workflow_dispatch` | Health checks, incident response |
| **Marketing** | `marketing.yml` | On release, `workflow_dispatch` | Updates changelog, docs, social drafts |

Agent definitions are in `.claude/agents/`:
- `triage-product.md`
- `bug-fixer.md`
- `qa-improver.md`
- `release-engineer.md`
- `devops-sre.md`
- `marketing-docs.md`

---

## Current State

### ✅ Completed
1. Repository created and pushed to GitHub
2. All 6 workflows configured with proper permissions
3. `ANTHROPIC_API_KEY` secret added
4. Claude GitHub App installed on repo
5. Triage workflow tested successfully on issue #2
6. GitHub labels created (bug, feature, ai-ready, priority-*, needs-human)

### 📁 Files in Repo
```
.github/workflows/          # 6 workflow files
.claude/agents/             # 6 agent definitions
src/
  lib/philosophers/         # Socrates, Nietzsche, Beauvoir definitions
  lib/db/                   # Prisma client
  types/                    # TypeScript types
  app/api/health/           # Health check endpoint
prisma/schema.prisma        # Database schema
CLAUDE.md                   # Master config for all agents
AGENT_STATE.md              # Cross-agent coordination
package.json                # Dependencies
tsconfig.json               # TypeScript config
```

### 🔄 Pending / Next Steps
1. Check issue #2 to see triage output: `gh issue view 2`
2. Test bug-fix agent: `gh issue edit 2 --add-label "bug" --add-label "ai-ready"`
3. Add actual UI code (currently just types and API stubs)
4. Set up Railway deployment
5. Add real philosophers beyond the 3 starters

---

## Key Patterns

### Agent Coordination
- All agents read `CLAUDE.md` for project rules
- Agents update `AGENT_STATE.md` with their progress
- Escalation to @jeremy when stuck >30min or after 3 CI failures

### Quality Gates
```bash
npm run lint          # ESLint
npm run typecheck     # TypeScript strict
npm run test          # Vitest
npm run build         # Next.js build
```

### Branch Naming
- `fix/<issue-number>-<description>`
- `feat/<issue-number>-<description>`

### Commit Format
`<type>(<scope>): <description>` where type is feat|fix|docs|test|chore|ci

---

## Useful Commands

```bash
# Watch workflow runs
gh run list
gh run watch

# Trigger workflows manually
gh workflow run triage.yml -f issue_number=2
gh workflow run bug-fix.yml -f issue_number=2
gh workflow run qa.yml
gh workflow run release-eng.yml
gh workflow run marketing.yml

# Create issues
gh issue create --title "Bug: something broken" --body "Details..." --label "bug"

# View issues
gh issue list
gh issue view <number>

# Add labels to trigger bug-fix
gh issue edit <number> --add-label "bug" --add-label "ai-ready"
```

---

## Architecture Sources

This setup synthesized patterns from:
- **claude-did-this/claude-hub**: Autonomous loop, container-per-task
- **doodledood/claude-code-workflow**: CLAUDE.md as master config, spec-first
- **VoltAgent/awesome-claude-code-subagents**: Agent role definitions, tool permissions
- **continuous-claude**: AGENT_STATE.md for cross-agent memory

---

## Philosophers Included

3 starter philosophers with full system prompts:

1. **Socrates** (Ancient) - Ethics, Epistemology, Dialectic
   - Socratic method, asks questions, humble
   
2. **Friedrich Nietzsche** (Modern) - Existentialism, Ethics, Aesthetics
   - Will to power, Übermensch, provocative but life-affirming
   
3. **Simone de Beauvoir** (Contemporary) - Existentialism, Feminism, Ethics
   - "One is not born but becomes a woman", situated freedom

Definitions in `src/lib/philosophers/`.

---

## Issues to Fix

The codebase is a skeleton - needs real UI:
- No actual pages/components yet
- No WebSocket server implementation
- No conversation storage logic
- No Anthropic API integration for responses

Good first task for Claude Code:
> "Add a basic Next.js home page that lists the philosophers with their names, eras, and a 'Start Chat' button for each."

---

## Contact

- Maintainer: @jeremy (escalation target for all agents)
- Repo: https://github.com/jeremymatthewwerner/dining-philosophers-Dec25-sw-factory
