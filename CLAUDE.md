# JARVIS Dashboard — Agent Instructions

## Mandatory Context Files

Before making ANY changes to JARVIS, read these files. They are the source of truth.

| File | Contains | When to update |
|------|----------|---------------|
| `ARCHITECTURE.md` | System overview, components, data flow, security | When architecture changes |
| `PRD.md` | Vision, capabilities, backlog, constraints, success metrics | When product scope changes |
| `ROADMAP.md` | Critical path to independence, Claude access strategy, failed approaches | When priorities or approach changes |

### Coherence Rule

If any decision, implementation, or design contradicts these documents:
1. **STOP** — do not proceed with the contradiction
2. **Update the document first** to reflect the new direction
3. **Then implement** the change

These documents must ALWAYS reflect the current reality. Never let code drift from docs.

### Key Facts (from ROADMAP.md — DO NOT forget)

- Claude API direct calls with OAuth tokens → 429 rate limited. DO NOT retry.
- Use PROMETHEUS bridge (claude-agent-sdk query()) for ALL Claude access.
- OpenCode serve is ONLY for delegate (sub-agent coding tasks), not chat.
- Target 100% test coverage AND 100% logging coverage.
- All secrets via 1Password op run. Never .env with real values.
- Every service containerized in Docker Compose (except OpenCode serve).
