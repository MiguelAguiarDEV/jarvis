---
name: server-guardrails
description: "Safety rules for server operations. Defines confirmation requirements and safe actions."
always: true
---

# Server Guardrails

## REQUIRES explicit user confirmation
- DROP/TRUNCATE/DELETE on production database without WHERE
- Stop jarvis-postgres (the main DB)
- Remove named Docker volumes (data loss)
- Modify 1Password secrets
- rm -rf ~/projects/ or ~/services/ (top-level delete)
- Change Cloudflare DNS
- Modify firewall/SSH/sudo config

## Does NOT need confirmation (user already asked = confirmation)
- Remove orphan/temp Docker containers (docker rm -f)
- Remove unnamed containers
- Restart services
- Clean /tmp files
- Kill processes the user asked to kill
- When user says "hazlo", "eliminalos", "ok", "dale" = confirmed

## ALWAYS safe
- Read: files, logs, status
- docker ps/logs, systemctl status
- git status/log/diff
- ls, cat, head, tail, grep
- df, free, top, htop, uptime
- svc logs, curl health endpoints

## SAFE with caution (do + report)
- Restart services (svc restart X)
- Rebuild containers (docker compose build)
- Git commit/push
- Create files/directories
- Install packages (apt, npm)
- Modify configs (keep backups)
- SELECT queries (no confirmation needed)

## When in doubt
Ask first. State the exact command and why.
