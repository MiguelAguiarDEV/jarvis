# JARVIS Roadmap — Path to Full Independence

> Last updated: 2026-04-03
> Goal: JARVIS autónomo que no depende de OpenCode ni Claude Code para operar

## Current State (~65% complete)

### Done
- [x] Orchestrator Go con tool system (18 tools, dispatcher, tool-call loop max 3)
- [x] Skills architecture (registry, loader, LLM-autonomous, /skill-name, always:true)
- [x] LLM backend abstraction (Backend interface, swappable)
- [x] PROMETHEUS bridge (claude-agent-sdk query() → Claude API sin rate limit)
- [x] Monorepo containerizado (Docker Compose, 1Password op run, health checks)
- [x] Memory system (engram CLI wrapper: search_memory, save_memory)
- [x] Task management (create_task, list_tasks, complete_task)
- [x] Delegation (OpenCode serve sessions para coding tasks)
- [x] Notifications (Discord DM via Notifier interface)
- [x] Model routing (Sonnet/Opus por complejidad, budget auto-downgrade 90%)
- [x] Dashboard (chat, tasks, activity, memory, graph, traces UI, costs)
- [x] Discord bot (Hermes — DM routing, slash commands)

### Critical Path (ordered by dependency)

| # | Task | Status | Blocks |
|---|------|--------|--------|
| 1 | Filesystem tools (read_file, write_file, edit_file) | **DONE** | 3, 5 |
| 2 | Shell tool (bash) con guardrails | **DONE** | 3, 5 |
| 3 | Search tools (grep, glob) | **DONE** | 5 |
| 4 | Web tools (fetch_url, web_search) | fetch_url DONE, web_search pending | 5 |
| 5 | Traces en todas las tools | Not started | 7 |
| 6 | Rewire chat para usar solo PROMETHEUS (no OpenCode) | Not started | 7 |
| 7 | Eliminar OpenCode como dependencia para chat | Not started | — |

### Non-blocking improvements

| Task | Priority |
|------|----------|
| Cost dashboard (historical view, budget viz) | P1 |
| Dashboard HUD redesign (multi-panel terminal aesthetic) | P1 |
| Proactive behavior (JARVIS inicia acciones sin pedírselo) | P2 |
| Multi-agent coordination (Postgres LISTEN/NOTIFY) | P2 |
| PROMETHEUS containerización en compose | P1 |

## Key Discovery: Claude API Access

### Problem
Claude API con OAuth tokens (de la suscripción) tiene rate limits que bloquean el uso directo.
- curl / Go SDK / Node.js SDK → 429 (rate limited)
- Solo el CLI binary de Claude Code bypasea el rate limit

### Solution Found
`@anthropic-ai/claude-agent-sdk` exporta `query()` que usa Claude Code internamente.
Bypasea todos los rate limits, funciona con Opus.

### Current Architecture
```
JARVIS (Docker) → host.docker.internal:9876 → PROMETHEUS bridge.js → claude-agent-sdk query() → Claude API
```

### What This Means
- NO necesitamos OpenCode serve para chat — PROMETHEUS bridge lo reemplaza
- OpenCode serve SOLO se necesita para `delegate` (sub-agentes de coding que necesitan tools de Claude Code)
- El día que implementemos filesystem/shell tools en Go, `delegate` a OpenCode será opcional

### Failed Approaches (DO NOT RETRY)
1. ~~curl con OAuth Bearer token~~ → 429
2. ~~Go anthropic-sdk-go con custom Transport~~ → 429
3. ~~Node.js @anthropic-ai/sdk con custom fetch~~ → 429
4. ~~Replicar headers de Claude Code (x-app, session-id, betas)~~ → 429
5. ~~API temporal create_api_key~~ → Investigado pero no implementado

### Working Approaches
1. `claude -p` (CLI binary) → Funciona siempre (first-party priority)
2. `claude-agent-sdk query()` → Funciona siempre (usa CLI internamente) ← **ESTO USAMOS**
3. OpenCode serve (usa claude-auth plugin) → Funciona (lo que teníamos antes)

## Technical Decisions

| Decision | Rationale |
|----------|-----------|
| Orchestrator Go owns tool definitions | LLM backend es swappable |
| PROMETHEUS bridge en Node.js | claude-agent-sdk es npm package |
| OpenCode serve en systemd | Necesita filesystem del host para delegate |
| 1Password op run siempre | Secrets nunca tocan disco |
| 100% test + logging coverage | Every function gets slog + tests |
| Docker Compose para todo | Excepto OpenCode serve (filesystem access) |

## Mythology Naming

| Name | Component | Role |
|------|-----------|------|
| ATHENA | Go backend | Brain — orchestration, API, tools, skills |
| NEXUS | Next.js dashboard | Eyes — visualization, chat UI |
| HERMES | Discord bot | Messenger — DM routing, notifications |
| PROMETHEUS | Claude bridge | Fire — LLM access via claude-agent-sdk |
| ENGRAM | Memory system | Memory — persistent cross-session knowledge |
