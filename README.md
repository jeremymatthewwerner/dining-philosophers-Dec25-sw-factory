# Dining Philosophers

Real-time multi-party chat with AI-simulated historical and contemporary thinkers.

**Live**: [diningphilosophers.ai](https://diningphilosophers.ai)

## Autonomous Software Factory

This repository uses 6 AI-powered GitHub Actions agents for autonomous development:

| Agent | Trigger | Purpose |
|-------|---------|---------|
| **Triage** | Issue opened | Classifies issues, detects duplicates, adds labels |
| **Bug Fixer** | `ai-ready` + `bug` labels | Diagnoses and fixes bugs, creates PRs |
| **QA** | Nightly 2am UTC | Improves test coverage, hunts flaky tests |
| **Release Eng** | Weekly Sunday 3am | Security audits, dependency updates |
| **DevOps** | Every 6 hours | Health checks, incident response |
| **Marketing** | On release | Updates changelog, docs |

Add `ANTHROPIC_API_KEY` to repo secrets to enable automation.

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
├── .github/workflows/     # 6 autonomous agent workflows
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
