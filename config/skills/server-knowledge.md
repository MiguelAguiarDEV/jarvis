---
name: server-knowledge
description: "Auto-generated server state: system info, Docker services, network, secrets vault locations."
always: true
---
# Server Knowledge (auto-generated)
> Last scan: 2026-04-07 10:00:01 UTC

## System Info
- Hostname: jarvis
- OS: Ubuntu 24.04.4 LTS
- Kernel: 6.8.0-106-generic
- CPU: 4 cores
- RAM: 7.5Gi total, 2.1Gi used
- Disk: 136G/232G (62% used)
- Uptime: up 1 week, 6 days, 11 hours, 6 minutes
- Tailscale IP: 100.71.66.54

## Docker Services
| Name | Status | Ports | Image |
|------|--------|-------|-------|
| jarvis-mnemo-cloud | Up 33 minutes (healthy) | 100.71.66.54:8080->8080/tcp | jarvis-dashboard-mnemo-cloud |
| jarvis-postgres | Up 33 minutes (healthy) | 127.0.0.1:5432->5432/tcp | postgres:16-alpine |
| jarvis-n8n | Up 22 hours | 127.0.0.1:5678->5678/tcp | n8nio/n8n:latest |
| jarvis-swagger | Up 3 days | 80/tcp, 127.0.0.1:8081->8080/tcp | swaggerapi/swagger-ui |
| jarvis-dashboard | Up 3 days (healthy) | 100.71.66.54:3001->3001/tcp | jarvis-dashboard-dashboard |

## Systemd Services (custom)
- opencode-serve: active
- cloudflared: active
- smbd: active

## Directory Structure
```
~/projects/
  claude-code-api
  claude-code-leaked
  claude-code-ts-leaked
  jarvis-dashboard
  opencode
~/services/
  discord-bot
  discord-bot-backup-20260329-163926.tgz
  discord-bot.bak
  discord-bot-hotfix204-backup-20260329-175653.tgz
  discord-bot-hotfix-backup-20260329-170559.tgz
  discord-bot-multifix-backup-20260329-201152.tgz
  discord-bot-poller-backup-20260329-181557.tgz
  discord-bot.rollback-
  discord-bot-tooluse-backup-20260329-183050.tgz
  engram
  jarvis-dashboard
  n8n
  postgres
  svc
~/personal-knowledgebase/
  │
  agent
  AGENTS.md
  CLAUDE.md
  docs
  GEMINI.md
  journal
  node_modules
  opencode.json
  package.json
  package-lock.json
  projects
  README.md
  scripts
  test-results
```

## Public URLs
- Dashboard: https://jarvis.miguelaguiar.dev
- Mnemo API: https://mnemo.miguelaguiar.dev
- Portfolio: https://miguelaguiar.dev

## Service Management
- Start/stop services: `~/services/svc up|down|restart|logs <name>`
- Services use 1Password for secrets: `.env.tpl` with `op://` references
- Rebuild: `cd ~/services/<name> && docker compose build --no-cache`

## Network
- Docker network: postgres_default (shared by all services)
- Tailscale: all services bind to 100.71.66.54
- Cloudflare Tunnel: jarvis-homelab
- Samba: \\\\100.71.66.54\\jarvis (Tailscale only)

## Secrets (1Password vault: Desarrollo)
- jarvis-mnemo-cloud: DB URL, JWT secret, cloud API key
- jarvis-dashboard: API URL, API key
- jarvis-discord-bot: bot token, user ID
- jarvis-opencode-server: server password
- jarvis-samba: SMB credentials
- cloudflare: API key, tunnel token, zone/account IDs
- jarvis-postgres: DB password
