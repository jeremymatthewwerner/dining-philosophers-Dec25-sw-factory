# Dining Philosophers

Real-time multi-party chat with AI-simulated historical and contemporary thinkers.

**Live**: [diningphilosophers.ai](https://diningphilosophers.ai)

## Autonomous Software Factory

This repository uses 7 AI-powered GitHub Actions agents for autonomous development:

| Agent | Trigger | Purpose |
|-------|---------|---------|
| **Triage** | Issue opened | Classifies issues, detects duplicates, adds labels |
| **Code Agent** | `ai-ready` + `bug`/`enhancement` labels | Diagnoses and fixes issues, creates PRs |
| **QA** | Nightly 2am UTC | Improves test coverage, hunts flaky tests |
| **Release Eng** | Daily 3am UTC | Security audits, dependency updates |
| **DevOps** | Every 6 hours | Health checks, incident response |
| **Marketing** | On release | Updates changelog, docs |
| **CI Monitor** | On CI failure (main) | Auto-creates issues for failed builds |

Add `ANTHROPIC_API_KEY` to repo secrets to enable automation.

## Working with AI Agents (Human Guide)

### Filing Issues

1. **Create an issue** describing the bug or feature
2. **Triage Agent** automatically adds labels within minutes
3. **Add `ai-ready` label** when you want the Code Agent to work on it
4. The Code Agent will analyze, implement, and create a PR

### Talking to the Bot

**Mention `@claude` in any comment** on an `ai-ready` issue to:
- Ask clarifying questions: `@claude what files are affected?`
- Give suggestions: `@claude consider using the existing helper in utils.py`
- Request actions: `@claude please also add a test for the error case`

The bot will read the full context, think about your input, and respond.

### Status Labels (Who Should Act)

| Label | What It Means | What You Do |
|-------|---------------|-------------|
| `status:bot-working` | Bot is actively working | Wait — check back in 10-15 min |
| `status:awaiting-human` | Bot needs your input | Read its question and reply with `@claude` |
| `status:awaiting-bot` | You commented, bot will respond | Wait — it will respond soon |
| *(no status label)* | No active work | Add `ai-ready` to trigger the bot |

### Notifications to Watch

Enable GitHub notifications for:
- **Issues you're mentioned in** — bot may ask you questions
- **PRs on this repo** — bot creates PRs that may need review
- **CI failures** — the CI Monitor creates issues automatically

### When to Intervene

The factory is designed to run autonomously. Intervene only when:
- Bot adds `needs-human` label (it's stuck)
- Bot asks a question in `status:awaiting-human`
- PR needs architectural review before merge
- Security concern

**If you intervene to fix something, consider**: Can we update the workflow so the bot handles this automatically next time?

### Example Workflow

```
1. You create issue: "Button doesn't work on mobile"
2. Triage Agent adds: bug, priority-medium
3. You add: ai-ready
4. Code Agent starts → status:bot-working
5. Code Agent comments: "## Analysis - Root cause: missing touch handler..."
6. You comment: "@claude make sure to test on iOS Safari too"
7. Code Agent responds and incorporates feedback → status:bot-working
8. Code Agent creates PR → removes status labels
9. CI passes → you merge (or it auto-merges)
10. Issue auto-closes
```

## Quick Start (Local Development)

### Prerequisites

- [uv](https://docs.astral.sh/uv/) - Python package manager
- [Node.js](https://nodejs.org/) v18+
- [Anthropic API key](https://console.anthropic.com/)

### Setup

```bash
# Clone the repo
git clone https://github.com/jeremymatthewwerner/dining-philosophers-Dec25-sw-factory.git
cd dining-philosophers-Dec25-sw-factory

# Run setup script
./scripts/setup.sh

# Add your Anthropic API key
echo "ANTHROPIC_API_KEY=your-key-here" >> backend/.env
```

### Run

```bash
./scripts/dev.sh
```

- Frontend: http://localhost:3000
- Backend: http://localhost:8000
- API Docs: http://localhost:8000/docs

### Test

```bash
./scripts/test-all.sh
```

## Deploy to Railway

### Prerequisites

- [Railway CLI](https://docs.railway.app/develop/cli) - `npm install -g @railway/cli`
- Railway account at https://railway.app

### Deployment

```bash
./scripts/deploy-railway.sh
```

This interactive script will guide you through:
1. Creating a new Railway project
2. Setting up PostgreSQL
3. Deploying backend and frontend services

## GitHub Secrets Required

Add these secrets in **Settings** → **Secrets and variables** → **Actions**:

| Secret | Description |
|--------|-------------|
| `ANTHROPIC_API_KEY` | Anthropic API key (for agents + E2E tests) |
| `RAILWAY_TOKEN` | Railway project token for deployments |
| `PRODUCTION_BACKEND_URL` | Backend URL for frontend build |
| `PRODUCTION_FRONTEND_URL` | Frontend URL for smoke tests |

## Project Structure

```
dining-philosophers-Dec25-sw-factory/
├── .github/workflows/     # 7 autonomous agent workflows
├── .claude/agents/        # Agent role definitions
├── backend/               # FastAPI backend
│   ├── app/
│   │   ├── api/           # API routes
│   │   ├── core/          # Config, database
│   │   ├── models/        # SQLAlchemy models
│   │   ├── schemas/       # Pydantic schemas
│   │   └── services/      # Business logic
│   ├── tests/
│   ├── Dockerfile
│   └── railway.json
├── frontend/              # Next.js frontend
│   ├── src/
│   ├── e2e/               # Playwright tests
│   ├── Dockerfile
│   └── railway.json
├── scripts/
│   ├── setup.sh           # Local dev setup
│   ├── dev.sh             # Run dev servers
│   └── test-all.sh        # Run all tests
├── CLAUDE.md              # Master config for all agents
├── AGENT_STATE.md         # Cross-agent coordination
├── REQUIREMENTS.md        # Product specification
└── TEST_PLAN.md           # Test cases
```

## Tech Stack

- **Frontend**: Next.js, TypeScript, TailwindCSS
- **Backend**: FastAPI, SQLAlchemy, Python 3.11
- **Database**: SQLite (local), PostgreSQL (production)
- **AI**: Claude API (Anthropic)
- **Real-time**: WebSockets
- **Deployment**: Railway

## Environment Variables

### Backend (`backend/.env`)

| Variable | Description | Default |
|----------|-------------|---------|
| `ANTHROPIC_API_KEY` | Anthropic API key | (required) |
| `DATABASE_URL` | Database connection URL | `sqlite+aiosqlite:///./thinkers_chat.db` |
| `DEBUG` | Enable debug mode | `true` |
| `CORS_ORIGINS` | Allowed CORS origins | `http://localhost:3000` |

### Frontend (`frontend/.env.local`)

| Variable | Description | Default |
|----------|-------------|---------|
| `NEXT_PUBLIC_API_URL` | Backend API URL | `http://localhost:8000` |
| `NEXT_PUBLIC_WS_URL` | WebSocket URL | `ws://localhost:8000` |
