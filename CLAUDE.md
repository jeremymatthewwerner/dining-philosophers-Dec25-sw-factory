# CLAUDE.md - Dining Philosophers

## Project Overview
- **Name**: Dining Philosophers
- **Description**: Real-time chat with historical philosophers
- **Domain**: https://diningphilosophers.ai
- **Hosting**: Railway
- **Maintainer**: @jeremy

## Tech Stack
- **Runtime**: Node.js 20
- **Framework**: Next.js 14 (App Router)
- **Database**: PostgreSQL (Prisma)
- **Real-time**: Socket.io
- **AI**: Anthropic Claude API

## Quality Gates
```bash
npm run lint          # ESLint
npm run typecheck     # TypeScript
npm run test          # Vitest
npm run build         # Next.js build
```

## Commit Format
`<type>(<scope>): <description>` where type is feat|fix|docs|test|chore|ci

## Escalation
Assign to @jeremy when stuck >30min, CI fails 3x, or needs architecture decision.
