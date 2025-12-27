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
- `automation` (#BFDADC) - Automated by agents
- `ci-failure` (#B60205) - CI failure issues
- `status:bot-working` (#7057FF) - Bot is actively working on this issue
- `status:awaiting-human` (#D93F0B) - Blocked waiting for human input
- `status:awaiting-bot` (#0E8A16) - Human commented, bot will respond
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

**E2E Debugging (CI captures server logs)**:
- When E2E tests fail in CI, backend logs are automatically captured
- **Artifacts uploaded:** `/tmp/backend.log`, `test-results/`, `playwright-report/`
- **Logs printed:** Backend logs appear in CI output on failure
- **To debug:** Check the workflow run artifacts and look for API errors, exceptions, or slow responses in backend logs

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
2. Commit changes with issue references (`Relates to #N` in commit messages)
3. Push to feature branch and create PR
4. CI runs on PR - must pass before merge
5. Merge PR (squash) - triggers deploy
6. Issues auto-close when PR merges

**CRITICAL: Issue Reference Rules (prevents premature closure)**
- **In commit messages:** Use `Relates to #N` (NOT `Fixes #N`)
- **In PR descriptions:** Use `Fixes #N` (closes issue when PR merges)
- **NEVER push directly to main** - Always use a feature branch + PR
- **Why:** GitHub auto-closes issues when commits on main contain "Fixes #N", even if the actual fix PR hasn't merged yet. This caused issue #84 to close prematurely.

**Best practices:**
- Commit frequently with clear messages
- One logical change per commit
- Always reference GitHub issues in commits (with `Relates to #N`)

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

All agents MUST post progress updates to their issues for visibility using the **checkbox progress pattern**.

#### Checkbox Progress Pattern

Agents create a progress comment/issue with checkboxes, then **edit that same content** (not post new comments) to check off items as they complete. This provides:
- Real-time visibility into agent progress
- A single place to see status (not scattered across comments)
- Clear indication of what's done and what's pending

**Example Progress Tracker:**
```markdown
## 🤖 Progress Tracker

- [x] 📖 Reading issue and understanding requirements
- [x] 🔍 Analyzing codebase and finding affected files
- [ ] 🛠️ Implementing fix
- [ ] ✅ Running tests and quality checks
- [ ] 📝 Creating PR
- [ ] 🚀 Waiting for CI

**Status:** Implementing fix...
**Workflow:** [View logs](...)

---
### Analysis
**Root Cause:** [discovered issue]
**Files Affected:** [list]
**Proposed Fix:** [plan]
```

Agents update this by editing the comment/issue body via API:
```bash
gh api repos/OWNER/REPO/issues/comments/COMMENT_ID -X PATCH -f body="[updated body]"
```

**Code Agent** creates a progress comment on each issue:
1. Initial: All boxes unchecked, "Starting analysis..."
2. Checks boxes as each step completes
3. Adds Analysis section after analyzing
4. Adds PR link when submitted
5. Monitors CI, auto-merges on success
6. Final: "✅ CI Passed & Merged" → triggers deploy → issue auto-closes

**Full Autonomous Flow:**
```
Issue Created → Triage labels → Code Agent fixes → PR created → CI passes → Auto-merge → Deploy → Issue closes
```

**QA Agent** creates a tracking issue with checkboxes:
1. Creates issue: "🤖 QA Agent: [focus] ([day])" with progress checklist
2. Edits issue body to check boxes and fill in sections
3. Closes issue with PR link when complete

**CI Monitor** triggers Code Agent automatically:
1. Creates issue with `bug`, `priority-high`, `ci-failure` labels
2. Adds `ai-ready` label separately (triggers Code Agent's `labeled` event)
3. Code Agent picks up and attempts fix

### Interacting with the Code Agent

**Comment-driven interaction:** You can comment on any issue with `@claude` to ask questions or provide suggestions. The bot will:
1. Read your comment and the full issue context
2. Think about your question/suggestion
3. Post a thoughtful response
4. Take action if appropriate

**Status labels indicate who should act next:**
| Label | Meaning | Who Acts |
|-------|---------|----------|
| `status:bot-working` | Bot is actively working | Wait for bot |
| `status:awaiting-human` | Bot needs your input | You respond |
| `status:awaiting-bot` | You commented, bot will respond | Wait for bot |
| (no status label) | No active work | Add `ai-ready` to trigger |

**Example workflow:**
1. Issue created with `bug` + `ai-ready` labels
2. Bot starts → `status:bot-working`
3. Bot has a question → `status:awaiting-human` + comment asking
4. You reply with `@claude here's the answer...`
5. Bot responds → `status:bot-working`
6. Bot creates PR → removes status labels

**Concurrency:** Only one bot run per issue at a time. Comments are queued, not dropped.

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
