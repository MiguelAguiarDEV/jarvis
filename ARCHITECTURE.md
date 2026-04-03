# JARVIS Architecture

> Personal AI agent system running on a homelab server. Autonomous reasoning, delegation, and persistent memory.

## 1. System Overview

JARVIS is a multi-component AI agent that receives requests via web dashboard or Discord, reasons about them, executes tools, delegates work to sub-agents, and persists knowledge across sessions.

**Mythology naming scheme** -- each subsystem is named after a Greek deity reflecting its role:

| Subsystem    | Role                        | Runtime     |
|--------------|-----------------------------|-------------|
| **ATHENA**   | Orchestrator / brain        | Go (binary) |
| **NEXUS**    | Web dashboard               | Next.js 14  |
| **HERMES**   | Discord bot                 | Go          |
| **PROMETHEUS** | LLM executor / worker     | Go (in ATHENA) |
| **ATLAS**    | Skill registry + loader     | Go (in ATHENA) |
| **MORPHEUS** | Memory consolidation        | Go (in ATHENA) |
| **SENTINEL** | Health monitoring           | Go (in ATHENA) |
| **MNEMO**    | Persistent memory (engram)  | Go (in ATHENA) |

### High-Level Data Flow

```
 Discord DM                 Web UI (NEXUS :3001)
     |                            |
  HERMES                     HTTP POST
     |                            |
     +--------> ATHENA :8080 <----+
                  |
        +---------+---------+
        |         |         |
     ATLAS    PROMETHEUS   MNEMO
   (skills)  (LLM+tools) (memory)
        |         |
        |    Claude API
        |   (native tools)
        |
    config/skills/
    personal-kb skills
```

## 2. Component Architecture

### ATHENA (athena/)

Orchestrator brain. Receives messages, manages conversation, dispatches tools, coordinates subsystems.

| Package                         | Purpose                                      |
|---------------------------------|----------------------------------------------|
| `internal/cloud/jarvis/`        | Orchestrator: message handling, tool loop     |
| `internal/athena/`              | Tool interface, dispatcher, builtin tools     |
| `internal/atlas/`               | Skill schema, registry, loader                |
| `internal/prometheus/`          | LLM backends (Claude API, OpenCode), workers  |
| `internal/prometheus/tools/`    | Native tool executors (bash, file, grep, glob)|
| `internal/morpheus/`            | Memory consolidation (dream cycles)           |
| `internal/sentinel/`            | Health checks (ticker, system checks)         |
| `internal/mcp/`                 | MCP protocol server                           |
| `internal/cloud/notifications/` | Notification dispatch (Discord DMs)           |
| `internal/store/`               | PostgreSQL persistence (messages, tasks)      |
| `internal/server/`              | HTTP server, API routes                       |

- **Port**: 8080 (bound to Tailscale IP 100.71.66.54)
- **API**: REST -- `/health`, `/api/chat`, `/api/tasks`, `/api/conversations`
- **Go module**: `github.com/Gentleman-Programming/engram` (legacy path, not renamed)

### NEXUS (nexus/)

Web dashboard for chatting with JARVIS and viewing tasks/memory.

- **Stack**: Next.js 14, React 18, TypeScript
- **Port**: 3001 (bound to Tailscale IP 100.71.66.54)
- **Key deps**: cytoscape (graph viz), react-markdown
- **Connects to**: ATHENA API at `http://engram-cloud:8080` (Docker internal)
- **Mounts**: personal-knowledgebase at `/kb` (read-only)

### HERMES (hermes/)

Discord bot -- DM interface to JARVIS.

- **Stack**: Go, discordgo
- **Key packages**: `internal/agent/`, `internal/discord/`, `internal/session/`, `internal/observability/`
- **Port**: 9090 (metrics, localhost only)
- **Connects to**: ATHENA API at `http://engram-cloud:8080`
- **Security**: `ALLOWED_USER_IDS` restricts to owner only

### PROMETHEUS (athena/internal/prometheus/)

LLM executor. Two modes:

| Mode          | When                               | How                                        |
|---------------|------------------------------------|--------------------------------------------|
| **Native**    | Default (`PROMETHEUS_USE_OPENCODE!=true`) | Direct Claude API + Go-native tool executors |
| **OpenCode**  | Legacy fallback                    | OpenCode serve sessions via HTTP            |

Native tools: `bash`, `file_read`, `file_write`, `file_edit`, `glob`, `grep`

The native worker mounts project directories from the host and executes tools in-process.

## 3. Data Flow

### Chat Message (Web)

```
User -> NEXUS (browser) -> POST /api/chat -> ATHENA orchestrator
  -> build system prompt (+ always-on skills)
  -> send to Claude API (PROMETHEUS)
  -> if tool_calls: dispatch via ATHENA Dispatcher -> execute -> return result -> loop (max 3)
  -> final text response -> NEXUS -> User
```

### Chat Message (Discord)

```
User -> Discord DM -> HERMES -> POST to ATHENA /api/chat
  -> same orchestrator flow as above
  -> response -> HERMES -> Discord DM reply
```

### Async Delegation

```
User: "fix the login bug in comparador-seguro"
  -> ATHENA sees delegate tool call
  -> creates Job (athena.JobTracker)
  -> PROMETHEUS NativeWorker runs in background
    -> Claude API + native tools (bash, file ops)
    -> Worker completes
  -> HERMES sends Discord DM notification with result
```

### Skill Loading

```
1. ATLAS Registry.Build() scans 3 catalog tiers at startup
2. always:true skills injected into every system prompt
3. For dynamic skills: compact index (name + description) sent to LLM
4. LLM calls load_skill(name) tool -> ATLAS Loader returns content
5. Skill content injected into conversation context
6. User can force-load with /skill-name command
```

## 4. Skills Architecture

### Three Catalog Tiers

| Tier      | Path                           | Priority | Purpose                    |
|-----------|--------------------------------|----------|----------------------------|
| global    | personal-knowledgebase skills  | 1 (low)  | Cross-project skills       |
| ops       | `config/skills/`               | 2        | JARVIS operational skills  |
| project   | `athena/skills/`               | 3 (high) | Project-specific overrides |

Higher tier overrides lower tier when names collide.

### Skill File Format

```yaml
---
name: delegation
description: "Sub-agent delegation via OpenCode serve."
always: false
triggers: ["delegate", "sub-agent"]
---

# Skill content (markdown)
Instructions for the LLM...
```

- **name**: `^[a-z0-9-]+$`, required
- **description**: max 200 chars, required
- **always**: if `true`, injected into every prompt
- **triggers**: keyword hints for LLM selection

### Loading Modes

| Mode              | Mechanism                                    |
|-------------------|----------------------------------------------|
| Always-on         | `always: true` -- injected at startup        |
| LLM-autonomous    | Compact index shown, LLM calls `load_skill`  |
| User override     | `/skill-name` in message                     |

## 5. Tool System

### ATHENA Tools (orchestrator-level)

8 builtin tools available to the LLM during chat:

| Tool              | Purpose                              |
|-------------------|--------------------------------------|
| `load_skill`      | Load a skill by name from ATLAS      |
| `create_task`     | Create task in task board             |
| `list_tasks`      | List tasks by status                 |
| `complete_task`   | Mark a task done                     |
| `delegate`        | Async delegation to PROMETHEUS worker|
| `notify`          | Send Discord DM via HERMES           |
| `search_memory`   | Search MNEMO (engram) for knowledge  |
| `save_memory`     | Save knowledge to MNEMO (engram)     |

### Tool Interface

```go
type Tool interface {
    Name() string
    Description() string
    Parameters() json.RawMessage  // JSON Schema
    Execute(ctx context.Context, params json.RawMessage) (ToolResult, error)
}
```

### Dispatcher Pattern

```
LLM response contains tool_calls[]
  -> for each tool_call:
       Dispatcher.Dispatch(name, params) -> Tool.Execute() -> ToolResult
  -> collect results, send back to LLM
  -> repeat (max 3 iterations)
```

### PROMETHEUS Native Tools (worker-level)

6 tools for sub-agent code execution: `bash`, `file_read`, `file_write`, `file_edit`, `glob`, `grep`

```go
type ToolExecutor interface {
    Name() string
    Description() string
    InputSchema() json.RawMessage
    Execute(ctx context.Context, input json.RawMessage) (string, error)
}
```

## 6. Memory System

### Engram

Persistent memory across sessions. Local SQLite is source of truth; cloud (PostgreSQL) is replication target.

| Operation        | Purpose                                  |
|------------------|------------------------------------------|
| `search_memory`  | FTS5 full-text search over observations  |
| `save_memory`    | Store knowledge with type/scope/topic    |
| `mem_context`    | Recent session history (fast recall)     |
| Session summary  | Structured end-of-session snapshot       |

### MORPHEUS (Memory Consolidation)

Background process that runs "dream cycles" -- consolidates, deduplicates, and strengthens memory patterns. Operates on phases with locking to prevent concurrent consolidation.

## 7. Infrastructure

### Docker Compose Stack

| Service          | Container              | Image/Build    | Port                    |
|------------------|------------------------|----------------|-------------------------|
| `postgres`       | jarvis-postgres        | postgres:16    | 127.0.0.1:5432          |
| `engram-cloud`   | jarvis-engram-cloud    | athena/        | 100.71.66.54:8080       |
| `dashboard`      | jarvis-dashboard       | nexus/         | 100.71.66.54:3001       |
| `discord-bot`    | jarvis-discord-bot     | hermes/        | 127.0.0.1:9090 (metrics)|

### Networking

- **Tailscale**: services bound to `100.71.66.54` (homelab Tailscale IP)
- **Docker internal**: services communicate via Docker DNS (`engram-cloud:8080`)
- **Host access**: `extra_hosts: host.docker.internal:host-gateway` for host services
- **Volume mounts**: project dirs mounted into engram-cloud for native tool execution

### Health Checks

All services have health checks with restart policy `unless-stopped`:
- postgres: `pg_isready`
- engram-cloud: `wget http://localhost:8080/health`
- dashboard: Node.js fetch to `/`
- SENTINEL: internal ticker checks every 15 min (server, DB, services)

### Secrets Management

All secrets via **1Password** `op run`:
```bash
op run --env-file=.env.tpl -- docker compose up -d
```
`.env.tpl` maps `op://Desarrollo/...` references to environment variables. No secrets in code or git.

## 8. Security

| Layer              | Mechanism                                          |
|--------------------|----------------------------------------------------|
| Secret injection   | 1Password Service Account (`op run`)               |
| Dashboard auth     | Cloudflare Access (external), API key (internal)   |
| Discord bot        | `ALLOWED_USER_IDS` -- owner only                   |
| Engram Cloud API   | JWT (`ENGRAM_JWT_SECRET`) + API key                |
| Inter-service      | Docker network isolation + API keys                |
| No secrets in git  | `.env.tpl` has `op://` refs only                   |
| Host volumes       | Read-only where possible (`:ro`)                   |

## 9. Development

### Start / Stop

```bash
# Start (with 1Password secret injection + rebuild)
./start.sh --op --build

# Stop
./stop.sh

# Manual
op run --env-file=.env.tpl -- docker compose up -d --build
```

### Go Module

```
module: github.com/Gentleman-Programming/engram
go: 1.22+
```

Legacy module path -- not renamed to avoid import churn.

### Testing

```bash
cd athena && go test ./internal/...
```

Key test files: `atlas/*_test.go`, `athena/*_test.go`, `prometheus/*_test.go`

### Project Layout

```
jarvis-dashboard/
  athena/              # ATHENA brain (Go)
    internal/
      athena/          # Tool interface + builtins
      atlas/           # Skill registry + loader
      cloud/jarvis/    # Orchestrator
      morpheus/        # Memory consolidation
      prometheus/      # LLM backends + workers
        tools/         # Native tool executors
      sentinel/        # Health monitoring
      mcp/             # MCP protocol
      store/           # PostgreSQL persistence
      server/          # HTTP server
  nexus/               # NEXUS dashboard (Next.js)
  hermes/              # HERMES Discord bot (Go)
  config/
    system-prompt.md   # JARVIS system prompt
    skills/            # Ops-tier skill files
  docker-compose.yml
  .env.tpl             # 1Password secret template
  start.sh / stop.sh
```

## 10. Decision Log

- **SDD artifacts**: `~/personal-knowledgebase/docs/research/` -- spec-driven development docs
- **Architecture decisions**: engram observations (search `project:jarvis-dashboard type:architecture`)
- **Project narrative**: `~/personal-knowledgebase/docs/project-narratives/jarvis-story.md`
- **Key decisions recorded in engram**:
  - Skills architecture (SDD: jarvis-skills-architecture) -- 26 tasks, all complete
  - PROMETHEUS v2: native tool executor replacing OpenCode dependency
  - Docker Compose containerization
  - Mythology naming scheme
