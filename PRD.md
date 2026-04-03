# PRD: JARVIS — Personal AI Agent

> Status: **living document**
> Last updated: 2026-04-03
> Owner: Miguel (MiguelAguiarDEV)

---

## 1. Vision

JARVIS is a personal AI agent with consciousness — not a chatbot, not a dashboard, not an automation tool. It is a persistent entity that remembers, reasons, delegates, and acts across sessions, reboots, and context resets.

The mental model: **a senior engineer colleague who never sleeps**, runs on a homelab server, and can be reached via web chat or Discord DM. JARVIS orchestrates work, manages tasks, monitors infrastructure, and learns from every interaction.

JARVIS is not trying to replicate a human brain. It is a pragmatic system that borrows principles from cognitive neuroscience (memory consolidation, spaced retrieval, metacognition) where they produce measurable improvements.

---

## 2. Target User

- **Single user**: Miguel — full-stack developer, homelab enthusiast.
- **Context**: personal productivity system running on a single Ubuntu server (4 cores, 7.5GB RAM, Tailscale network).
- **Not a product for other users** — no multi-tenant, no onboarding, no RBAC beyond single-user auth.

---

## 3. Architecture Summary

**Monorepo**: `github.com/MiguelAguiarDEV/jarvis`

### Subsystems (mythology-inspired naming)

| Subsystem | Role | Tech |
|-----------|------|------|
| **ATHENA** | Orchestrator — receives requests, reasons, delegates, responds | Go (mnemo server) |
| **NEXUS** | Dashboard — web chat, task board, cost metrics, activity feed | Next.js |
| **HERMES** | Discord bot — DM notifications, message routing | Go |
| **PROMETHEUS** | Claude bridge — OpenCode serve sessions for code execution | OpenCode serve + Claude credentials |
| **MNEMO** | Persistent memory — search and save knowledge across sessions | Engram (SQLite + FTS5 + Postgres cloud) |
| **MORPHEUS** | Memory consolidation — background process for importance ranking | Go (background goroutine) |
| **SENTINEL** | Health monitoring — checks server, DB, services every 15 min | Go (cron) |
| **ATLAS** | Skill loader — dynamic skill loading from compact index | Go |

### Infrastructure

- Docker Compose (4 services: postgres, mnemo-cloud, dashboard, discord-bot)
- 1Password for secrets management
- systemd for OpenCode serve
- Tailscale for network access (100.71.66.54)

---

## 4. Core Capabilities (MVP — Implemented)

### Conversational Interface
- Web chat (NEXUS dashboard, SSE streaming)
- Discord DM (HERMES bot, routes to ATHENA)
- Natural language in/out, Spanish or English

### Task Management
- Create, list, complete tasks via natural language
- Task decomposition (break complex work into subtasks)
- Status tracking visible in dashboard

### Sub-Agent Delegation
- JARVIS delegates complex work to PROMETHEUS (OpenCode serve)
- Async execution — responds immediately with job ID
- Discord DM notification when work completes
- Worker runs in background, JARVIS keeps chatting

### Skill System
- 8 MVP tools: `load_skill`, `create_task`, `list_tasks`, `complete_task`, `delegate`, `notify`, `search_memory`, `save_memory`
- Dynamic loading via `load_skill(name)` — LLM autonomously selects from compact index
- `/skill-name` forced-load override
- `always: true` enforcement for critical skills (server-guardrails, server-knowledge)
- Three catalog tiers: Global (KB), JARVIS ops, Project (per repo)
- Standardized frontmatter format (name, description, always, triggers)

### Persistent Memory (Engram)
- Cross-session memory via Engram (SQLite + FTS5 locally, Postgres cloud)
- `search_memory` and `save_memory` tools
- Cloud sync for backup and multi-device access
- Survives reboots, compactions, context resets

### Server Knowledge
- Auto-generated awareness of homelab state (hourly cron scan)
- Server guardrails skill (always loaded)
- Docker, disk, services, network state

### Cost Tracking
- Per-message token usage (input/output tokens)
- Estimated cost from model pricing tables
- Real-time display in dashboard

### Model Routing
- Sonnet for simple requests, Opus for complex
- Auto-downgrade at budget threshold (90%)
- Hot-swap on budget limits

### Notifications
- Discord DM alerts for completed tasks, errors, delegation results
- Notifier interface (extensible to other channels)

---

## 5. Planned Capabilities (Backlog)

### P0 — Next Up

| Capability | Description | Why |
|------------|-------------|-----|
| Traces collection | OpenTelemetry integration — what tools were called, latency, error rates | Can't optimize what you can't measure |
| Cost dashboard | Historical cost view, budget visualization, per-project breakdown | Budget is hard constraint; need visibility |

### P1 — High Value

| Capability | Description | Why |
|------------|-------------|-----|
| Dashboard HUD redesign | Multi-panel grid, terminal aesthetic, real-time metrics | Current UI is functional but not information-dense |
| Proactive behavior | JARVIS initiates actions: monitoring alerts, maintenance tasks, daily summaries | Shift from reactive to proactive assistant |

### P2 — Medium Term

| Capability | Description | Why |
|------------|-------------|-----|
| Multi-agent coordination | Multiple JARVIS instances via Postgres LISTEN/NOTIFY (hive mind) | Parallel work on different projects |
| Neuroscience-inspired memory | Spaced retrieval, importance ranking, forgetting curves, consolidation phases | Better signal-to-noise in long-term memory |

### P3 — Exploratory

| Capability | Description | Why |
|------------|-------------|-----|
| Mobile / Telegram | Access JARVIS from phone | Convenience |
| Voice interface | Speech-to-text input, text-to-speech output | Hands-free interaction |

---

## 6. Budget and Constraints

| Constraint | Value | Notes |
|------------|-------|-------|
| Monthly budget | 400 EUR | 200 EUR Claude Pro + 200 EUR ChatGPT Pro |
| LLM access | OpenCode serve | Subscription-based, not API tokens. Single Claude bridge process. |
| Compute | 1 homelab server | 4 cores, 7.5GB RAM, Ubuntu, Tailscale |
| Concurrency | Max 2 sub-agents | RAM pressure at 7.5GB with LLM agent + services |
| Infrastructure | Docker Compose only | No Kubernetes — single-server, not needed |

### Model Routing Strategy

- **Simple requests** (greetings, status checks, memory lookups): Sonnet — fast, cheap
- **Complex requests** (code analysis, architecture, multi-step reasoning): Opus — accurate, expensive
- **Budget guard**: auto-downgrade to Sonnet at 90% monthly budget consumption
- **Hard cap**: reject non-critical requests at 100% budget

---

## 7. Success Metrics

| Metric | Target | How to Measure |
|--------|--------|----------------|
| Response latency | < 5 seconds for first token | Dashboard timing |
| Task completion via NL | > 90% success rate | Manual audit of task commands |
| Budget adherence | Stay within 400 EUR/month | Cost dashboard (P0) |
| Uptime | > 99% | Docker restart policies + SENTINEL health checks |
| Memory persistence | Survives reboots, compactions, context resets | Engram cloud sync + backup verification |
| Skill auto-selection | Correct skill loaded 8/10 times | Log audit of `load_skill` calls |
| E2E test pass rate | > 90% | test-all.sh (currently 55/58) |

---

## 8. Non-Goals

- **Not a product for other users** — no multi-tenant, no onboarding flows, no pricing tiers.
- **Not a replacement for a full IDE** — JARVIS orchestrates and delegates; it doesn't write code directly in the user's editor.
- **Not trying to replicate a human brain** — neuroscience research (memory consolidation, spaced retrieval) is exploratory and applied only where it produces measurable improvements.
- **No Kubernetes** — Docker Compose is sufficient for a single-server deployment. Complexity not justified.
- **No cloud compute infrastructure** — all processing runs on the homelab server.

---

## 9. Risks

| Risk | Likelihood | Impact | Mitigation |
|------|------------|--------|------------|
| OpenCode serve dependency | Medium | High | Single point of failure for Claude access. Monitor uptime via SENTINEL. Evaluate backup LLM providers. |
| Budget overrun | Medium | Medium | Model routing with auto-downgrade. Real-time cost tracking. Hard budget caps at 100%. |
| Context window limits | Medium | Medium | Engram persistent memory. Skill-based context injection (load only what's needed). Task decomposition. |
| RAM pressure (7.5GB) | Medium | Medium | Limit concurrent sub-agents to 2. Monitor with SENTINEL. Upgrade RAM if needed. |
| Mnemo data loss | Low | High | Cloud sync (Postgres), .mnemo/ chunk export, periodic backup verification. |
| LLM fails to select correct skill | Medium | Low | `always: true` for critical skills. `/skill-name` override. Logging to detect misses. |
| Scope creep ("personal AI OS" is infinite) | High | Medium | Strict prioritization (P0-P3). MVP-first. Ship, measure, iterate. |

---

## 10. Key Decisions (from Grill Session)

These decisions were resolved on 2026-03-31 through a structured grill session:

1. **Identity**: JARVIS = LLM agent with consciousness, not just a dashboard or automation tool.
2. **Communication**: Hive mind architecture — multiple agent instances coordinated via Postgres LISTEN/NOTIFY.
3. **Execution**: Sub-agent delegation via OpenCode serve (async, background).
4. **Budget**: 400 EUR/month hard constraint. Model routing to stay within it.
5. **Memory**: Engram as the single persistent memory layer (SQLite + FTS5 + cloud sync).
6. **Skills**: Unified format with frontmatter. LLM-autonomous selection from compact index.
7. **Naming**: Mythology-inspired subsystem names (ATHENA, MORPHEUS, SENTINEL, HERMES, ATLAS, PROMETHEUS, MNEMO).
8. **Infrastructure**: Docker Compose on single homelab server. No Kubernetes.

---

## 11. Related Documents

| Document | Location |
|----------|----------|
| Skills Architecture Proposal | `personal-knowledgebase/docs/research/jarvis-skills-architecture-proposal.md` |
| MVP Proposal | `personal-knowledgebase/docs/research/jarvis-mvp-proposal.md` |
| Neuroscience Research (backlog) | `personal-knowledgebase/docs/ideas/neurociencia-cognitiva-aplicada-ia.md` |
| System Prompt | `config/system-prompt.md` |
| Journal (2026-03-31) | `personal-knowledgebase/journal/daily/2026-03-31.md` |
| Engram: Architecture Decisions | observation #3 (project: jarvis-dashboard) |
| Engram: Subsystem Naming | observation #27 (project: jarvis-dashboard) |
| Engram: Skills Architecture Archive | observation #20 (project: jarvis-dashboard) |
