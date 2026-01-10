# Comparison: This Factory vs OpenHands

This document provides a comprehensive comparison between our GitHub Actions-based autonomous software factory and [OpenHands](https://github.com/OpenHands/OpenHands), a popular open-source framework for AI coding agents.

## Executive Summary

| Aspect | This Factory | OpenHands |
|--------|-------------|-----------|
| **Primary Architecture** | GitHub Actions workflows | Python SDK + Docker sandboxes |
| **Execution Model** | Event-driven (issues/comments) | Conversation-driven (CLI/GUI/API) |
| **Sandbox Type** | GitHub Actions runners | Docker containers |
| **Agent Coordination** | @mention-based triggers | Single-agent or programmatic |
| **State Management** | GitHub Issues + Labels | Event-sourced conversation log |
| **Infrastructure** | Zero (uses GitHub's infra) | Self-hosted or cloud |
| **License** | Project-specific | MIT (enterprise separate) |
| **Maturity** | Production-ready for this project | 60k+ stars, enterprise-ready |

## Architecture Deep Dive

### This Factory: GitHub Actions-Based

Our factory uses GitHub as both the orchestration layer and execution environment:

```
┌──────────────────────────────────────────────────────────────────────┐
│                        GitHub Repository                              │
├──────────────────────────────────────────────────────────────────────┤
│  ┌────────────┐    ┌────────────┐    ┌────────────┐                  │
│  │   Issue    │───>│  Triage    │───>│   @code    │                  │
│  │  Created   │    │   Agent    │    │  mention   │                  │
│  └────────────┘    └────────────┘    └────────────┘                  │
│                                            │                          │
│                                            v                          │
│  ┌────────────┐    ┌────────────┐    ┌────────────┐                  │
│  │  Auto-     │<───│    CI      │<───│   Code     │                  │
│  │  merge     │    │  Passes    │    │   Agent    │                  │
│  └────────────┘    └────────────┘    └────────────┘                  │
│         │                                                             │
│         v                                                             │
│  ┌────────────┐    ┌────────────┐                                    │
│  │  Deploy    │───>│  Smoke     │───> Issue Auto-Closes              │
│  │  (Railway) │    │  Tests     │                                    │
│  └────────────┘    └────────────┘                                    │
└──────────────────────────────────────────────────────────────────────┘
```

**Key Components:**
- **9 Specialized Agents**: Triage, Code, QA, DevOps, Principal Engineer, Factory Manager, Marketing, CI Monitor, Release Engineer
- **Trigger Mechanism**: `@code`, `@devops`, `@pe`, `@factory-manager` mentions in comments
- **State Tracking**: GitHub Issues with labels (`status:bot-working`, `status:awaiting-human`)
- **CI/CD Integration**: Native GitHub Actions with Railway deployment
- **Human Escalation**: `needs-human` label when agents can't proceed

### OpenHands: SDK + Docker Architecture

OpenHands (V1) uses a modular Python SDK with optional Docker sandboxing:

```
┌──────────────────────────────────────────────────────────────────────┐
│                        OpenHands SDK                                  │
├──────────────────────────────────────────────────────────────────────┤
│  ┌─────────────────────────────────────────────────────────────────┐ │
│  │                    openhands.sdk                                │ │
│  │  (Agent, Conversation, LLM, Tool, MCP abstractions)            │ │
│  └─────────────────────────────────────────────────────────────────┘ │
│                              │                                        │
│              ┌───────────────┼───────────────┐                       │
│              v               v               v                        │
│  ┌─────────────────┐ ┌─────────────────┐ ┌─────────────────┐        │
│  │ openhands.tools │ │openhands.workspace│ │openhands.agent_│        │
│  │ (Bash, Edit,    │ │ (Local, Remote)  │ │    server      │        │
│  │  Browse, etc.)  │ │                  │ │ (REST/WebSocket)│        │
│  └─────────────────┘ └─────────────────┘ └─────────────────┘        │
│                              │                                        │
│              ┌───────────────┴───────────────┐                       │
│              v                               v                        │
│  ┌─────────────────────┐       ┌─────────────────────┐               │
│  │   LocalWorkspace    │       │   RemoteWorkspace   │               │
│  │ (Direct filesystem) │       │ (Docker container)  │               │
│  └─────────────────────┘       └─────────────────────┘               │
└──────────────────────────────────────────────────────────────────────┘
```

**Key Components:**
- **Modular SDK**: Four decoupled packages (sdk, tools, workspace, agent_server)
- **Workspace Abstraction**: LocalWorkspace for development, RemoteWorkspace for production
- **Event-Sourced State**: Immutable events with ConversationState as single source of truth
- **LLM Agnostic**: Supports Claude, GPT, and 100+ providers via LiteLLM
- **Deployment Options**: CLI, Local GUI, Cloud (SaaS), Enterprise (Kubernetes)

## Sandbox Comparison

### OpenHands Docker Sandboxes

OpenHands V0 mandated all tool execution in Docker containers. V1 made this opt-in:

**V0 (Legacy):**
```python
# All execution in Docker, regardless of safety
sandbox.run("rm -rf /") # Isolated, safe
sandbox.run("ls")       # Also in Docker, even though safe
```

**V1 (Current):**
```python
# Local by default, Docker when needed
workspace = LocalWorkspace()    # Fast, for development
workspace = RemoteWorkspace()   # Docker, for production/untrusted code
```

**Sandbox Features:**
- Full OS capabilities inside container
- Network isolation configurable
- Jupyter kernel for Python execution
- BrowserGym for web automation
- Resource limits (CPU, memory, disk)

### This Factory's "Sandboxes"

Our factory has multiple isolation layers that serve sandbox-like purposes:

#### 1. GitHub Actions Runner (Primary Sandbox)

```yaml
# .github/workflows/bug-fix.yml
jobs:
  fix:
    runs-on: ubuntu-latest      # Fresh VM for each run
    timeout-minutes: 60         # Time-limited execution
    steps:
      - uses: actions/checkout@v4
        with:
          token: ${{ secrets.PAT_WITH_WORKFLOW_ACCESS }}
```

**Characteristics:**
- Each workflow run gets a fresh Ubuntu VM
- No persistent state between runs
- Network access controlled by GitHub
- Tool access restricted via `--allowedTools` flag in Claude Code
- Automatic timeout (default 60 min)
- No direct access to production systems (must use APIs)

#### 2. Concurrency Groups (Single-Issue Isolation)

```yaml
concurrency:
  group: code-agent-issue-${{ github.event.issue.number }}
  cancel-in-progress: false
```

This ensures only one agent instance works on an issue at a time, preventing race conditions.

#### 3. Permission Boundaries

```yaml
permissions:
  contents: write      # Can push code
  issues: write        # Can manage issues
  pull-requests: write # Can create PRs
  # NOTE: No workflows:write - Code Agent delegates workflow changes
```

#### 4. Tool Allowlisting

```bash
claude_args: |
  --dangerously-skip-permissions
  --allowedTools "Bash(gh:*),Bash(git:*),Bash(npm:*),Read,Write,Edit,Glob,Grep"
```

Agents can only use explicitly allowed tools - they can't make arbitrary system calls.

#### 5. Railway Environment Isolation

Production access is isolated through the DevOps Agent:
```yaml
# Only DevOps Agent has RAILWAY_TOKEN
env:
  RAILWAY_TOKEN: ${{ secrets.RAILWAY_TOKEN_SW_FACTORY }}
```

Code Agent must request production data via `@devops` mentions.

## Feature Comparison

| Feature | This Factory | OpenHands |
|---------|-------------|-----------|
| **Code Editing** | Claude Code Edit/Write tools | CodeEditTool with AST awareness |
| **Shell Execution** | Bash tool with allowlist | CmdRunTool in sandbox |
| **Web Browsing** | WebFetch tool (limited) | BrowserGym with full automation |
| **File Search** | Grep/Glob tools | Built-in search tools |
| **Git Operations** | Bash(git:*) + gh CLI | Git tools with smart staging |
| **Python REPL** | Not native | Jupyter Kernel integration |
| **Multi-Agent** | Yes (9 agents, @mention routing) | Limited (single-agent focus) |
| **Human-in-Loop** | Labels + comments | Confirmation prompts |
| **Context Management** | Issue comments, CLAUDE.md | Event condensation + summarization |

## Strengths Comparison

### This Factory's Strengths

1. **Zero Infrastructure Cost**: Uses GitHub's free Actions runners
2. **Native GitHub Integration**: PRs, issues, comments, labels all work naturally
3. **Multi-Agent Specialization**: Different agents for different concerns (QA vs DevOps vs Code)
4. **Audit Trail Built-in**: Every action is a commit, comment, or workflow run
5. **Progressive Escalation**: Code Agent → Principal Engineer → Human
6. **CI/CD Native**: Tests, deploys, and verification are first-class citizens
7. **Factory Self-Healing**: Factory Manager monitors and fixes stuck processes
8. **Community Familiar**: Uses standard GitHub workflows developers know

### OpenHands' Strengths

1. **Portable Architecture**: Not tied to any platform (GitHub, GitLab, etc.)
2. **True Sandboxing**: Docker containers with full OS isolation
3. **LLM Agnostic**: Works with any provider, easy to switch
4. **Interactive Mode**: CLI and GUI for real-time development
5. **Event Sourcing**: Deterministic replay and debugging
6. **Enterprise Ready**: Kubernetes deployment, SSO, audit logs
7. **Active Community**: 60k+ GitHub stars, major contributors
8. **Benchmark Performance**: 72.8% on SWE-Bench Verified (state-of-art)

## Weaknesses Comparison

### This Factory's Weaknesses

1. **GitHub Lock-in**: Tightly coupled to GitHub's ecosystem
2. **No True Sandbox**: Runner isolation is less robust than Docker
3. **Single LLM**: Currently Claude-only (via Anthropic API)
4. **Limited Local Development**: Designed for CI, not interactive use
5. **Workflow Complexity**: Many YAML files to maintain
6. **Cold Start Latency**: Each run spins up a new runner (30-60s)
7. **GitHub Rate Limits**: API calls are rate-limited
8. **No Persistent Agent State**: Each run is independent

### OpenHands' Weaknesses

1. **Infrastructure Required**: Need to run Docker, servers, etc.
2. **Complexity**: Four packages, many configuration options
3. **Resource Heavy**: Docker containers need memory/CPU
4. **Single-Agent Focus**: Multi-agent orchestration less mature
5. **CI/CD Not Native**: Need separate integration work
6. **Learning Curve**: SDK is powerful but complex
7. **Enterprise Cost**: Full features require commercial license
8. **Network-Isolated Testing**: Harder to test with real APIs

## When to Use Each

### Use This Factory When:

- You're building a GitHub-hosted open source project
- You want zero infrastructure management
- You need tight CI/CD integration
- Multiple specialized agents would help (QA, DevOps, etc.)
- You want a full audit trail in GitHub
- Your team is familiar with GitHub Actions

### Use OpenHands When:

- You need platform independence
- True sandboxing is a security requirement
- You want local/interactive development
- You need to switch LLM providers easily
- Enterprise deployment (Kubernetes, SSO) is required
- You're building a product around AI coding agents

## Hybrid Approaches

Both systems could theoretically be combined:

1. **OpenHands in Actions**: Run OpenHands CLI in GitHub Actions for better sandboxing
2. **GitHub + OpenHands Server**: Use this factory for coordination, OpenHands for execution
3. **OpenHands for Local, Actions for CI**: Develop with OpenHands locally, deploy with Actions

## Security Model Comparison

| Aspect | This Factory | OpenHands |
|--------|-------------|-----------|
| **Code Execution** | GitHub runner (shared, ephemeral) | Docker (isolated, configurable) |
| **Secrets Access** | GitHub Secrets with per-workflow grants | Environment variables in container |
| **Network** | GitHub-controlled, egress allowed | Configurable isolation |
| **File System** | Ephemeral workspace | Container-scoped or local |
| **Human Approval** | Label-based gates | SecurityAnalyzer + ConfirmationPolicy |
| **Audit Log** | GitHub Actions logs | Event log with full history |

## Conclusion

Both systems represent different philosophies for autonomous software development:

- **This Factory** is optimized for GitHub-native development with zero infrastructure overhead and multi-agent specialization. It's ideal for open-source projects that want AI assistance integrated into their existing GitHub workflow.

- **OpenHands** is a more general-purpose SDK that offers true sandboxing, LLM flexibility, and multiple deployment options. It's better suited for teams building AI coding products or needing platform independence.

Neither is strictly "better" - the choice depends on your constraints, existing infrastructure, and whether you prioritize GitHub integration vs platform independence.

## References

- [OpenHands GitHub Repository](https://github.com/OpenHands/OpenHands)
- [OpenHands Documentation](https://openhands.dev/)
- [OpenHands SDK Paper (arXiv)](https://arxiv.org/html/2511.03690v1)
- [OpenHands Platform Paper (arXiv)](https://arxiv.org/abs/2407.16741)
- This factory's [CLAUDE.md](../CLAUDE.md) for full architecture documentation
