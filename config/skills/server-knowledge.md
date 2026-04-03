---
name: server-knowledge
description: "Auto-generated server state: system info, Docker services, network, secrets vault locations."
always: true
---
# Server Knowledge (auto-generated)
> Last scan: 2026-04-03 17:00:01 UTC

## System Info
- Hostname: jarvis
- OS: Ubuntu 24.04.4 LTS
- Kernel: 6.8.0-106-generic
- CPU: 4 cores
- RAM: 7.5Gi total, 2.2Gi used
- Disk: 129G/232G (59% used)
- Uptime: up 1 week, 2 days, 18 hours, 6 minutes
- Tailscale IP: 100.71.66.54

## Docker Services
| Name | Status | Ports | Image |
|------|--------|-------|-------|
| jarvis-mnemo-cloud | Up 4 minutes (healthy) | 100.71.66.54:8080->8080/tcp | jarvis-dashboard-mnemo-cloud |
| jarvis-swagger | Up 11 minutes | 80/tcp, 127.0.0.1:8081->8080/tcp | swaggerapi/swagger-ui |
| jarvis-discord-bot | Up 37 minutes | 127.0.0.1:9090->9090/tcp | jarvis-dashboard-discord-bot |
| jarvis-dashboard | Up 37 minutes (healthy) | 100.71.66.54:3001->3001/tcp | jarvis-dashboard-dashboard |
| modest_raman | Up 41 minutes | 0.0.0.0:34642->5432/tcp, [::]:34642->5432/tcp | postgres:16-alpine |
| quirky_swartz | Up 7 hours | 0.0.0.0:34538->5432/tcp, [::]:34538->5432/tcp | postgres:16-alpine |
| stupefied_pare | Up 7 hours | 0.0.0.0:34537->5432/tcp, [::]:34537->5432/tcp | postgres:16-alpine |
| recursing_carver | Up 7 hours | 0.0.0.0:34494->5432/tcp, [::]:34494->5432/tcp | postgres:16-alpine |
| serene_stonebraker | Up 7 hours | 0.0.0.0:34493->5432/tcp, [::]:34493->5432/tcp | postgres:16-alpine |
| objective_lewin | Up 40 hours | 0.0.0.0:34272->5432/tcp, [::]:34272->5432/tcp | postgres:16-alpine |
| epic_satoshi | Up 40 hours | 0.0.0.0:34271->5432/tcp, [::]:34271->5432/tcp | postgres:16-alpine |
| festive_ardinghelli | Up 40 hours | 0.0.0.0:34263->5432/tcp, [::]:34263->5432/tcp | postgres:16-alpine |
| silly_banach | Up 40 hours | 0.0.0.0:34259->5432/tcp, [::]:34259->5432/tcp | postgres:16-alpine |
| suspicious_williams | Up 40 hours | 0.0.0.0:34257->5432/tcp, [::]:34257->5432/tcp | postgres:16-alpine |
| epic_mcclintock | Up 40 hours | 0.0.0.0:34255->5432/tcp, [::]:34255->5432/tcp | postgres:16-alpine |
| elegant_khayyam | Up 2 days | 0.0.0.0:34124->5432/tcp, [::]:34124->5432/tcp | postgres:16-alpine |
| sad_maxwell | Up 2 days | 0.0.0.0:34123->5432/tcp, [::]:34123->5432/tcp | postgres:16-alpine |
| jarvis-postgres | Up 2 days (healthy) | 127.0.0.1:5432->5432/tcp | postgres:16-alpine |
| elegant_franklin | Up 2 days | 0.0.0.0:34067->5432/tcp, [::]:34067->5432/tcp | postgres:16-alpine |
| gallant_bhaskara | Up 2 days | 0.0.0.0:34056->5432/tcp, [::]:34056->5432/tcp | postgres:16-alpine |
| festive_feistel | Up 2 days | 0.0.0.0:34055->5432/tcp, [::]:34055->5432/tcp | postgres:16-alpine |
| dreamy_napier | Up 2 days | 0.0.0.0:34054->5432/tcp, [::]:34054->5432/tcp | postgres:16-alpine |
| clever_mccarthy | Up 2 days | 0.0.0.0:34053->5432/tcp, [::]:34053->5432/tcp | postgres:16-alpine |
| sleepy_fermat | Up 2 days | 0.0.0.0:34032->5432/tcp, [::]:34032->5432/tcp | postgres:16-alpine |
| quizzical_easley | Up 2 days | 0.0.0.0:34031->5432/tcp, [::]:34031->5432/tcp | postgres:16-alpine |
| nervous_booth | Up 2 days | 0.0.0.0:34030->5432/tcp, [::]:34030->5432/tcp | postgres:16-alpine |
| sharp_nash | Up 2 days | 0.0.0.0:34029->5432/tcp, [::]:34029->5432/tcp | postgres:16-alpine |

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
