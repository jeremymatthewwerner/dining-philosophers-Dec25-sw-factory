# CLAUDE.md - Dining Philosophers

Real-time multi-party chat with AI-simulated historical/contemporary thinkers.

## Project Overview
- **Name**: Dining Philosophers
- **Description**: Real-time chat with historical philosophers
- **Domain**: https://diningphilosophers.ai
- **Hosting**: Railway
- **Maintainer**: @jeremymatthewwerner

## Repository Setup (One-Time)

**Before the autonomous factory can run without intervention, complete these steps:**

### 1. GitHub App Permissions
Go to **Settings → Actions → General** and grant these permissions to the GitHub App:
- ✅ `workflows` - Allows agents to modify `.github/workflows/` files
- ✅ `contents: write` - Allows agents to push code
- ✅ `issues: write` - Allows agents to create/update issues
- ✅ `pull-requests: write` - Allows agents to create PRs

### 2. Required Labels
Create these labels (or run: `gh label create <name> --color <color>`):
- `ai-ready` (#0E8A16) - Ready for autonomous agent
- `needs-human` (#D93F0B) - Requires human intervention
- `qa-agent` (#0052CC) - QA Agent tracking issues
- `ci-failure` (#B60205) - CI failure issues
- `bug`, `enhancement`, `priority-high`, `priority-medium`, `priority-low`

### 3. Secrets
Ensure these secrets are set in **Settings → Secrets and variables → Actions**:
- `ANTHROPIC_API_KEY` - For Claude API access
- `GITHUB_TOKEN` - Auto-provided, but verify workflow permissions

### 4. Branch Protection (Optional)
If using branch protection on `main`, ensure:
- Allow GitHub Actions to bypass (for auto-merge)
- Or use admin merge for agent PRs

**Once setup is complete, the factory should run autonomously.**

## Autonomous Software Factory Philosophy

**This repo is designed to run as an autonomous software factory.** The goal is for AI agents to handle routine development tasks without human intervention.

**Key Principles:**
- **Human intervention = factory bug** - If a human needs to step in to fix something, that's a bug in the factory itself, not just a bug in the code
- **Fix the factory, not the symptom** - When intervening, always ask: "How can I prevent needing to intervene for this type of issue again?"
- **Visibility enables autonomy** - Agents must post progress updates to issues so humans can monitor without intervening
- **Self-healing over manual fixes** - CI failures auto-create issues, agents auto-fix them

**When you (human or Claude) intervene:**
1. Fix the immediate issue
2. Update the relevant agent workflow to handle this case autonomously next time
3. Document the improvement in this file

## IMPORTANT Rules

- ALWAYS write tests alongside code (unit, integration, E2E)
- NEVER commit code without tests - minimum 70% coverage (goal: 85%, tracked via QA agent)
- Commit and push frequently at logical checkpoints
- See REQUIREMENTS.md for full product specification
- **ALWAYS check things yourself before asking the user** - Use available tools (CLI, API calls, logs, code inspection) to verify state, configuration, or behavior. Only ask the user to check something if you've confirmed there's no way for you to check it directly.
- **ALWAYS check CI results after every push** - Use `gh run list` and `gh run view <id> --log-failed` to verify CI passes. If CI fails, debug and fix immediately. Do not consider a task complete until CI is green.
- **When resuming work or assessing project state, ALWAYS check CI first** - Run `gh run list` before anything else. There may be failed runs from a previous session that need fixing.
- **ALWAYS check open issues at session start** - Run `gh issue list` and work from highest priority (P0 → P1 → P2). Critical bugs must be addressed before new features.

## Tech Stack

- **Frontend**: Next.js (TypeScript strict mode)
- **Backend**: Python / FastAPI
- **Database**: PostgreSQL
- **LLM**: Claude API
- **Real-time**: WebSockets
- **Deployment**: Railway

## Quality Gates

```bash
# Backend
cd backend
uv run pytest                    # run tests
uv run pytest --cov=app          # run tests with coverage
uv run ruff check .              # lint
uv run ruff format .             # format
uv run mypy .                    # type check
uv run uvicorn app.main:app --reload  # dev server

# Frontend
cd frontend
npm test                         # jest tests
npm run lint                     # eslint
npm run typecheck                # tsc
npm run dev                      # dev server
npx playwright test              # e2e tests

# Full test suite
./scripts/test-all.sh
```

## Development Workflow (MANDATORY)

At every meaningful milestone (new feature, API changes, UI flow completion):

1. **Run all unit tests** - `./scripts/test-all.sh` or run backend/frontend tests separately
2. **Run E2E tests** - `cd frontend && npx playwright test` (with backend running)
3. **Local user testing** - Have user manually test the feature in browser
4. **Fix any issues** - Repeat steps 1-3 until passing
5. **Commit and push** - Only after E2E and manual testing pass

**Why this matters**: Unit tests with mocked APIs won't catch schema mismatches between frontend and backend. E2E tests exercise the real API and catch integration bugs before they reach the user.

**E2E test requirements**:
- Every user-facing flow must have E2E coverage
- Test the happy path AND error cases
- Use real backend (not mocked) to validate actual API contracts

**When E2E tests hang or timeout (CRITICAL)**:
- **DO NOT assume it's a test or framework issue** - E2E tests exercise real code paths
- **ASSUME a real regression** - Something in recent changes broke the functionality
- **Investigate recent commits** - Look at what changed since tests last passed
- **Check the feature being tested** - If a test for "thinker suggestions" hangs, the thinker suggestion code likely has a bug
- **Avoid piling on fixes** - Don't keep adjusting test timeouts or adding workarounds; find and fix the root cause

## Testing

- **Backend**: pytest + pytest-asyncio + pytest-cov
- **Frontend**: Jest + React Testing Library
- **E2E**: Playwright
- Coverage minimum: 70% (goal: 85%)

### Test Rigor Protocol (MANDATORY)

**Before implementing any non-trivial feature or change:**
1. **Think deeply about test cases** - Consider what new unit, integration, and E2E tests are needed
2. **Document in TEST_PLAN.md** - Update the test plan document with new test cases before writing code
3. **Consider edge cases** - What could go wrong? What are the boundary conditions?

**After implementing:**
1. **Write tests for all new code** - Don't just test happy paths
2. **Update existing tests** - If behavior changed, tests should change too
3. **Run full test suite** - Verify nothing regressed

## Code Style

- **Python**: ruff (format + lint + isort), mypy strict
- **TypeScript**: ESLint + Prettier, strict mode

### MANDATORY: Run Formatters and Linters Before Every Commit

**NEVER commit code without running formatters and linters first.** This applies to ALL code changes.

```bash
# Frontend (REQUIRED before every commit that touches frontend/)
cd frontend
npm run format          # Run Prettier to auto-fix formatting
npm run lint -- --fix   # Run ESLint with auto-fix
npm run typecheck       # Verify TypeScript types

# Backend (REQUIRED before every commit that touches backend/)
cd backend
uv run ruff format .    # Auto-format Python code
uv run ruff check . --fix  # Lint and auto-fix Python code
uv run mypy .           # Type check Python code
```

**The workflow is:**
1. Make code changes
2. Run formatters (`npm run format`, `uv run ruff format .`)
3. Run linters with auto-fix (`npm run lint -- --fix`, `uv run ruff check . --fix`)
4. Run type checking (`npm run typecheck`, `uv run mypy .`)
5. If any issues remain, fix them manually
6. THEN commit

## Git Workflow

**Claude Code sessions use feature branches:**
1. Create branch: `claude/<description>-<session-id>` (branch name is auto-assigned)
2. Commit changes with issue references (`Fixes #N` or `Relates to #N`)
3. Push to feature branch and create PR
4. CI runs on PR - must pass before merge
5. Merge PR (squash) - triggers deploy
6. Issues auto-close when PR merges

**Best practices:**
- Commit frequently with clear messages
- One logical change per commit
- Always reference GitHub issues in commits

## Commit Format

`<type>(<scope>): <description>` where type is feat|fix|docs|test|chore|ci

## GitHub CLI Setup

The `gh` CLI is required for creating PRs, checking CI, and managing issues.

```bash
# Install gh (if not present)
curl -L https://github.com/cli/cli/releases/download/v2.63.2/gh_2.63.2_linux_amd64.tar.gz -o /tmp/gh.tar.gz
tar -xzf /tmp/gh.tar.gz -C /tmp
sudo mv /tmp/gh_2.63.2_linux_amd64/bin/gh /usr/local/bin/

# Authenticate (required after install)
gh auth login --web --git-protocol https
```

When using `gh` commands, always specify the repo explicitly (the git remote uses a local proxy):
```bash
gh pr create --repo jeremymatthewwerner/dining-philosophers-Dec25-sw-factory ...
gh run list --repo jeremymatthewwerner/dining-philosophers-Dec25-sw-factory
gh issue list --repo jeremymatthewwerner/dining-philosophers-Dec25-sw-factory
```

## Task & Bug Tracking with GitHub Issues

All bugs AND tasks must be tracked via GitHub Issues for audit history and traceability.

### Issue Priority (MANDATORY)

**Always assign a priority label when creating issues:**
- **P0** - Blocks most or all functionality from working (critical bugs, system down)
- **P1** - Blocks some functionality from working correctly, OR new functionality requests
- **P2** - Optimizations, cleanup, refactoring, or minor improvements

### Issue Labels

Use labels to categorize issues:
- `bug` - Something isn't working
- `feature` / `enhancement` - New feature request
- `ai-ready` - Ready for autonomous agent to pick up
- `needs-human` - Requires human intervention
- `priority-high`, `priority-medium`, `priority-low`

## Autonomous Agents

This repo uses 7 AI-powered GitHub Actions agents. See `.github/workflows/` and `.claude/agents/` for details.

| Agent | Trigger | Purpose |
|-------|---------|---------|
| **Triage** | Issue opened | Classifies issues, detects duplicates, adds labels |
| **Code Agent** | `ai-ready` + `bug`/`enhancement` labels | Diagnoses and fixes issues, creates PRs |
| **QA** | Nightly 2am UTC | Test quality improvement with daily focus rotation |
| **Release Eng** | Daily 3am UTC | Security audits, dependency updates, CI optimization |
| **DevOps** | Every 6 hours | Health checks, incident response |
| **Marketing** | On release | Updates changelog, docs |
| **CI Monitor** | On CI failure (main) | Auto-creates `ai-ready` issues for failed builds |

### Agent Visibility (IMPORTANT)

All agents MUST post progress updates to their issues for visibility:

**Code Agent** posts to each issue it works on:
1. "🤖 Code Agent Started" - with workflow link
2. "## Analysis" - root cause, affected files, proposed fix
3. "## ✅ Fix Submitted" - PR link, changes, tests added
4. "## ❌ Failed" - error details, adds `needs-human` label

**QA Agent** creates a tracking issue for each run:
1. Creates issue: "🤖 QA Agent: [focus] ([day])"
2. Updates with: analysis → detailed plan → progress → results
3. Closes issue with PR link when complete

**CI Monitor** triggers Code Agent automatically:
1. Creates issue with `bug`, `priority-high`, `ci-failure` labels
2. Adds `ai-ready` label separately (triggers Code Agent's `labeled` event)
3. Code Agent picks up and attempts fix

### QA Agent - Test Quality Guardian

The QA agent performs **periodic reflection and enhancement** of the test suite:

**Daily Focus Rotation:**
- Monday: Coverage Sprint - bring lowest-coverage module up by 15%+
- Tuesday: Flaky Test Hunt - run tests 5x, identify and fix flaky tests
- Wednesday: Integration Test Gaps - add tests for untested API endpoints
- Thursday: E2E Enhancement - add edge case E2E tests (errors, mobile, edge cases)
- Friday: Test Refactoring - improve readability, reduce duplication
- Saturday: Edge Case Analysis - test error paths and boundary conditions
- Sunday: Regression Prevention - add tests for recent bug fixes

**Each run includes:**
1. Coverage analysis (backend + frontend)
2. E2E test completeness review
3. Test sophistication check (edge cases, error paths, race conditions)
4. Creation of meaningful tests (not just coverage padding)
5. **Update TEST_PLAN.md** with descriptions of all new tests added
6. PR with coverage diff and test descriptions

**E2E Enhancement Focus:**
- Empty form submissions, max length inputs, special characters
- Session expiry, network disconnection, concurrent operations
- Mobile-specific behaviors (touch, orientation, viewport)
- Error recovery and state persistence

### Agent Coordination

- All agents read this `CLAUDE.md` for project rules
- Agents update `AGENT_STATE.md` with their progress
- Escalation to @jeremymatthewwerner when stuck >30min or after 3 CI failures

### Known Limitations (require human intervention)

**Workflow file changes**: The GitHub App cannot modify `.github/workflows/` files due to missing `workflows` permission. When CI fails due to workflow config (like coverage thresholds), a human must update the workflow file.

**To fix**: Grant `workflows` permission to the GitHub App in repo Settings → Actions → General.

## Default Policies (for autonomous decisions)

When agents encounter these situations, apply these defaults instead of asking:

**Coverage threshold unreachable:**
- If coverage is >10% below the required threshold, lower threshold to (current + 5%)
- Create tracking issue for incremental improvement
- Let QA agent gradually increase coverage over time

**Test flakiness:**
- If a test fails intermittently, disable it with `@pytest.mark.skip(reason="flaky - issue #N")`
- Create issue to investigate and fix the root cause
- Don't block CI on flaky tests

**Dependency conflicts:**
- Pin to last known working version
- Create issue for proper resolution
- Don't spend >30min on dependency issues

## Escalation

Assign to @jeremymatthewwerner when:
- Stuck >30min
- CI fails 3x on same issue
- Needs architecture decision (not covered by default policies)
- Security concern

## Architecture

- Thinker agents run as independent async tasks (concurrent responses)
- Conversation only progresses when user has chat window open
- Agents resume automatically when user returns to chat
