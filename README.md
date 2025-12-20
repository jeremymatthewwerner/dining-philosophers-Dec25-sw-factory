# Dining Philosophers 🏛️

Chat with history's greatest minds at [diningphilosophers.ai](https://diningphilosophers.ai)

## Setup
```bash
npm install
cp .env.example .env.local  # Add your keys
npx prisma migrate dev
npm run dev
```

## Autonomous Agents
This repo uses AI-powered GitHub Actions. Add `ANTHROPIC_API_KEY` to repo secrets.

| Agent | Trigger |
|-------|---------|
| Triage | Issue opened |
| Bug Fix | `ai-ready` + `bug` labels |
| QA | Nightly |
| Release Eng | Weekly |
| DevOps | Every 6h |
| Marketing | On release |
